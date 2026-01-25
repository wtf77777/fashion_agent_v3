from typing import List, Dict, Optional
import random
import logging
from database.models import ClothingItem, WeatherData

logger = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self):
        # 顏色規則
        self.NEUTRAL_COLORS = ["黑色", "白色", "灰色", "深藍", "卡其", "米色", "咖啡"]
        
        # 風格相容矩陣
        self.STYLE_MATRIX = {
            "休閒": ["休閒", "運動", "街頭", "極簡", "日系", "韓系", "戶外機能"],
            "正式": ["正式", "商務休閒", "優雅", "極簡"],
            "運動": ["運動", "休閒", "街頭", "戶外機能"],
            "街頭": ["街頭", "休閒", "運動", "復古"],
            "復古": ["復古", "休閒", "日系"],
            "商務休閒": ["商務休閒", "正式", "休閒", "極簡"],
            "戶外機能": ["戶外機能", "運動", "休閒"]
        }

    def recommend(
        self, 
        wardrobe: List[ClothingItem], 
        weather: WeatherData, 
        occasion: str, 
        user_gender: str = "中性",
        target_style: Optional[str] = None,
        force_outer: bool = False # ✅ 新增參數：由 Gemini 判斷是否強制外套
    ) -> List[Dict]:
        """產生推薦穿搭 (Top 3)"""
        
        # 1. 前置過濾
        valid_items = self._pre_filter(wardrobe, weather, occasion, user_gender)
        
        tops = [i for i in valid_items if i.category == "上衣"]
        bottoms = [i for i in valid_items if i.category == "下身"]
        outers = [i for i in valid_items if i.category == "外套"]
        onepieces = [i for i in valid_items if i.category == "連身裝" or "裙" in str(i.name)]
        shoes = [i for i in valid_items if i.category == "鞋子"]
            
        # 判斷是否需要外套
        # 邏輯: 如果環境很冷 (<22度) OR Gemini 說需要 (force_outer)
        need_outer = (weather.temp < 22) or force_outer
        
        candidates = []
        
        # --- 策略 A: 上衣 + 下身 + 鞋子 ---
        if tops and bottoms:
            for _ in range(25):
                t = random.choice(tops)
                b = random.choice(bottoms)
                s = random.choice(shoes) if shoes else None
                
                outfit_items = [t, b]
                if s: outfit_items.append(s)
                
                if need_outer and outers:
                    o = self._find_best_match(t, outers)
                    if o: outfit_items.append(o)
                
                outfit = {"items": outfit_items, "score": 0, "reasons": [], "type": "2-piece"}
                self._score_outfit(outfit, weather, occasion, target_style)
                candidates.append(outfit)

        # --- 策略 B: 連身裝 + 鞋子 ---
        if onepieces and user_gender != "男":
            for _ in range(15):
                o = random.choice(onepieces)
                s = random.choice(shoes) if shoes else None
                outfit_items = [o]
                if s: outfit_items.append(s)
                
                if need_outer and outers:
                    ext_o = self._find_best_match(o, outers)
                    if ext_o: outfit_items.append(ext_o)
                    
                outfit = {"items": outfit_items, "score": 0, "reasons": [], "type": "one-piece"}
                self._score_outfit(outfit, weather, occasion, target_style)
                candidates.append(outfit)
        
        if not candidates: return []

        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        final_list = []
        for c in candidates[:3]:
            final_list.append({
                "items": [item.to_dict() for item in c["items"]],
                "score": c["score"],
                "reasons": c["reasons"],
                "type": c["type"]
            })
        return final_list

    def _pre_filter(self, items: List[ClothingItem], weather: WeatherData, occasion: str, user_gender: str) -> List[ClothingItem]:
        filtered = []
        is_raining = "雨" in str(weather.desc)
        for item in items:
            if user_gender == "男" and "女" in str(item.style): continue
            if user_gender == "女" and "男" in str(item.style): continue
            if weather.temp > 28 and item.warmth > 6: continue
            if weather.temp < 16 and item.warmth < 3: continue
            if is_raining and item.category == "下身" and item.color in ["白色", "淺灰"]: continue
            filtered.append(item)
        return filtered

    def _score_outfit(self, outfit: Dict, weather: WeatherData, occasion: str, target_style: str):
        score = 70
        items = outfit["items"]
        
        # 風格加分
        for item in items:
            if target_style and target_style.lower() in str(item.name).lower() + str(item.style).lower():
                score += 15
                outfit["reasons"].append(f"符合指定風格: {target_style}")
                break
        
        # 顏色配對
        colors = [i.color for i in items]
        if len(set(colors)) <= 2:
            score += 10
            outfit["reasons"].append("色系簡潔")
            
        outfit["score"] = score

    def _find_best_match(self, base_item: ClothingItem, candidates: List[ClothingItem]) -> Optional[ClothingItem]:
        for c in candidates:
            if c.color == base_item.color or c.color in self.NEUTRAL_COLORS:
                return c
        return candidates[0] if candidates else None
