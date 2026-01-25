"""
衣櫥服務層
處理衣櫥管理相關的業務邏輯
"""
import base64
import hashlib
from typing import List, Tuple, Optional
from datetime import datetime
from database.models import ClothingItem
from database.supabase_client import SupabaseClient

class WardrobeService:
    def __init__(self, supabase_client: SupabaseClient):
        self.db = supabase_client
    
    @staticmethod
    def get_image_hash(img_bytes: bytes) -> str:
        """計算圖片的 SHA256 hash 值"""
        return hashlib.sha256(img_bytes).hexdigest()
    
    def check_duplicate_image(self, user_id: str, img_hash: str) -> Tuple[bool, Optional[str]]:
        """
        檢查圖片是否已存在
        
        Returns:
            (是否重複, 已存在的衣物名稱)
        """
        try:
            result = self.db.client.table("my_wardrobe")\
                .select("id, name")\
                .eq("user_id", user_id)\
                .eq("image_hash", img_hash)\
                .execute()
            
            if result.data:
                return True, result.data[0]['name']
            return False, None
        except Exception as e:
            print(f"檢查重複失敗: {str(e)}")
            return False, None
    
    def save_item(self, item: ClothingItem, img_bytes: bytes) -> Tuple[bool, str]:
        """
        儲存衣物到資料庫
        
        Args:
            item: 衣物資料模型
            img_bytes: 圖片 bytes
            
        Returns:
            (是否成功, 結果訊息)
        """
        try:
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            img_hash = self.get_image_hash(img_bytes)
            
            item.image_data = img_base64
            item.image_hash = img_hash
            item.created_at = datetime.now()
            
            data = item.to_dict()
            result = self.db.client.table("my_wardrobe").insert(data).execute()
            
            return True, "儲存成功"
        except Exception as e:
            return False, str(e)
    
    def get_wardrobe(self, user_id: str) -> List[ClothingItem]:
        """獲取使用者的衣櫥"""
        try:
            response = self.db.client.table("my_wardrobe")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .execute()
            
            return [ClothingItem.from_dict(item) for item in response.data]
        except Exception as e:
            print(f"讀取衣櫥失敗: {str(e)}")
            return []
    
    def update_item(self, user_id: str, item_id: int, data: dict) -> bool:
        """更新衣物資訊"""
        try:
            # Ensure 'updated_at' is set for updates
            if 'updated_at' not in data:
                data['updated_at'] = datetime.now().isoformat()
            
            result = self.db.client.table("my_wardrobe")\
                .update(data)\
                .eq("id", item_id)\
                .eq("user_id", user_id)\
                .execute()
            return len(result.data) > 0
        except Exception as e:
            print(f"資料庫更新失敗: {str(e)}")
            return False

    def delete_item(self, user_id: str, item_id: int) -> bool:
        """刪除單件衣物"""
        try:
            self.db.client.table("my_wardrobe")\
                .delete()\
                .eq("id", item_id)\
                .eq("user_id", user_id)\
                .execute()
            return True
        except Exception as e:
            print(f"刪除失敗: {str(e)}")
            return False
    
    def batch_delete_items(self, user_id: str, item_ids: List[int]) -> Tuple[bool, int, int]:
        """批次刪除衣物"""
        if not item_ids:
            return False, 0, 0
            
        try:
            success_count = 0
            fail_count = 0
            
            for item_id in item_ids:
                try:
                    self.db.client.table("my_wardrobe")\
                        .delete()\
                        .eq("id", item_id)\
                        .eq("user_id", user_id)\
                        .execute()
                    success_count += 1
                except:
                    fail_count += 1
            
            return True, success_count, fail_count
        except Exception as e:
            print(f"批次刪除失敗: {str(e)}")
            return False, 0, 0
    
    def get_category_statistics(self, user_id: str) -> dict:
        """獲取衣櫥分類統計"""
        items = self.get_wardrobe(user_id)
        
        categories = {}
        for item in items:
            cat = item.category or "其他"
            categories[cat] = categories.get(cat, 0) + 1
        
        return categories
