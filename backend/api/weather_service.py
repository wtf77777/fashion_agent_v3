"""
天氣服務層
處理天氣資料獲取與快取 - 使用台灣中央氣象署 API
"""
import requests
from datetime import datetime, timedelta
from typing import Optional
from database.models import WeatherData
import urllib3

class WeatherService:
    def __init__(self, api_key: str, cache_hours: int = 1):
        self.api_key = api_key
        self.cache_hours = cache_hours
        self._cache = {}  # {city: (weather_data, timestamp)}
    
    def get_weather(self, city: str) -> Optional[WeatherData]:
        """
        獲取天氣資料(含快取機制) - 使用中央氣象署 API
        
        Args:
            city: 城市名稱 (例如: 臺北市, 高雄市)
            
        Returns:
            WeatherData 或 None
        """
        # 檢查快取
        if city in self._cache:
            cached_data, cached_time = self._cache[city]
            if datetime.now() - cached_time < timedelta(hours=self.cache_hours):
                return cached_data
        
        # 獲取新資料
        try:
            # 中央氣象署開放資料平台 API (O-A0003-001 局屬氣象站)
            # 必須使用正確的 API Key (Authorization)
            url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001"
            params = {
                "Authorization": self.api_key
            }
            
            # 使用 verify=False 繞過 SSL 驗證 (避免某些環境下的證書問題)
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url, params=params, timeout=10, verify=False)
            
            response.raise_for_status()
            data = response.json()
            
            # 檢查回應格式
            if not data.get('success'):
                print(f"天氣 API 回應異常: {data}")
                return None
            
            # 解析資料
            records = data.get('records', {})
            stations = records.get('Station', [])
            
            # 確保輸入的城市名稱格式正確
            target_city = city
            
            # 輔助函數: 正規化城市名稱
            def normalize_name(name):
                return name.replace('台', '臺').replace('縣', '').replace('市', '')
            
            target_city_norm = normalize_name(target_city)
            
            # 收集該縣市所有候選氣象站
            candidates = []
            
            # 1. 搜尋局屬氣象站 (O-A0003-001)
            for station in stations:
                geo_info = station.get('GeoInfo', {})
                county_name = geo_info.get('CountyName', '')
                
                if normalize_name(county_name) == target_city_norm:
                    weather_element = station.get('WeatherElement', {})
                    temp = float(weather_element.get('AirTemperature', -99))
                    
                    if temp > -90:
                        altitude = float(geo_info.get('StationAltitude', 9999))
                        candidates.append({
                            'station': station,
                            'altitude': altitude,
                            'source': 'O-A0003-001'
                        })

            # 2. 如果候選名單很少(小於3個)，嘗試自動氣象站 (O-A0001-001) 補充資料
            if len(candidates) < 3:
                try:
                    url_auto = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0001-001"
                    response_auto = requests.get(url_auto, params=params, timeout=10, verify=False)
                    if response_auto.status_code == 200:
                        data_auto = response_auto.json()
                        if data_auto.get('success'):
                            stations_auto = data_auto.get('records', {}).get('Station', [])
                            for station in stations_auto:
                                geo_info = station.get('GeoInfo', {})
                                county_name = geo_info.get('CountyName', '')
                                
                                if normalize_name(county_name) == target_city_norm:
                                    weather_element = station.get('WeatherElement', {})
                                    temp = float(weather_element.get('AirTemperature', -99))
                                    
                                    if temp > -90:
                                        altitude = float(geo_info.get('StationAltitude', 9999))
                                        candidates.append({
                                            'station': station,
                                            'altitude': altitude,
                                            'source': 'O-A0001-001'
                                        })
                except Exception as e:
                    print(f"獲取自動氣象站資料失敗: {str(e)}")

            if not candidates:
                print(f"找不到城市 {city} 的有效氣象站資料")
                return None
            
            # 3. 排序: 優先選擇海拔最低的氣象站
            candidates.sort(key=lambda x: x['altitude'])
            
            best_match = candidates[0]
            found_station = best_match['station']
            valid_weather_element = found_station.get('WeatherElement', {})
            
            # 提取溫度和天氣描述
            temp = float(valid_weather_element.get('AirTemperature', 0))
            humidity = float(valid_weather_element.get('RelativeHumidity', 0))
            weather_desc = valid_weather_element.get('Weather', '晴')
            
            if weather_desc == '-99':
                weather_desc = '多雲'
            
            # 計算體感溫度
            if temp > 26 and humidity > 60:
                feels_like = temp + ((humidity - 60) / 100) * 3
            elif temp < 10:
                feels_like = temp - 2
            else:
                feels_like = temp
            
            weather_data = WeatherData(
                temp=temp,
                feels_like=round(feels_like, 1),
                desc=weather_desc,
                city=city,
                update_time=datetime.now()
            )
            
            self._cache[city] = (weather_data, datetime.now())
            return weather_data
            
        except requests.exceptions.Timeout:
            print(f"天氣 API 請求超時: {city}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"天氣 API 請求失敗: {str(e)}")
            return None
        except (KeyError, ValueError, IndexError) as e:
            print(f"天氣資料解析失敗: {str(e)}")
            return None
        except Exception as e:
            print(f"天氣資料處理失敗: {str(e)}")
            return None
    
    def clear_cache(self):
        """清除快取"""
        self._cache.clear()
