"""
AI 服務層
處理所有與 Gemini API 相關的業務邏輯
"""
import json
import time
import google.generativeai as genai
from typing import List, Dict, Optional, Tuple
from database.models import ClothingItem, WeatherData

from google.api_core.exceptions import ResourceExhausted
from api.model_a_adapter import ModelAAdapter
from api.recommendation_engine import RecommendationEngine

class AIService:
    def __init__(self, api_key: str, rate_limit_seconds: int = 15):
        self.api_key = api_key
        self.rate_limit_seconds = rate_limit_seconds
        self.last_request_time = 0
        genai.configure(api_key=api_key)
        # 設定安全過濾 (關閉以避免誤判衣物圖片)
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
        
        # 使用使用者指定的版本 2.5-flash
        self.model = genai.GenerativeModel('gemini-2.5-flash', safety_settings=self.safety_settings)
    
    def _rate_limit_wait(self):
        """API 速率限制保護"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_seconds:
            wait_time = self.rate_limit_seconds - time_since_last
            time.sleep(wait_time)
        
        self.last_request_time = time.time()

    def batch_auto_tag(self, img_bytes_list: List[bytes]) -> Optional[List[Dict]]:
        final_results = [None] * len(img_bytes_list)
        gemini_indices = []
        gemini_img_bytes = []
        
        # 1. 嘗試使用本地 Model A
        print(f"[AI] 開始批次辨識 {len(img_bytes_list)} 張圖片...")
        adapter = ModelAAdapter()
        
        for idx, img_bytes in enumerate(img_bytes_list):
            # 嘗試使用本地模型
            local_result = adapter.analyze_image(img_bytes)
            
            if local_result:
                print(f"[AI] 分部 {idx+1}: Model A 辨識成功 ({local_result['confidence']:.2f})")
                # 轉換為統一格式
                final_results[idx] = {
                    "name": f"{local_result['colors'][0]} {local_result['category_zh']}" if local_result['colors'] else local_result['category_zh'],
                    "category": self._map_category_to_frontend(local_result['category']),
                    "color": local_result['colors'][0] if local_result['colors'] else "未知",
                    "style": local_result['style'][0] if local_result['style'] else "休閒"
                }
            else:
                print(f"[AI] 分部 {idx+1}: Model A 辨識失敗/未啟用，加入 Gemini 隊列")
                gemini_indices.append(idx)
                gemini_img_bytes.append(img_bytes)
        
        # 如果所有圖片都已由 Model A 處理完成，直接返回
        if not gemini_indices:
            print("[AI] ✅ 全部由本地 Model A 完成辨識")
            return final_results

        # 2. 剩餘圖片使用 Gemini API (Fallback)
        try:
            print(f"[AI] 轉送 {len(gemini_img_bytes)} 張圖片給 Gemini API...")
            self._rate_limit_wait()
            
            prompt = f"""請仔細分析這 {len(gemini_img_bytes)} 件衣服,為每件衣服分別回傳 JSON 格式的標籤。
 
回傳格式必須是一個 JSON 陣列,包含 {len(gemini_img_bytes)} 個物件:
[
  {{
    "name": "衣服名稱(如:白色T恤、牛仔褲)",
    "category": "上衣|下身|外套|鞋子|配件",
    "color": "主要顏色",
    "style": "風格(如:休閒、正式、運動)"
  }},
  ... (依序對應每張圖片)
]
 
重要規則:
1. 只回傳 JSON 陣列,不要任何其他文字
2. 不要包含 ```json 或任何 Markdown 標籤
3. 陣列中的順序必須與圖片順序一致
4. 每個物件都必須包含這 4 個欄位
"""
            
            content_parts = [prompt]
            for idx, img_bytes in enumerate(gemini_img_bytes):
                content_parts.append({
                    "mime_type": "image/jpeg",
                    "data": img_bytes
                })
            
            print(f"[AI] 發送請求到 Gemini API...")
            
            max_retries = 3
            retry_count = 0
            response = None
            
            while retry_count < max_retries:
                try:
                    response = self.model.generate_content(content_parts)
                    break
                except ResourceExhausted as e:
                    retry_count += 1
                    wait_time = 30 * retry_count
                    print(f"[AI] ⚠️ 觸發速率限制 (429)，等待 {wait_time} 秒後重試 ({retry_count}/{max_retries})...")
                    time.sleep(wait_time)
                    if retry_count == max_retries:
                        raise e
            
            print(f"[AI] 收到 API 回應")
            
            try:
                raw_text = response.text
            except ValueError:
                if response.candidates and response.candidates[0].content.parts:
                    raw_text = response.candidates[0].content.parts[0].text
                else:
                    raise ValueError("AI 回應為空，無法解析")
            
            clean_text = raw_text.strip()
            clean_text = clean_text.replace('```json', '').replace('```', '').strip()
            
            gemini_tags_list = json.loads(clean_text)
            
            if not isinstance(gemini_tags_list, list):
                raise ValueError("AI 回傳格式錯誤: 應為陣列")
            
            if len(gemini_tags_list) != len(gemini_img_bytes):
                raise ValueError(f"AI 回傳數量不符: 預期 {len(gemini_img_bytes)} 件,實際 {len(gemini_tags_list)} 件")
            
            # 將 Gemini 結果填回對應位置
            for i, tags in enumerate(gemini_tags_list):
                original_idx = gemini_indices[i]
                final_results[original_idx] = tags
            
            print(f"[AI] ✅ 混合辨識完成 (Model A: {len(img_bytes_list)-len(gemini_indices)}, Gemini: {len(gemini_indices)})")
            return final_results
            
        except Exception as e:
            print(f"[AI] ❌ Gemini 辨識失敗: {str(e)}")
            # 如果 Gemini 失敗，至少回傳 Model A 成功的部份 (失敗的部分用 None 或預設值)
            # 這裡簡單處理：只要有部分失敗就算全部失敗 (前端可能會重試)
            # 或者我們可以回傳部分結果
            return None

    def _map_category_to_frontend(self, model_cat: str) -> str:
        """將 Model A 的類別對應到前端 (上衣|下身|外套|鞋子|配件)"""
        # 簡單映射邏輯
        UPPER = ['Tee', 'Blouse', 'Top', 'Tank', 'Jersey', 'Hoodie', 'Sweater']
        LOWER = ['Jeans', 'Shorts', 'Skirt', 'Sweatpants', 'Joggers', 'Leggings', 'Chinos']
        OUTER = ['Jacket', 'Coat', 'Blazer', 'Cardigan', 'Parka', 'Kimono']
        FULL = ['Dress', 'Jumpsuit', 'Romper']
        
        if model_cat in UPPER: return "上衣"
        if model_cat in LOWER: return "下身"
        if model_cat in OUTER: return "外套"
        if model_cat in FULL: return "上衣" # 或連身裝，視前端需求
        return "配件" # 預設
    
    def generate_outfit_recommendation(
        self, 
        wardrobe: List[ClothingItem],
        weather: WeatherData,
        style: str,
        occasion: str
    ) -> Optional[Dict]:
        """產出智能推薦穿搭組合"""
        try:
            # 1. 使用 Gemini 解析精細場景 (例如：去電影院約會 -> 需要帶外套、浪漫休閒)
            analysis_prompt = f"""
            使用者描述："{occasion}｜風格偏好：{style}"
            
            請根據以上內容解析場景意圖。
            回傳格式必須是 JSON，包含：
            {{
                "normalized_occasion": "約會|日常|運動|上班|正式",
                "needs_outer": true/false (是否因為場合如電影院、冷氣房或溫差需要外套),
                "vibe_description": "一段約 30 字的專業穿搭顧問開場白",
                "parsed_style": "從描述中提取出的核心風格關鍵字(例如：英倫, 街頭, 低調)"
            }}
            """
            
            response = self.model.generate_content(analysis_prompt)
            try:
                # 簡單清理並加載 JSON
                clean_json = response.text.strip().replace('```json','').replace('```','')
                analysis = json.loads(clean_json)
            except:
                analysis = {
                    "normalized_occasion": "日常", 
                    "needs_outer": False, 
                    "vibe_description": "為您挑選了幾套合適的穿搭方案。",
                    "parsed_style": style
                }
                
            # 2. 呼叫引擎從衣櫥挑選衣服 (對接參數)
            engine = RecommendationEngine()
            outfits = engine.recommend(
                wardrobe=wardrobe,
                weather=weather,
                occasion=analysis["normalized_occasion"],
                target_style=analysis["parsed_style"],
                force_outer=analysis["needs_outer"]  # ✅ 將 Gemini 建議傳給引擎
            )
            
            if not outfits:
                return None
                
            return {
                "vibe": analysis["vibe_description"],
                "recommendations": outfits
            }

        except Exception as e:
            print(f"AI 推薦失敗: {str(e)}")
            return None
    
    def parse_recommended_items(
        self, 
        ai_response: str, 
        wardrobe: List[ClothingItem]
    ) -> List[ClothingItem]:
        """解析 AI 推薦文字,提取推薦的衣物 ID"""
        recommended_items = []
        response_lower = ai_response.lower()
        
        for item in wardrobe:
            item_name = item.name.lower()
            item_category = item.category.lower()
            item_color = item.color.lower()
            
            if (item_name and item_name in response_lower) or \
               (item_color and item_category and f"{item_color}{item_category}" in response_lower.replace(' ', '')):
                recommended_items.append(item)
        
        return recommended_items
