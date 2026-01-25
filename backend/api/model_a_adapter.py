import sys
from pathlib import Path
from PIL import Image
import io
import torch
import logging

# 加入專案根目錄到 sys.path，確保能 import model_a
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

try:
    from model_a.inference import FashionPredictor
    MODEL_A_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Model A import failed: {e}")
    MODEL_A_AVAILABLE = False

logger = logging.getLogger(__name__)

class ModelAAdapter:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelAAdapter, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.predictor = None
        if not MODEL_A_AVAILABLE:
            logger.warning("Model A module not found.")
            return

        # 模型權重路徑
        # 優先尋找最佳模型
        checkpoint_dir = BASE_DIR / "model_a" / "output" / "checkpoints"
        checkpoint_path = checkpoint_dir / "best.pth"
        
        # 檢查是否需要合併檔案 (針對 GitHub 上傳限制)
        if not checkpoint_path.exists():
            parts = sorted(checkpoint_dir.glob("best.pth.part*"))
            if parts:
                logger.info(f"🧩 Found {len(parts)} parts, merging model...")
                try:
                    with open(checkpoint_path, 'wb') as outfile:
                        for part in parts:
                            with open(part, 'rb') as infile:
                                outfile.write(infile.read())
                    logger.info("✅ Model merged successfully.")
                except Exception as e:
                    logger.error(f"❌ Failed to merge model parts: {e}")

        if checkpoint_path.exists():
            try:
                # 載入模型 (這裡會自動使用 GPU 或 CPU)
                self.predictor = FashionPredictor(str(checkpoint_path))
                logger.info(f"✅ Model A loaded from {checkpoint_path}")
            except Exception as e:
                logger.error(f"❌ Failed to load Model A: {e}")
                self.predictor = None
        else:
            logger.warning(f"⚠️ Model A checkpoint not found at {checkpoint_path}")
            self.predictor = None

    def analyze_image(self, image_bytes: bytes):
        """
        分析圖片並返回結構化特徵
        
        Returns:
            dict: {
                "category": str,
                "attributes": list[str],
                "colors": list[str], # Hex codes
                "style": list[str],
                "confidence": float
            }
        """
        if not self.predictor:
            return None
            
        try:
            # 將 bytes 轉換為 PIL Image
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            # 儲存為暫存檔供推論使用 (inference.py 設計是用路徑讀取)
            # 為了效能，我們稍後應該修改 inference.py 支援直接傳入 PIL Image
            # 但現在先用最簡單的方法: 改寫 inference.py 的介面
            
            # 使用我們修改過後的 predictor.predict_from_image (稍後需要在 inference.py 中增加此方法)
            # 或者直接修改 inference.py 讓 predict 接受 PIL Image
            
            # 這裡我們需要對 inference.py 做一點小修改來支援 memory image
            # 暫時先把 PIL image 傳過去，假設我們會修改 inference.py
            
            # 呼叫預測 (注意：這裡假設 predict 已經被修改為支援 PIL Image 或我們需要修改它)
            # 為了不改動太多 model_a 的代碼，我們先用臨時文件的方法 (雖然慢一點但最穩)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                image.save(tmp.name)
                tmp_path = tmp.name
            
            result = self.predictor.predict(tmp_path, top_k=3)
            
            # 清理暫存檔
            Path(tmp_path).unlink()
            
            # 格式化輸出
            return self._format_result(result)
            
        except Exception as e:
            logger.error(f"❌ Model A inference error: {e}")
            return None

    def _format_result(self, raw_result):
        """將 Model A 的原始輸出轉換為前端需要的格式"""
        
        # 類別 (Category)
        category = raw_result['category']['top_1']['name']
        confidence = raw_result['category']['top_1']['probability']
        
        # 屬性 (Attributes)
        attributes = [attr['name'] for attr in raw_result['attributes']]
        
        # 顏色 (Colors) - 只取前 2 個主要顏色的 Hex
        colors = [c['hex'] for c in raw_result['colors'][:2]]
        
        # 風格 (Style)
        style = raw_result['style_tags']
        
        # 擴充屬性：如果信心度夠高，把類別也加到屬性標籤裡，方便搜尋
        if confidence > 0.6:
            attributes.append(category)
            
        return {
            "category": category,
            "category_zh": translate_category(category), # 需要一個翻譯函數
            "attributes": attributes,
            "colors": colors,
            "style": style,
            "confidence": confidence,
            "source": "model_a" # 標記來源
        }

# 簡單的翻譯對照表 (DeepFashion -> 中文)
def translate_category(eng_name):
    MAPPING = {
        'Dress': '連身裙', 'Tee': 'T恤', 'Blouse': '女式襯衫', 'Top': '上衣',
        'Shorts': '短褲', 'Skirt': '裙子', 'Jeans': '牛仔褲', 'Jacket': '夾克',
        'Cardigan': '針織外套', 'Coat': '大衣', 'Sweater': '毛衣', 'Hoodie': '帽T',
        'Tank': '背心', 'Joggers': '慢跑褲', 'Leggings': '緊身褲',
        # ... 其他類別
    }
    return MAPPING.get(eng_name, eng_name)
