from typing import List, Dict, Optional
import random
import logging
from database.models import ClothingItem, WeatherData

logger = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self):
        self.NEUTRAL_COLORS = ["黑色", "白色", "灰色", "深藍", "卡其", "米色", "咖啡"]
        
    def recommend(
        self, wardrobe: List[ClothingItem], weather: WeatherData, occasion: str, 
        user_gender: str = "中性", target_style: Optional[str] = None, force_outer: bool = False
    ) -> List[Dict]:
        """核心推薦 - 防止長袖配短褲版"""
        valid_items = self._pre_filter(wardrobe, weather, occasion, user_gender)
        
        tops = [i for i in valid_items if i.category == "上衣"]
        bottoms = [i for i in valid_items if i.category == "下身"]
        outers = [i for i in valid_items if i.category == "外套"]
        shoes = [i for i in valid_items if i.category == "鞋子"]
            
        need_outer = (weather.temp < 22) or force_outer
        candidates = []
        
        # 配對邏輯
        if tops and bottoms:
            for _ in range(50): # 增加嘗試次數
                t = random.choice(tops)
                b = random.choice(bottoms)
                s = random.choice(shoes) if shoes else None
                
                # ✅ 關鍵平衡規則：防止長袖配短褲
                # 長袖/厚重 (warmth > 6), 短褲/輕薄 (warmth < 4)
                if t.warmth > 6 and b.warmth < 4: continue 
                # 反之亦然
                if b.warmth > 7 and t.warmth < 3: continue 
                
                outfit_items = [t, b]
                if s: outfit_items.append(s)
                if need_outer and outers:
                    o = self._find_best_match(t, outers)
                    if o: outfit_items.append(o)
                
                outfit = {"items": outfit_items, "score": 0, "reasons": [], "type": "2-piece"}
                self._score_outfit(outfit, weather, target_style)
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
        for item in items:
            if weather.temp > 28 and item.warmth > 6: continue
            if weather.temp < 15 and item.warmth < 3: continue
            filtered.append(item)
        return filtered

    def _score_outfit(self, outfit: Dict, weather: WeatherData, target_style: str):
        score = 70
        items = outfit["items"]
        
        # 簡單評分 logic
        colors = [i.color for i in items]
        if len(set(colors)) <= 2: score += 10
        
        if target_style:
            for item in items:
                if target_style.lower() in str(item.name).lower():
                    score += 15; break
            
        outfit["score"] = score

    def _find_best_match(self, base_item: ClothingItem, candidates: List[ClothingItem]) -> Optional[ClothingItem]:
        for c in candidates:
            if c.color == base_item.color or c.color in self.NEUTRAL_COLORS:
                return c
        return candidates[0] if candidates else None
