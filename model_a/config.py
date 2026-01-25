"""
Model A 訓練配置檔案
定義所有超參數、路徑和訓練設定
"""

import os
from pathlib import Path

# ==================== 路徑設定 ====================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "Category and Attribute Prediction Benchmark"
ANNO_DIR = DATA_DIR / "Anno_fine"
IMG_DIR = DATA_DIR / "data"

# 輸出目錄
OUTPUT_DIR = BASE_DIR / "output"
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
LOG_DIR = OUTPUT_DIR / "logs"
RESULT_DIR = OUTPUT_DIR / "results"

# 創建輸出目錄
for dir_path in [OUTPUT_DIR, CHECKPOINT_DIR, LOG_DIR, RESULT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# ==================== 資料集設定 ====================
# 類別數量 (50 個服飾類別)
NUM_CATEGORIES = 50

# 屬性數量 (26 個核心屬性)
NUM_ATTRIBUTES = 26

# 屬性名稱 (按照 Anno_fine/list_attr_cloth.txt 的順序)
ATTRIBUTE_NAMES = [
    # Texture (紋理) - Type 1
    'floral', 'graphic', 'striped', 'embroidered', 'pleated', 'solid', 'lattice',
    # Sleeve (袖長) - Type 2
    'long_sleeve', 'short_sleeve', 'sleeveless',
    # Length (長度) - Type 3
    'maxi_length', 'mini_length', 'no_dress',
    # Neckline (領口) - Type 4
    'crew_neckline', 'v_neckline', 'square_neckline', 'no_neckline',
    # Fabric (材質) - Type 5
    'denim', 'chiffon', 'cotton', 'leather', 'faux', 'knit',
    # Fit (版型) - Type 6
    'tight', 'loose', 'conventional'
]

# 類別名稱 (50 個服飾類別)
CATEGORY_NAMES = [
    # Upper-body (上身) - Type 1
    'Anorak', 'Blazer', 'Blouse', 'Bomber', 'Button-Down', 'Cardigan',
    'Flannel', 'Halter', 'Henley', 'Hoodie', 'Jacket', 'Jersey',
    'Parka', 'Peacoat', 'Poncho', 'Sweater', 'Tank', 'Tee', 'Top', 'Turtleneck',
    # Lower-body (下身) - Type 2
    'Capris', 'Chinos', 'Culottes', 'Cutoffs', 'Gauchos', 'Jeans',
    'Jeggings', 'Jodhpurs', 'Joggers', 'Leggings', 'Sarong', 'Shorts',
    'Skirt', 'Sweatpants', 'Sweatshorts', 'Trunks',
    # Full-body (全身) - Type 3
    'Caftan', 'Cape', 'Coat', 'Coverup', 'Dress', 'Jumpsuit',
    'Kaftan', 'Kimono', 'Nightdress', 'Onesie', 'Robe', 'Romper',
    'Shirtdress', 'Sundress'
]

# ==================== 模型設定 ====================
# 使用的預訓練模型 (可選: 'resnet50', 'efficientnet_b0', 'mobilenet_v3_large')
BACKBONE = 'efficientnet_b0'

# 圖片尺寸
IMG_SIZE = 224

# Embedding 維度
EMBEDDING_DIM = 512

# ==================== 訓練設定 ====================
# 訓練參數
BATCH_SIZE = 32
NUM_EPOCHS = 50
LEARNING_RATE = 1e-4
WEIGHT_DECAY = 1e-5

# 學習率調度器
LR_SCHEDULER = 'cosine'  # 'step', 'cosine', 'plateau'
LR_STEP_SIZE = 10
LR_GAMMA = 0.1

# Early Stopping
EARLY_STOPPING_PATIENCE = 10

# ==================== 損失函數權重 ====================
# 多任務學習的損失權重
LOSS_WEIGHTS = {
    'category': 1.0,      # 類別分類損失
    'attribute': 0.5,     # 屬性預測損失
}

# 屬性損失類型 ('bce' 或 'focal')
ATTRIBUTE_LOSS_TYPE = 'bce'  # Binary Cross Entropy

# Focal Loss 參數 (如果使用)
FOCAL_ALPHA = 0.25
FOCAL_GAMMA = 2.0

# ==================== 資料增強設定 ====================
# 訓練時的資料增強
TRAIN_AUGMENTATION = True
AUGMENTATION_PARAMS = {
    'horizontal_flip': 0.5,
    'rotation': 15,
    'color_jitter': {
        'brightness': 0.2,
        'contrast': 0.2,
        'saturation': 0.2,
        'hue': 0.1
    },
    'random_erasing': 0.3,
}

# ==================== 其他設定 ====================
# 隨機種子
RANDOM_SEED = 42

# 使用的設備
DEVICE = 'cuda'  # 'cuda' 或 'cpu'

# 多 GPU 訓練
USE_MULTI_GPU = False

# 混合精度訓練
USE_AMP = True

# 梯度累積步數
GRADIENT_ACCUMULATION_STEPS = 1

# 梯度裁剪
GRADIENT_CLIP_VALUE = 1.0

# 保存檢查點的頻率 (每 N 個 epoch)
SAVE_CHECKPOINT_EVERY = 5

# 驗證頻率 (每 N 個 epoch)
VALIDATE_EVERY = 1

# 是否保存最佳模型
SAVE_BEST_MODEL = True

# TensorBoard 日誌
USE_TENSORBOARD = True

# ==================== 評估設定 ====================
# 評估指標
EVAL_METRICS = ['accuracy', 'precision', 'recall', 'f1']

# Top-K 準確率
TOP_K = [1, 3, 5]

# ==================== 推論設定 ====================
# 屬性預測的閾值
ATTRIBUTE_THRESHOLD = 0.5

# 是否使用 TTA (Test Time Augmentation)
USE_TTA = False

# ==================== 顏色提取設定 ====================
# 使用 K-Means 提取主色調
NUM_DOMINANT_COLORS = 3

# ==================== 風格標籤映射 ====================
# 根據屬性組合推斷風格標籤
STYLE_MAPPING = {
    'casual': ['denim', 'cotton', 'loose'],
    'formal': ['tight', 'conventional'],
    'sporty': ['loose', 'cotton'],
    'elegant': ['chiffon', 'tight'],
    'vintage': ['floral', 'pleated'],
}

print(f"✅ 配置載入完成")
print(f"📂 資料目錄: {DATA_DIR}")
print(f"📂 輸出目錄: {OUTPUT_DIR}")
print(f"🎯 類別數量: {NUM_CATEGORIES}")
print(f"🎯 屬性數量: {NUM_ATTRIBUTES}")
print(f"🖼️  圖片尺寸: {IMG_SIZE}x{IMG_SIZE}")
print(f"🔧 Backbone: {BACKBONE}")
