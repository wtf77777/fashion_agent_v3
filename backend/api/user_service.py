"""
使用者服務層
處理個人資料、設定和歷史紀錄相關的業務邏輯
"""
from typing import List, Tuple, Optional, Dict
from datetime import datetime
from database.models import User
from database.supabase_client import SupabaseClient
import json


class UserService:
    def __init__(self, supabase_client: SupabaseClient):
        self.db = supabase_client
    
    # ========== 個人資料管理 ==========
    
    def get_profile(self, user_id: str) -> Optional[Dict]:
        """
        獲取使用者個人資料
        
        Returns:
            dict: {
                "gender": "male/female/other",
                "height": "170",
                "weight": "65",
                "favorite_styles": ["Japanese Cityboy", "Korean Chic"],
                "dislikes": "短褲, 涼鞋",
                "thermal_preference": "cold_sensitive/normal/heat_sensitive",
                "custom_style_desc": "喜歡寬鬆簡約"
            }
        """
        try:
            result = self.db.client.table("users")\
                .select(
                    "gender, height, weight, favorite_styles, dislikes, "
                    "thermal_preference, custom_style_desc"
                )\
                .eq("id", user_id)\
                .execute()
            
            if result.data:
                profile = result.data[0]
                # 確保 favorite_styles 是列表
                if profile.get('favorite_styles') is None:
                    profile['favorite_styles'] = []
                elif isinstance(profile['favorite_styles'], str):
                    try:
                        profile['favorite_styles'] = json.loads(profile['favorite_styles'])
                    except:
                        profile['favorite_styles'] = []
                
                return profile
            return None
        except Exception as e:
            print(f"[ERROR] 獲取個人資料失敗: {str(e)}")
            return None
    
    def update_profile(self, user_id: str, profile_data: Dict) -> Tuple[bool, str]:
        """
        更新使用者個人資料
        
        Args:
            user_id: 使用者 ID
            profile_data: {
                "gender": "male/female/other",
                "height": "170",
                "weight": "65",
                "favorite_styles": ["Japanese Cityboy", "Korean Chic"],
                "dislikes": "短褲, 涼鞋",
                "thermal_preference": "cold_sensitive",
                "custom_style_desc": "喜歡寬鬆簡約"
            }
        
        Returns:
            (是否成功, 訊息)
        """
        try:
            # 確保 favorite_styles 是有效的 JSON
            if 'favorite_styles' in profile_data:
                if isinstance(profile_data['favorite_styles'], list):
                    profile_data['favorite_styles'] = json.dumps(profile_data['favorite_styles'])
            
            # 驗證 thermal_preference 值
            if 'thermal_preference' in profile_data:
                valid_values = ['cold_sensitive', 'normal', 'heat_sensitive']
                if profile_data['thermal_preference'] not in valid_values:
                    return False, f"體感偏好值無效: {profile_data['thermal_preference']}"
            
            # ✅ 修復問題 4: 先檢查記錄是否存在
            check_result = self.db.client.table("users")\
                .select("id")\
                .eq("id", user_id)\
                .execute()
            
            if not check_result.data:
                # 記錄不存在，需要先建立（應該在註冊時自動建立，但作為防衛措施）
                print(f"[WARN] 用戶記錄不存在，建立新記錄: {user_id}")
                init_data = {"id": user_id}
                init_data.update(profile_data)
                result = self.db.client.table("users")\
                    .insert(init_data)\
                    .execute()
            else:
                # 記錄存在，進行更新
                result = self.db.client.table("users")\
                    .update(profile_data)\
                    .eq("id", user_id)\
                    .execute()
            
            if result.data:
                return True, "個人資料已更新"
            return False, "更新失敗"
        except Exception as e:
            print(f"[ERROR] 更新個人資料失敗: {str(e)}")
            return False, str(e)
    
    # ========== 推薦歷史紀錄管理 ==========
    
    def get_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """
        獲取使用者的推薦歷史紀錄
        
        Args:
            user_id: 使用者 ID
            limit: 最多返回多少筆
        
        Returns:
            list: [
                {
                    "id": 1,
                    "city": "臺北市",
                    "occasion": "約會",
                    "style": "日系簡約",
                    "recommendation_data": {...},
                    "created_at": "2026-02-04T12:00:00Z"
                },
                ...
            ]
        """
        try:
            result = self.db.client.table("recommendation_history")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data if result.data else []
        except Exception as e:
            print(f"[ERROR] 獲取歷史紀錄失敗: {str(e)}")
            return []
    
    def save_history(
        self, 
        user_id: str, 
        city: str, 
        occasion: str, 
        style: str,
        recommendation_data: Dict
    ) -> Tuple[bool, str]:
        """
        儲存推薦歷史紀錄
        
        Args:
            user_id: 使用者 ID
            city: 城市
            occasion: 場合 (如: 約會、上班、運動)
            style: 風格偏好 (如: 日系、韓系)
            recommendation_data: 完整推薦結果 (包含 vibe 和 recommendations)
        
        Returns:
            (是否成功, 訊息)
        """
        try:
            data = {
                "user_id": user_id,
                "city": city,
                "occasion": occasion,
                "style": style,
                "recommendation_data": recommendation_data,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            
            result = self.db.client.table("recommendation_history")\
                .insert(data)\
                .execute()
            
            if result.data:
                return True, "歷史紀錄已儲存"
            return False, "儲存失敗"
        except Exception as e:
            print(f"[ERROR] 儲存歷史紀錄失敗: {str(e)}")
            return False, str(e)
    
    def delete_history(self, user_id: str, history_id: int) -> Tuple[bool, str]:
        """
        刪除單筆歷史紀錄
        
        Args:
            user_id: 使用者 ID
            history_id: 歷史紀錄 ID
        
        Returns:
            (是否成功, 訊息)
        """
        try:
            result = self.db.client.table("recommendation_history")\
                .delete()\
                .eq("id", history_id)\
                .eq("user_id", user_id)\
                .execute()
            
            return True, "歷史紀錄已刪除"
        except Exception as e:
            print(f"[ERROR] 刪除歷史紀錄失敗: {str(e)}")
            return False, str(e)
