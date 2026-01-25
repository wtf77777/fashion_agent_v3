"""
Model A - 多任務學習模型
同時預測服飾類別和屬性
"""

import torch
import torch.nn as nn
import torchvision.models as models
from typing import Dict, Tuple
import config


class FashionMultiTaskModel(nn.Module):
    """服飾多任務學習模型"""
    
    def __init__(
        self,
        num_categories: int = config.NUM_CATEGORIES,
        num_attributes: int = config.NUM_ATTRIBUTES,
        embedding_dim: int = config.EMBEDDING_DIM,
        backbone: str = config.BACKBONE,
        pretrained: bool = True
    ):
        """
        Args:
            num_categories: 類別數量 (50)
            num_attributes: 屬性數量 (26)
            embedding_dim: Embedding 維度 (512)
            backbone: 預訓練模型名稱
            pretrained: 是否使用預訓練權重
        """
        super().__init__()
        
        self.num_categories = num_categories
        self.num_attributes = num_attributes
        self.embedding_dim = embedding_dim
        
        # ==================== Backbone ====================
        self.backbone, self.feature_dim = self._build_backbone(backbone, pretrained)
        
        # ==================== Embedding Layer ====================
        self.embedding_layer = nn.Sequential(
            nn.Linear(self.feature_dim, embedding_dim),
            nn.BatchNorm1d(embedding_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3)
        )
        
        # ==================== Category Head ====================
        self.category_head = nn.Sequential(
            nn.Linear(embedding_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_categories)
        )
        
        # ==================== Attribute Head ====================
        self.attribute_head = nn.Sequential(
            nn.Linear(embedding_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_attributes)
        )
        
        print(f"✅ 模型初始化完成:")
        print(f"  - Backbone: {backbone}")
        print(f"  - Feature Dim: {self.feature_dim}")
        print(f"  - Embedding Dim: {embedding_dim}")
        print(f"  - Categories: {num_categories}")
        print(f"  - Attributes: {num_attributes}")
    
    def _build_backbone(self, backbone: str, pretrained: bool) -> Tuple[nn.Module, int]:
        """構建 Backbone 網路"""
        
        if backbone == 'resnet50':
            model = models.resnet50(pretrained=pretrained)
            feature_dim = model.fc.in_features
            model.fc = nn.Identity()  # 移除最後的全連接層
            
        elif backbone == 'efficientnet_b0':
            model = models.efficientnet_b0(pretrained=pretrained)
            feature_dim = model.classifier[1].in_features
            model.classifier = nn.Identity()
            
        elif backbone == 'mobilenet_v3_large':
            model = models.mobilenet_v3_large(pretrained=pretrained)
            feature_dim = model.classifier[0].in_features
            model.classifier = nn.Identity()
            
        else:
            raise ValueError(f"不支援的 backbone: {backbone}")
        
        return model, feature_dim
    
    def forward(self, x: torch.Tensor, return_embedding: bool = False) -> Dict[str, torch.Tensor]:
        """
        前向傳播
        
        Args:
            x: 輸入圖片 [B, 3, H, W]
            return_embedding: 是否返回 embedding
        
        Returns:
            dict: {
                'category_logits': [B, num_categories],
                'attribute_logits': [B, num_attributes],
                'embedding': [B, embedding_dim] (可選)
            }
        """
        # 特徵提取
        features = self.backbone(x)  # [B, feature_dim]
        
        # Embedding
        embedding = self.embedding_layer(features)  # [B, embedding_dim]
        
        # 類別預測
        category_logits = self.category_head(embedding)  # [B, num_categories]
        
        # 屬性預測
        attribute_logits = self.attribute_head(embedding)  # [B, num_attributes]
        
        output = {
            'category_logits': category_logits,
            'attribute_logits': attribute_logits,
        }
        
        if return_embedding:
            output['embedding'] = embedding
        
        return output
    
    def predict(self, x: torch.Tensor, threshold: float = 0.5) -> Dict[str, torch.Tensor]:
        """
        預測模式 (帶 softmax/sigmoid)
        
        Args:
            x: 輸入圖片 [B, 3, H, W]
            threshold: 屬性預測閾值
        
        Returns:
            dict: {
                'category_probs': [B, num_categories],
                'category_pred': [B],
                'attribute_probs': [B, num_attributes],
                'attribute_pred': [B, num_attributes],
                'embedding': [B, embedding_dim]
            }
        """
        self.eval()
        with torch.no_grad():
            output = self.forward(x, return_embedding=True)
            
            # 類別預測
            category_probs = torch.softmax(output['category_logits'], dim=1)
            category_pred = torch.argmax(category_probs, dim=1)
            
            # 屬性預測
            attribute_probs = torch.sigmoid(output['attribute_logits'])
            attribute_pred = (attribute_probs > threshold).float()
            
            return {
                'category_probs': category_probs,
                'category_pred': category_pred,
                'attribute_probs': attribute_probs,
                'attribute_pred': attribute_pred,
                'embedding': output['embedding']
            }


class MultiTaskLoss(nn.Module):
    """多任務學習損失函數"""
    
    def __init__(
        self,
        category_weight: float = 1.0,
        attribute_weight: float = 0.5,
        attribute_loss_type: str = 'bce'
    ):
        """
        Args:
            category_weight: 類別損失權重
            attribute_weight: 屬性損失權重
            attribute_loss_type: 屬性損失類型 ('bce' 或 'focal')
        """
        super().__init__()
        
        self.category_weight = category_weight
        self.attribute_weight = attribute_weight
        self.attribute_loss_type = attribute_loss_type
        
        # 類別損失 (Cross Entropy)
        self.category_loss_fn = nn.CrossEntropyLoss()
        
        # 屬性損失 (Binary Cross Entropy)
        if attribute_loss_type == 'bce':
            self.attribute_loss_fn = nn.BCEWithLogitsLoss()
        elif attribute_loss_type == 'focal':
            self.attribute_loss_fn = FocalLoss(alpha=config.FOCAL_ALPHA, gamma=config.FOCAL_GAMMA)
        else:
            raise ValueError(f"不支援的屬性損失類型: {attribute_loss_type}")
    
    def forward(self, outputs: Dict[str, torch.Tensor], targets: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """
        計算總損失
        
        Args:
            outputs: 模型輸出
            targets: 真實標籤
        
        Returns:
            dict: {
                'total_loss': 總損失,
                'category_loss': 類別損失,
                'attribute_loss': 屬性損失
            }
        """
        # 類別損失
        category_loss = self.category_loss_fn(
            outputs['category_logits'],
            targets['category']
        )
        
        # 屬性損失
        attribute_loss = self.attribute_loss_fn(
            outputs['attribute_logits'],
            targets['attributes']
        )
        
        # 總損失
        total_loss = (
            self.category_weight * category_loss +
            self.attribute_weight * attribute_loss
        )
        
        return {
            'total_loss': total_loss,
            'category_loss': category_loss,
            'attribute_loss': attribute_loss
        }


class FocalLoss(nn.Module):
    """Focal Loss for imbalanced classification"""
    
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        BCE_loss = nn.functional.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
        pt = torch.exp(-BCE_loss)
        F_loss = self.alpha * (1 - pt) ** self.gamma * BCE_loss
        return F_loss.mean()


# ==================== 測試程式碼 ====================
if __name__ == '__main__':
    print("🧪 測試 Fashion Multi-Task Model")
    
    # 創建模型
    model = FashionMultiTaskModel()
    
    # 測試輸入
    batch_size = 4
    x = torch.randn(batch_size, 3, config.IMG_SIZE, config.IMG_SIZE)
    
    print(f"\n📊 輸入形狀: {x.shape}")
    
    # 前向傳播
    output = model(x, return_embedding=True)
    
    print(f"\n📦 輸出形狀:")
    print(f"  - Category Logits: {output['category_logits'].shape}")
    print(f"  - Attribute Logits: {output['attribute_logits'].shape}")
    print(f"  - Embedding: {output['embedding'].shape}")
    
    # 測試預測
    pred = model.predict(x)
    
    print(f"\n🎯 預測結果:")
    print(f"  - Category Probs: {pred['category_probs'].shape}")
    print(f"  - Category Pred: {pred['category_pred']}")
    print(f"  - Attribute Probs: {pred['attribute_probs'].shape}")
    print(f"  - Attribute Pred: {pred['attribute_pred'].shape}")
    
    # 測試損失函數
    loss_fn = MultiTaskLoss()
    
    targets = {
        'category': torch.randint(0, config.NUM_CATEGORIES, (batch_size,)),
        'attributes': torch.randint(0, 2, (batch_size, config.NUM_ATTRIBUTES)).float()
    }
    
    losses = loss_fn(output, targets)
    
    print(f"\n💰 損失值:")
    print(f"  - Total Loss: {losses['total_loss'].item():.4f}")
    print(f"  - Category Loss: {losses['category_loss'].item():.4f}")
    print(f"  - Attribute Loss: {losses['attribute_loss'].item():.4f}")
    
    # 計算參數量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"\n📈 模型參數:")
    print(f"  - 總參數量: {total_params:,}")
    print(f"  - 可訓練參數: {trainable_params:,}")
    
    print("\n✅ 模型測試完成!")
