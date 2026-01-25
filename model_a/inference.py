"""
單張圖片推論腳本
用於測試訓練好的模型
"""

import torch
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
from pathlib import Path
from typing import Dict, List
import cv2

import config
from model import FashionMultiTaskModel


class FashionPredictor:
    """服飾預測器"""
    
    def __init__(self, checkpoint_path: str = None):
        """
        Args:
            checkpoint_path: 模型檢查點路徑 (None 則使用 best.pth)
        """
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # 載入模型
        self.model = FashionMultiTaskModel().to(self.device)
        
        if checkpoint_path is None:
            checkpoint_path = config.CHECKPOINT_DIR / 'best.pth'
        
        if Path(checkpoint_path).exists():
            checkpoint = torch.load(checkpoint_path, map_location=self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            print(f"✅ 載入模型: {checkpoint_path}")
        else:
            print(f"⚠️  找不到檢查點: {checkpoint_path}")
            print("使用未訓練的模型")
        
        self.model.eval()
        
        # 圖片轉換
        self.transform = transforms.Compose([
            transforms.Resize((config.IMG_SIZE, config.IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    
    def predict(self, image_path: str, top_k: int = 3) -> Dict:
        """
        預測單張圖片
        
        Args:
            image_path: 圖片路徑
            top_k: 返回 Top-K 類別
        
        Returns:
            dict: 預測結果
        """
        # 載入圖片
        image = Image.open(image_path).convert('RGB')
        original_size = image.size
        
        # 轉換
        image_tensor = self.transform(image).unsqueeze(0).to(self.device)
        
        # 預測
        with torch.no_grad():
            pred = self.model.predict(image_tensor, threshold=config.ATTRIBUTE_THRESHOLD)
        
        # 類別預測
        category_probs = pred['category_probs'][0].cpu().numpy()
        top_k_indices = np.argsort(category_probs)[-top_k:][::-1]
        
        top_k_categories = []
        for idx in top_k_indices:
            top_k_categories.append({
                'name': config.CATEGORY_NAMES[idx],
                'probability': float(category_probs[idx]),
                'index': int(idx)
            })
        
        # 屬性預測
        attribute_probs = pred['attribute_probs'][0].cpu().numpy()
        attribute_pred = pred['attribute_pred'][0].cpu().numpy()
        
        active_attributes = []
        for i, is_active in enumerate(attribute_pred):
            if is_active:
                active_attributes.append({
                    'name': config.ATTRIBUTE_NAMES[i],
                    'probability': float(attribute_probs[i]),
                    'index': int(i)
                })
        
        # Embedding
        embedding = pred['embedding'][0].cpu().numpy()
        
        # 提取主色調
        dominant_colors = self.extract_dominant_colors(image_path)
        
        # 推斷風格標籤
        style_tags = self.infer_style_tags(active_attributes)
        
        result = {
            'image_path': str(image_path),
            'image_size': original_size,
            'category': {
                'top_1': top_k_categories[0],
                'top_k': top_k_categories
            },
            'attributes': active_attributes,
            'colors': dominant_colors,
            'style_tags': style_tags,
            'embedding': embedding.tolist(),
            'embedding_dim': len(embedding)
        }
        
        return result
    
    def extract_dominant_colors(self, image_path: str, n_colors: int = 3) -> List[Dict]:
        """
        提取主色調 (使用 K-Means)
        
        Args:
            image_path: 圖片路徑
            n_colors: 提取顏色數量
        
        Returns:
            list: [{rgb, hex, percentage}, ...]
        """
        # 讀取圖片 (支援中文路徑)
        # cv2.imread 不支援中文路徑, 改用 imdecode
        img_array = np.fromfile(str(image_path), dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if image is None:
            print(f"❌ 無法讀取圖片: {image_path}")
            return []
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 調整大小以加速
        image = cv2.resize(image, (150, 150))
        
        # 重塑為像素列表 (float32)
        pixels = image.reshape(-1, 3).astype(np.float32)
        
        # 使用 OpenCV 的 K-Means
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        flags = cv2.KMEANS_RANDOM_CENTERS
        _, labels, centers = cv2.kmeans(pixels, n_colors, None, criteria, 10, flags)
        
        # 獲取顏色 (轉回 uint8)
        colors = centers.astype(int)
        labels = labels.flatten()
        
        # 計算每個顏色的比例
        # labels 是 [0, 1, 2, 0, ...]
        counts = np.bincount(labels)
        percentages = counts / len(labels)
        
        # 按比例排序
        sorted_indices = np.argsort(percentages)[::-1]
        
        dominant_colors = []
        for idx in sorted_indices:
            rgb = colors[idx].tolist()
            hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb)
            
            # 簡單的背景過濾: 如果顏色過於接近純白 (sum > 700) 或純黑 (sum < 30) 且佔比 > 30%
            # 視為背景剔除 (除非只剩這個顏色)
            color_sum = sum(rgb)
            if (color_sum > 700 or color_sum < 30) and percentages[idx] > 0.3:
                if len(sorted_indices) > 1 and len(dominant_colors) == 0:
                    continue  # 跳過背景色
            
            dominant_colors.append({
                'rgb': rgb,
                'hex': hex_color,
                'percentage': float(percentages[idx])
            })
            
            if len(dominant_colors) >= n_colors:
                break
        
        # 萬一全部都被過濾光了(極端情況)，退回到原始的第一名
        if not dominant_colors and len(sorted_indices) > 0:
            idx = sorted_indices[0]
            rgb = colors[idx].tolist()
            return [{
                'rgb': rgb,
                'hex': '#{:02x}{:02x}{:02x}'.format(*rgb),
                'percentage': float(percentages[idx])
            }]
        
        return dominant_colors
    
    def infer_style_tags(self, active_attributes: List[Dict]) -> List[str]:
        """
        根據屬性推斷風格標籤
        
        Args:
            active_attributes: 啟用的屬性列表
        
        Returns:
            list: 風格標籤
        """
        attr_names = [attr['name'] for attr in active_attributes]
        
        style_tags = []
        for style, keywords in config.STYLE_MAPPING.items():
            if any(keyword in attr_names for keyword in keywords):
                style_tags.append(style)
        
        return style_tags
    
    def print_result(self, result: Dict):
        """打印預測結果"""
        print("\n" + "="*60)
        print("🎯 預測結果")
        print("="*60)
        
        print(f"\n📸 圖片: {result['image_path']}")
        print(f"📐 尺寸: {result['image_size']}")
        
        print(f"\n【類別預測】")
        print(f"  🥇 Top-1: {result['category']['top_1']['name']} ({result['category']['top_1']['probability']*100:.2f}%)")
        
        print(f"\n  Top-{len(result['category']['top_k'])} 預測:")
        for i, cat in enumerate(result['category']['top_k'], 1):
            print(f"    {i}. {cat['name']:20s} {cat['probability']*100:.2f}%")
        
        print(f"\n【屬性預測】 (共 {len(result['attributes'])} 個)")
        for attr in result['attributes']:
            print(f"  ✓ {attr['name']:20s} ({attr['probability']*100:.2f}%)")
        
        print(f"\n【主色調】")
        for i, color in enumerate(result['colors'], 1):
            print(f"  {i}. RGB{tuple(color['rgb'])} {color['hex']} ({color['percentage']*100:.1f}%)")
        
        if result['style_tags']:
            print(f"\n【風格標籤】")
            for tag in result['style_tags']:
                print(f"  • {tag}")
        
        print(f"\n【Embedding】")
        print(f"  維度: {result['embedding_dim']}")
        print(f"  範例值: {result['embedding'][:5]}...")
        
        print("\n" + "="*60)


# ==================== 主程式 ====================
if __name__ == '__main__':
    import sys
    
    # 創建預測器
    predictor = FashionPredictor()
    
    # 測試圖片路徑
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # 使用範例圖片 (來自 train.txt 的第一張圖)
        # train.txt 路徑範例: img/Sweet_Crochet_Blouse/img_00000070.jpg
        # config.IMG_DIR: .../model_a/.../data
        image_path = config.IMG_DIR / "img" / "Sweet_Crochet_Blouse" / "img_00000078.jpg"
        print(f"⚠️  未指定圖片路徑,使用範例圖片: {image_path}")
    
    if not Path(image_path).exists():
        print(f"❌ 圖片不存在: {image_path}")
        sys.exit(1)
    
    # 預測
    result = predictor.predict(image_path, top_k=5)
    
    # 打印結果
    predictor.print_result(result)
    
    # 保存結果
    import json
    output_path = config.RESULT_DIR / 'prediction_result.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 結果已保存至: {output_path}")
