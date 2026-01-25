"""
配置管理模組
統一管理所有配置，支援環境變數和 Streamlit Secrets
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class AppConfig:
    """應用配置類"""
    gemini_api_key: str
    weather_api_key: str
    supabase_url: str
    supabase_key: str
    default_city: str = "Taipei"
    api_rate_limit_seconds: int = 15
    max_batch_upload: int = 10
    weather_cache_hours: int = 1
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """從環境變數載入配置"""
        return cls(
            gemini_api_key=os.getenv("GEMINI_KEY", ""),
            weather_api_key=os.getenv("CWA_API_KEY", "") or os.getenv("WEATHER_KEY", ""),  # 優先使用 CWA Key，相容舊設定
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_key=os.getenv("SUPABASE_KEY", ""),
            default_city=os.getenv("DEFAULT_CITY", "臺北市")  # 改用中文城市名稱
        )
    
    def is_valid(self) -> bool:
        """檢查配置是否完整"""
        return all([
            self.gemini_api_key,
            self.weather_api_key,
            self.supabase_url,
            self.supabase_key
        ])

# 台灣城市資料 - 使用中央氣象署格式
TAIWAN_CITIES = {
    "臺北市": "臺北市",
    "新北市": "新北市",
    "桃園市": "桃園市",
    "臺中市": "臺中市",
    "臺南市": "臺南市",
    "高雄市": "高雄市",
    "基隆市": "基隆市",
    "新竹市": "新竹市",
    "新竹縣": "新竹縣",
    "苗栗縣": "苗栗縣",
    "彰化縣": "彰化縣",
    "南投縣": "南投縣",
    "雲林縣": "雲林縣",
    "嘉義市": "嘉義市",
    "嘉義縣": "嘉義縣",
    "屏東縣": "屏東縣",
    "宜蘭縣": "宜蘭縣",
    "花蓮縣": "花蓮縣",
    "臺東縣": "臺東縣",
    "澎湖縣": "澎湖縣",
    "金門縣": "金門縣",
    "連江縣": "連江縣"  # 馬祖
}

def get_city_display_name(city_name: str) -> str:
    """根據城市名稱獲取顯示名稱"""
    return TAIWAN_CITIES.get(city_name, "臺北市")
# 台灣城市資料
TAIWAN_CITIES = {
    "台北 (Taipei)": "Taipei",
    "新北 (New Taipei)": "New Taipei",
    "桃園 (Taoyuan)": "Taoyuan",
    "台中 (Taichung)": "Taichung",
    "台南 (Tainan)": "Tainan",
    "高雄 (Kaohsiung)": "Kaohsiung",
    "基隆 (Keelung)": "Keelung",
    "新竹 (Hsinchu)": "Hsinchu",
    "苗栗 (Miaoli)": "Miaoli",
    "彰化 (Changhua)": "Changhua",
    "南投 (Nantou)": "Nantou",
    "雲林 (Yunlin)": "Yunlin",
    "嘉義 (Chiayi)": "Chiayi",
    "屏東 (Pingtung)": "Pingtung",
    "宜蘭 (Yilan)": "Yilan",
    "花蓮 (Hualien)": "Hualien",
    "台東 (Taitung)": "Taitung",
    "澎湖 (Penghu)": "Penghu",
    "金門 (Kinmen)": "Kinmen",
    "馬祖 (Matsu)": "Matsu"
}

def get_city_display_name(english_name: str) -> str:
    """根據英文名稱獲取顯示名稱"""
    for display, english in TAIWAN_CITIES.items():
        if english.lower() == english_name.lower():
            return display
    return "台北 (Taipei)"
