from dataclasses import dataclass
from typing import Optional
from datetime import datetime
@dataclass
class WeatherData:
    """天氣資料模型"""
    temp: float
    feels_like: float
    desc: str
    city: str
    update_time: datetime
    
    def to_dict(self) -> dict:
        return {
            "temp": round(self.temp, 1),
            "feels_like": round(self.feels_like, 1),
            "desc": self.desc,
            "city": self.city
        }
@dataclass
class ClothingItem:
    """衣物模型"""
    id: Optional[int] = None
    user_id: str = ""  # ✅ UUID 字串
    name: str = ""
    category: str = ""
    color: str = ""
    style: str = ""
    warmth: int = 5
    image_data: Optional[str] = None
    image_hash: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """
        轉換為字典
        注意: 當 id 為 None 時不包含在字典中,讓 Supabase 自動生成
        """
        data = {
            "user_id": self.user_id,
            "name": self.name,
            "category": self.category,
            "color": self.color,
            "style": self.style,
            "warmth": self.warmth,
            "image_data": self.image_data,
            "image_hash": self.image_hash,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        
        # 只有當 id 不為 None 時才包含(用於更新操作)
        if self.id is not None:
            data["id"] = self.id
        
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ClothingItem':
        return cls(
            id=data.get("id"),
            user_id=str(data.get("user_id", "")),  # ✅ 確保是字串
            name=data.get("name", ""),
            category=data.get("category", ""),
            color=data.get("color", ""),
            style=data.get("style", ""),
            warmth=data.get("warmth", 5),
            image_data=data.get("image_data"),
            image_hash=data.get("image_hash"),
            image_url=data.get("image_url"),
            created_at=cls._parse_datetime(data.get("created_at"))
        )

    @staticmethod
    def _parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            # 處理 Z 結尾 (UTC)
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            return datetime.fromisoformat(date_str)
        except ValueError:
            # 如果 Python版本過舊不支援某些格式，嘗試簡單處理
            try:
                # 嘗試去掉小數點後的秒數
                if '.' in date_str:
                    date_str = date_str.split('.')[0] + '+00:00'
                return datetime.fromisoformat(date_str)
            except:
                return None

@dataclass
class User:
    """用戶模型"""
    id: str = ""  # ✅ UUID 字串
    username: str = ""
    password: str = ""
    created_at: Optional[datetime] = None
