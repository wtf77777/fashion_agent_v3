"""
AI 服務層 - Oreoooooo 終極穩定整合版
處理所有與 Gemini API 相關的業務邏輯，包含重試機制、高品質 Prompt 與階梯式辨識
"""
import json
import time
import re
import google.generativeai as genai
from typing import List, Dict, Optional, Tuple, Tuple
from database.models import ClothingItem, WeatherData

from google.api_core.exceptions import ResourceExhausted, InternalServerError
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
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
        
        # 依照 Oreoooooo 要求，定義階梯模型 (Tier 1 & Tier 2)
        # 注意: 確保系統環境支援此模型名稱
        self.model_t1 = genai.GenerativeModel('gemini-2.5-flash', safety_settings=self.safety_settings)
        self.model_t2 = genai.GenerativeModel('gemini-3-flash-preview', safety_settings=self.safety_settings)
    
    def _rate_limit_wait(self):
        """API 速率限制保護 - 嚴格版"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_seconds:
            wait_time = self.rate_limit_seconds - time_since_last
            print(f"[AI] ⏳ 速率限制保護中，等待 {wait_time:.1f} 秒...")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()

    def batch_auto_tag(self, img_bytes_list: List[bytes]) -> Optional[List[Dict]]:
        """
        Oreoooooo 階梯式自動標籤辨識:
        1. 先嘗試 Gemini 2.5-flash (具備重試)
        2. 若爆流量則試 Gemini 3-flash-preview (具備重試)
        3. 均失敗則 Fallback 到本地 Model A
        """
        print(f"[AI] 開始對 {len(img_bytes_list)} 件衣物進行階梯式辨識分析...")
        
        # A. 嘗試模型 1 (2.5-flash)
        results = self._call_gemini_with_robust_logic(self.model_t1, img_bytes_list, "Tier 1 (2.5-flash)")
        if results: return results
        
        # B. 嘗試模型 2 (3-preview)
        results = self._call_gemini_with_robust_logic(self.model_t2, img_bytes_list, "Tier 2 (3-preview)")
        if results: return results

        # C. 最終 Fallback - 本地 Model A (當 API 均不可用時)
        print("[AI] ⚠️ 所有 Gemini 模型均已達流量上限或失敗，啟動本地 Model A 辨識...")
        adapter = ModelAAdapter()
        final_results = []
        for idx, img_bytes in enumerate(img_bytes_list):
            local_result = adapter.analyze_image(img_bytes)
            if local_result:
                final_results.append({
                    "name": f"{local_result['colors'][0]} {local_result['category_zh']}" if local_result['colors'] else local_result['category_zh'],
                    "category": self._map_category_to_frontend(local_result['category']),
                    "color": local_result['colors'][0] if local_result['colors'] else "未知",
                    "style": local_result['style'][0] if local_result['style'] else "休閒"
                })
            else:
                final_results.append({"name": f"未知衣物 {idx+1}", "category": "上衣", "color": "未知", "style": "休閒"})
        
        print(f"[AI] ✅ 回歸本地 Model A辨識完成 ({len(final_results)} 件)")
        return final_results

    def _call_gemini_with_robust_logic(self, model, img_bytes_list, label) -> Optional[List[Dict]]:
        """原本最穩健的呼叫邏輯 (包含 Retry, JSON 清洗, Candidates 檢查)"""
        try:
            self._rate_limit_wait()
            print(f"[AI] 🚀 正在嘗試 {label}...")

            prompt = f"""

---

## 1) 衣物特徵自動標註（batch_auto_tag）

【用途】
用於多張衣服圖片的標籤產生。

【輸出限制】
- 僅允許輸出「純 JSON 陣列」
- 陣列長度必須等於圖片數
- 不得輸出任何 Markdown 或說明文字

【指令】
請仔細分析這 {len(img_bytes_list)} 件衣服圖片，逐件回傳 JSON：

[
  {{
    "name": "顏色+品項（盡量具體，例如：黑色短版飛行外套）",
    "category": "上衣|下身|外套|全身",
    "color": "主要顏色（單一）",
    "style": "以下 15 種其一（無法判斷填 Unknown）",

    "pattern": "solid|striped|checked|printed|logo|graphic|other|unknown",
    "material": "cotton|denim|wool|knit|leather|nylon|polyester|linen|fleece|other|unknown",
    "fit": "slim|regular|oversized|cropped|longline|unknown",
    "thickness": "thin|medium|thick|unknown",
    "season": "spring|summer|autumn|winter|all|unknown",
    "formality": 1,
    "notes": "≤20字，辨識到的設計亮點（如：領型、袖長、口袋、機能、光澤等）"
  }},
  ...
]

【風格列表 15】
1. Minimalist(極簡)
2. Japanese Cityboy(日系寬鬆)
3. Korean Chic(韓系)
4. American Vintage(美式復古)
5. Streetwear(街頭潮流)
6. Formal(正裝/商務)
7. Athleisure(運動休閒)
8. French Chic(法式慵懶)
9. Y2K(千禧復古)
10. Old Money(老錢風)
11. Bohemian(波西米亞)
12. Grunge / Punk(暗黑搖滾)
13. Techwear(機能)
14. Coquette(甜美少女)
15. Gorpcore(山系戶外)

【規則】
- 每件必填：name / category / color / style
- style 必須從清單擇一；不確定填 Unknown
- formality：1=非常休閒、3=日常可通勤、5=正式場合
- 不可捏造品牌或看不到的細節；不清楚一律填 unknown
請僅輸出上述格式的純 JSON 陣列，不要包含 Markdown、說明或額外文字。
"""
            content_parts = [{"mime_type": "image/jpeg", "data": img} for img in img_bytes_list]
            content_parts.insert(0, prompt)

            max_retries = 3
            retry_count = 0
            while retry_count < max_retries:
                try:
                    response = model.generate_content(content_parts)
                    return self._parse_and_validate_response(response, len(img_bytes_list))
                except ResourceExhausted:
                    retry_count += 1
                    wait_time = 30 * retry_count
                    print(f"[AI] ⚠️ {label} 速率限制，等待 {wait_time} 秒後重試 ({retry_count}/{max_retries})...")
                    time.sleep(wait_time)
                except Exception as e:
                    print(f"[AI] {label} 呼叫異常: {e}")
                    break
            return None
        except Exception as e:
            print(f"[AI] {label} 區塊執行失敗: {e}")
            return None

    def _parse_and_validate_response(self, response, count):
        """原本代碼中最完整的解析邏輯"""
        try:
            # 檢查是否存在 content
            try:
                raw_text = response.text
            except ValueError:
                if response.candidates and response.candidates[0].content.parts:
                    raw_text = response.candidates[0].content.parts[0].text
                else:
                    return None
            
            clean_text = raw_text.strip().replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_text)
            
            if isinstance(data, list) and len(data) == count:
                return data
            return None
        except:
            return None

    def _extract_response_text(self, response) -> str:
        """安全取得 Gemini 回傳文字內容"""
        if response is None:
            return ""

        try:
            raw_text = response.text
            if raw_text:
                return str(raw_text)
        except ValueError:
            pass
        except Exception:
            pass

        try:
            if response.candidates and response.candidates[0].content.parts:
                return str(response.candidates[0].content.parts[0].text or "")
        except Exception:
            return ""

        return ""

    def _safe_json_loads(self, text: str):
        """嘗試解析 JSON，失敗時再抽取最可能的 JSON 區塊"""
        if not text:
            return None

        cleaned = text.strip().replace('```json', '').replace('```', '').strip()
        if not cleaned:
            return None

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 嘗試抓出第一段 JSON 物件或陣列
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', cleaned)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                return None

        return None

    def generate_outfit_recommendation(
        self, wardrobe: List[ClothingItem], weather: WeatherData, style: str, occasion: str,
        user_profile: Optional[Dict] = None,
        locked_items: Optional[List[str]] = None  # ✅ 優先級 3：指定單品鎖定
    ) -> Optional[Dict]:
        """產出智能穿搭組合 - 含完整解析與 Gemini 結語、支援個人偏好 & 指定單品"""
        try:
            self._rate_limit_wait()

            locked_item_ids = list(locked_items) if locked_items else []
            locked_item_ids_set = set(locked_item_ids)
            locked_item_ids_str = set(str(x) for x in locked_item_ids)

            def is_locked(item_id) -> bool:
                return item_id in locked_item_ids_set or str(item_id) in locked_item_ids_str
            
            # ✅ 解析個人資料
            dislikes = ""
            thermal_preference = "normal"
            custom_desc = ""
            
            if user_profile:
                dislikes = user_profile.get("dislikes", "") or ""
                thermal_preference = user_profile.get("thermal_preference", "normal") or "normal"
                custom_desc = user_profile.get("custom_style_desc", "") or ""
            
            # 1. 意圖解析 - 增強提示詞融入個人資料
            user_height = user_profile.get("height") if user_profile else None
            user_weight = user_profile.get("weight") if user_profile else None
            user_gender = user_profile.get("gender") if user_profile else "中性"
            favorite_styles = user_profile.get("favorite_styles", []) if user_profile else []
            
            # ✅ 處理 None 值
            user_height_str = f"{user_height} cm" if user_height else "未設定"
            user_weight_str = f"{user_weight} kg" if user_weight else "未設定"
            favorite_styles_str = "、".join(favorite_styles) if favorite_styles else "無特殊偏好"
            
            # ✅ 優先級 3：處理指定單品
            locked_item_details = ""
            if locked_items:
                locked_wardrobe = [item for item in wardrobe if is_locked(item.id)]
                if locked_wardrobe:
                    locked_desc = "、".join([f"{item.name}({item.color})" for item in locked_wardrobe])
                    locked_item_details = f"\n【指定今日單品】必須包含: {locked_desc}"
            
            analysis_prompt = f"""
【使用者資料】
性別/身形: {user_gender} / {user_height_str} / {user_weight_str}
習慣風格: {favorite_styles_str}
體感偏好：{thermal_preference} (若為'cold_sensitive'請增加保暖度權重)
避雷清單：{dislikes if dislikes else '無'}
自訂備註：{custom_desc if custom_desc else '無'}{locked_item_details}

【本次需求】
場合："{occasion}"
風格偏好：{style}
天氣：{weather.temp}度 ({weather.desc})

---
## 2) 穿搭推薦情境分析（analysis_prompt）

【輸入變數】
- user_gender（male / female / other）
- user_height, user_weight
- favorite_styles（陣列）
- thermal_preference（cold_sensitive / normal / heat_sensitive）
- dislikes（字串，逗號分隔）
- custom_desc
- locked_items
- occasion
- occasion（可多選）：
  見客 / 拍照 / 久走 / 久坐冷氣房 / 旅行移動 / 親子 / 夜晚外出 / 戶外曝曬
- style（若有）
- weather.temp
- weather.desc

【指令】
你是穿搭情境分析器，請根據使用者條件、場合、外出目的、風格偏好與天氣，回傳「單一 JSON」。

輸出格式：
{{
  "normalized_occasion": "休閒|通勤|約會|正式|運動|戶外",
  "needs_outer": true/false,
  "vibe_description": "≤30 字，整體氛圍描述",
  "parsed_style": "標準化後的風格名稱"
}}

【判斷規則】

1) normalized_occasion：
- 上班/通勤/開會 → 通勤
- 約會/聚餐/看展/拍照 → 約會
- 婚禮/面試/典禮 → 正式
- 運動相關 → 運動
- 登山/露營/長時間戶外 → 戶外
- 其他 → 休閒

2) parsed_style：
- 若 style 有提供，以 style 為主
- 否則從 favorite_styles 中選 1 個最接近主風格
- 只選 1 個，其餘風格以 vibe_description 補充

3) needs_outer：
- temp ≤ 18 → 通常 true
- 19–24：
  - cold_sensitive → true
  - normal → 視 weather.desc + occasion
  - heat_sensitive → 通常 false
- temp ≥ 25 → 通常 false
- 若下雨 / 有風 / 夜晚外出 / 久坐冷氣房 → needs_outer 傾向 true

4) occasion 影響：
- 拍照 → 層次感、比例、配件
- 久走 / 旅行 → 舒適、活動性
- 見客 / 夜晚 → 俐落、精神感
- 戶外曝曬 → 透氣、防曬

只輸出 JSON，不要任何說明。
"""
            res = self.model_t1.generate_content(analysis_prompt)
            analysis_text = self._extract_response_text(res)
            analysis = self._safe_json_loads(analysis_text)

            if not isinstance(analysis, dict):
                print("[AI] ⚠️ 場景解析回傳非 JSON，改用預設解析值")
                analysis = {
                    "normalized_occasion": "日常",
                    "needs_outer": weather.temp < 22,
                    "vibe_description": "今天就走舒適俐落的日常穿搭風格。",
                    "parsed_style": style or "日常"
                }

            # ✅ 根據體感偏好調整保暖需求
            needs_outer = bool(analysis.get("needs_outer", weather.temp < 22))
            if thermal_preference == "cold_sensitive" and weather.temp < 24:
                needs_outer = True  # 強制加外套
            elif thermal_preference == "heat_sensitive" and weather.temp > 25:
                needs_outer = False  # 儘量不穿外套

            normalized_occasion = analysis.get("normalized_occasion") or "日常"
            parsed_style = analysis.get("parsed_style") or style or "日常"
            
            # 2. 引擎從真實衣櫥挑選 - 實現軟扣分機制（推薦 3 套時追蹤已使用單品）
            engine = RecommendationEngine()
            outfits = []
            # ✅ 優先級 3 修復：初始化 used_items 為空，但稍後會加入 locked_items
            used_items = list(locked_item_ids)  # 初始化為指定單品（必須包含）
            
            for set_idx in range(3):
                try:
                    # 在每一套時傳入已使用單品，實現軟扣分
                    single_outfit = engine.recommend(
                        wardrobe, weather, normalized_occasion, "中性", 
                        parsed_style, needs_outer, used_items=used_items
                    )
                    
                    if single_outfit:
                        outfits.append(single_outfit[0])  # 取第 1 套即可
                        
                        # ✅ 提取該套中的單品 ID 加入 used_items（不包括指定單品，防止後續套裝排除它們）
                        if single_outfit[0].get('items'):
                            for item in single_outfit[0]['items']:
                                if item.get('id') and not is_locked(item['id']):
                                    # 只追蹤非指定的單品，指定單品應在每套中重複出現
                                    used_items.append(item['id'])
                except Exception as e:
                    print(f"[AI] 第 {set_idx+1} 套推薦出錯: {e}")
                    continue
            
            if not outfits:
                return None
            
            # ✅ 過濾避雷清單
            if dislikes:
                dislike_keywords = [kw.strip().lower() for kw in dislikes.split(',')]
                filtered_outfits = []
                
                for outfit in outfits:
                    should_include = True
                    for item in outfit['items']:
                        item_name = (item.get('name', '') + item.get('color', '')).lower()
                        if any(kw in item_name for kw in dislike_keywords):
                            should_include = False
                            break
                    
                    if should_include:
                        filtered_outfits.append(outfit)
                
                outfits = filtered_outfits[:3] if filtered_outfits else outfits[:3]

            # 3. 針對具體衣服產出 100 字溫馨總結 (Gemini 結語) - 融入身形修飾建議
            body_shape_tip = ""
            if user_height and user_weight:
                try:
                    height_cm = float(user_height)
                    weight_kg = float(user_weight)
                    # 簡單 BMI 計算幫助判斷修飾建議
                    bmi = weight_kg / ((height_cm / 100) ** 2)
                    if bmi < 18.5:
                        body_shape_tip = "此使用者偏瘦，應選擇有蓬度/紋理的衣服來增加視覺豐盈感，避免過度貼身。"
                    elif bmi > 25:
                        body_shape_tip = "此使用者偏重，應選擇直線條/深色/豎紋路的衣服來顯瘦，避免過度鬆散或橫紋。"
                    else:
                        body_shape_tip = f"此使用者身材勻稱({height_cm}cm/{weight_kg}kg)，可選擇符合氣質的任何剪裁。"
                except (ValueError, TypeError):
                    body_shape_tip = "無法解析身形數據，建議無身形限制。"
            
            detail_prompt = f"""
## 3) 穿搭推薦細節（detail_prompt｜單一長段文字）

【指令】
你是專業穿搭顧問，請輸出「一段完整文字」（detailed_reasons），語氣溫馨、自然。

【背景資訊】
- 性別：{user_gender}
- 身高體重：{user_height_str} / {user_weight_str}
- 天氣：{weather.temp}度 / {weather.desc}
- 場合：{normalized_occasion}
- 外出目的：{occasion}
- 體感：{thermal_preference}
- 風格：{parsed_style} + {favorite_styles_str}
- 避雷：{dislikes if dislikes else '無'}
- 鎖定單品（若有）：{locked_item_details if locked_item_details else '無'}
- 身形提示：{body_shape_tip if body_shape_tip else '無'}

【男女不同修飾邏輯（必須套用）】

- 若 user_gender = male：
  - 強調肩線、上身結構、比例俐落
  - 常用策略：上短下長、外套撐肩、避免過長上衣壓身高
  - 偏寬者：避免貼身，選擇有垂墜或挺度的版型

- 若 user_gender = female：
  - 強調腰線、腿部比例、整體輕盈感
  - 常用策略：提高腰線、A 字或直筒修飾下身
  - 偏豐者：避免過貼或過薄，利用層次修飾曲線

- 若 user_gender = other：
  - 採中性比例原則，重視線條平衡與層次

【寫作規則（全部必須包含）】

1) 開頭 1–2 句總體建議：
   呼應天氣、體感、場合與外出目的

2) 第 1～3 套穿搭逐套說明，每套需包含：
   - 天氣與體感策略
   - 場合＋外出目的適配原因
   - 風格邏輯說明
   - 依性別套用修飾比例邏輯
   - 明確提及如何避開 dislikes（至少一次）

3) 每套結尾補一句小技巧或備案：
   溫差、下雨、夜晚、冷氣房的調整方式

【限制】
- 不提品牌
- 不捏造材質（未知用中性描述）
- 避免空泛形容詞，需說明「為什麼這樣搭」
- 全文約 220–320 字，單一段落、不分行

方案詳情：
"""
            for i, o in enumerate(outfits):
                names = [f"{it['color']}{it['name']}" for it in o['items']]
                detail_prompt += f"方案{i+1}: {', '.join(names)}\n"
            
            self._rate_limit_wait()
            reason_res = self.model_t1.generate_content(detail_prompt)
            
            return {
                "vibe": analysis.get("vibe_description") or "今天就走舒適俐落的日常穿搭風格。",
                "detailed_reasons": reason_res.text,
                "recommendations": outfits
            }
        except Exception as e:
            print(f"[AI Recommendation Error] {e}")
            return None

    def _map_category_to_frontend(self, model_cat: str) -> str:
        """將 Model A 的類別對應到前端 (Oreoooooo 指定完整版)"""
        UPPER = ['Tee', 'Blouse', 'Top', 'Tank', 'Jersey', 'Hoodie', 'Sweater']
        LOWER = ['Jeans', 'Shorts', 'Skirt', 'Sweatpants', 'Joggers', 'Leggings', 'Chinos']
        OUTER = ['Jacket', 'Coat', 'Blazer', 'Cardigan', 'Parka', 'Kimono']
        FULL = ['Dress', 'Jumpsuit', 'Romper']
        
        if model_cat in UPPER: return "上衣"
        if model_cat in LOWER: return "下身"
        if model_cat in OUTER: return "外套"
        if model_cat in FULL: return "上衣"
        return "配件"

    def parse_recommended_items(self, ai_response: str, wardrobe: List[ClothingItem]) -> List[ClothingItem]:
        """保留解析函數以支援主流程"""
        recommended_items = []
        res = str(ai_response).lower()
        for item in wardrobe:
            if (item.name and item.name.lower() in res) or \
               (f"{item.color}{item.category}".lower() in res.replace(' ', '')):
                recommended_items.append(item)
        return recommended_items

