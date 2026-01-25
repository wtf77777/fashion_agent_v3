from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from config import AppConfig
from database.supabase_client import SupabaseClient
from api.ai_service import AIService
from api.weather_service import WeatherService
from api.wardrobe_service import WardrobeService
from database.models import ClothingItem

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = AppConfig.from_env()
supabase_client = SupabaseClient(config.supabase_url, config.supabase_key)
ai_service = AIService(config.gemini_api_key)
weather_service = WeatherService(config.weather_api_key)
wardrobe_service = WardrobeService(supabase_client)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# ========== 認證 ==========

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """登入"""
    try:
        result = supabase_client.client.table("users")\
            .select("id")\
            .eq("username", username)\
            .eq("password", password)\
            .execute()
        
        if result.data:
            return {
                "success": True,
                "user_id": str(result.data[0]['id']),
                "username": username
            }
        
        return {"success": False, "message": "帳號或密碼錯誤"}
    except Exception as e:
        print(f"[ERROR] 登入: {str(e)}")
        return {"success": False, "message": "登入失敗"}

@app.post("/api/register")
async def register(username: str = Form(...), password: str = Form(...)):
    """註冊"""
    try:
        # 檢查重複
        existing = supabase_client.client.table("users")\
            .select("id")\
            .eq("username", username)\
            .execute()
        
        if existing.data:
            return {"success": False, "message": "使用者名稱已存在"}
        
        # 新增用戶（讓 Supabase 自動生成 UUID）
        result = supabase_client.client.table("users")\
            .insert({"username": username, "password": password})\
            .execute()
        
        if result.data:
            return {"success": True, "message": "註冊成功"}
        
        return {"success": False, "message": "註冊失敗"}
    except Exception as e:
        print(f"[ERROR] 註冊: {str(e)}")
        return {"success": False, "message": "註冊失敗"}

# ========== 天氣 ==========

@app.get("/api/weather")
async def get_weather(city: str = "Taipei"):
    """天氣"""
    try:
        weather = weather_service.get_weather(city)
        return weather.to_dict() if weather else {"error": "無法獲取天氣"}
    except Exception as e:
        print(f"[ERROR] 天氣: {str(e)}")
        return {"error": str(e)}

# ========== 上傳 ==========

@app.post("/api/upload")
async def upload_images(request: Request):
    """上傳衣物"""
    import traceback
    
    try:
        print(f"[INFO] ========== 開始上傳流程 ==========")
        
        # 步驟 1: 接收表單資料
        form = await request.form()
        user_id = form.get("user_id")
        files = form.getlist("files")
        warmth_str = form.get("warmth", "薄")
        
        # 映射厚度字串到數值
        warmth_map = {"薄": 2, "適中": 5, "厚": 8}
        user_warmth = warmth_map.get(warmth_str, 5)
        
        print(f"[INFO] 步驟 1: 接收到 user_id={user_id}, 文件數量={len(files)}, 厚度={warmth_str}({user_warmth})")
        
        if not user_id or not files:
            print(f"[ERROR] 缺少必要參數: user_id={user_id}, files={len(files) if files else 0}")
            return {"success": False, "message": "缺少必要參數"}
        
        # 步驟 2: 讀取圖片
        img_bytes_list = []
        file_names = []
        
        for idx, file in enumerate(files):
            content = await file.read()
            img_bytes_list.append(content)
            file_names.append(file.filename)
            print(f"[INFO] 步驟 2.{idx+1}: 讀取文件 '{file.filename}', 大小={len(content)} bytes")
        
        # 步驟 3: AI 辨識
        print(f"[INFO] 步驟 3: 開始 AI 辨識 {len(img_bytes_list)} 張圖片...")
        tags_list = ai_service.batch_auto_tag(img_bytes_list)
        
        if not tags_list:
            print(f"[ERROR] AI 辨識失敗: tags_list 為 None")
            return {"success": False, "message": "AI 辨識失敗,請稍後再試"}
        
        print(f"[INFO] 步驟 3: AI 辨識成功,返回 {len(tags_list)} 個標籤")
        for idx, tags in enumerate(tags_list):
            print(f"[INFO]   - 圖片 {idx+1}: {tags}")
        
        # 步驟 4: 儲存到資料庫
        print(f"[INFO] 步驟 4: 開始儲存到資料庫...")
        success_count = 0
        fail_count = 0
        fail_details = []
        
        for idx, (img_bytes, tags, filename) in enumerate(zip(img_bytes_list, tags_list, file_names)):
            try:
                print(f"[INFO] 步驟 4.{idx+1}: 處理 '{filename}'...")
                
                item = ClothingItem(
                    user_id=user_id,
                    name=tags.get('name', filename),
                    category=tags.get('category', '其他'),
                    color=tags.get('color', '未知'),
                    style=tags.get('style', ''),
                    warmth=user_warmth # 使用使用者指定的厚度
                )
                
                success, msg = wardrobe_service.save_item(item, img_bytes)
                
                if success:
                    success_count += 1
                    print(f"[INFO] 步驟 4.{idx+1}: '{filename}' 儲存成功")
                else:
                    fail_count += 1
                    fail_details.append(f"{filename}: {msg}")
                    print(f"[ERROR] 步驟 4.{idx+1}: '{filename}' 儲存失敗 - {msg}")
                    
            except Exception as e:
                fail_count += 1
                error_msg = str(e)
                fail_details.append(f"{filename}: {error_msg}")
                print(f"[ERROR] 步驟 4.{idx+1}: '{filename}' 處理異常 - {error_msg}")
                print(f"[ERROR] 詳細錯誤: {traceback.format_exc()}")
        
        print(f"[INFO] ========== 上傳完成: 成功 {success_count} 件, 失敗 {fail_count} 件 ==========")
        
        return {
            "success": True,
            "success_count": success_count,
            "fail_count": fail_count,
            "items": tags_list[:success_count],
            "fail_details": fail_details if fail_details else None
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] ========== 上傳流程異常 ==========")
        print(f"[ERROR] 錯誤訊息: {error_msg}")
        print(f"[ERROR] 詳細堆疊: {traceback.format_exc()}")
        return {"success": False, "message": f"上傳失敗: {error_msg}"}

# ========== 衣櫥 ==========

@app.get("/api/wardrobe")
async def get_wardrobe(user_id: str):
    """取得衣櫥"""
    try:
        items = wardrobe_service.get_wardrobe(user_id)
        return {"success": True, "items": [item.to_dict() for item in items]}
    except Exception as e:
        print(f"[ERROR] 衣櫥: {str(e)}")
        return {"success": False, "message": "查詢失敗"}

@app.post("/api/wardrobe/delete")
async def delete_item(user_id: str = Form(...), item_id: int = Form(...)):
    """刪除衣物"""
    try:
        success = wardrobe_service.delete_item(user_id, item_id)
        return {"success": success}
    except Exception as e:
        print(f"[ERROR] 刪除: {str(e)}")
        return {"success": False}

@app.post("/api/wardrobe/batch-delete")
async def batch_delete(user_id: str = Form(...), item_ids: List[int] = Form(...)):
    """批量刪除"""
    try:
        success, count, fail = wardrobe_service.batch_delete_items(user_id, item_ids)
        return {"success": success, "success_count": count, "fail_count": fail}
    except Exception as e:
        print(f"[ERROR] 批量刪除: {str(e)}")
        return {"success": False, "success_count": 0, "fail_count": len(item_ids)}

# ========== 推薦 ==========

@app.post("/api/recommendation")
async def get_recommendation(
    user_id: str = Form(...),
    city: str = Form(...),
    style: str = Form(""),
    occasion: str = Form("外出遊玩")
):
    """推薦衣搭"""
    try:
        wardrobe = wardrobe_service.get_wardrobe(user_id)
        if not wardrobe:
            return {"success": False, "message": "衣櫥是空的"}
        
        weather = weather_service.get_weather(city)
        if not weather:
            return {"success": False, "message": "無法獲取天氣"}
        
        recommendation = ai_service.generate_outfit_recommendation(
            wardrobe, weather, style or "不限", occasion
        )
        if not recommendation:
            return {"success": False, "message": "推薦生成失敗"}
        
        # ✅ Oreoooooo 修正：因為現在回傳的是結構化資料，不需再手動解析文字
        return {
            "success": True,
            "recommendation": recommendation, # 包含 vibe 和 recommendations
            "items": [] # 為了相容前端舊欄位，保留但留空，主要資料在 recommendation 裡
        }
    except Exception as e:
        print(f"[ERROR] 推薦: {str(e)}")
        return {"success": False, "message": "推薦失敗"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
