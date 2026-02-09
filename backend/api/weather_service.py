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
            try:
                humidity_raw = valid_weather_element.get('RelativeHumidity', -99)
                humidity = float(humidity_raw)
            except Exception:
                humidity = -99.0
            # 濕度防呆：缺值或異常時給預設 60%
            if humidity < 0 or humidity > 100:
                humidity = 60.0

            # 風速（可能不存在）
            wind_speed = None
            for key in ["WindSpeed", "WindSpeedObs", "WindSpeed10M"]:
                if key in valid_weather_element:
                    try:
                        wind_speed = float(valid_weather_element.get(key))
                    except Exception:
                        wind_speed = None
                    break

            weather_desc = valid_weather_element.get('Weather', '晴')
            if weather_desc == '-99':
                weather_desc = '多雲'
            
            # 體感溫度計算（簡版 Heat Index / 風寒）
            def heat_index_c(t, rh):
                # NOAA Heat Index 改寫攝氏版本
                return (
                    -8.784695 +
                    1.61139411 * t +
                    2.338549 * rh -
                    0.14611605 * t * rh -
                    0.012308094 * (t ** 2) -
                    0.016424828 * (rh ** 2) +
                    0.002211732 * (t ** 2) * rh +
                    0.00072546 * t * (rh ** 2) -
                    0.000003582 * (t ** 2) * (rh ** 2)
                )

            def wind_chill_c(t, wind_ms):
                # 公式需要 km/h
                v = wind_ms * 3.6
                return 13.12 + 0.6215 * t - 11.37 * (v ** 0.16) + 0.3965 * t * (v ** 0.16)

            feels_like = temp
            if temp >= 27 and humidity >= 40:
                hi = heat_index_c(temp, humidity)
                # Heat Index 不應低於實際溫度
                feels_like = max(temp, hi)
            elif temp <= 10:
                if wind_speed and wind_speed > 0:
                    wc = wind_chill_c(temp, wind_speed)
                    feels_like = min(temp, wc)  # 風寒不應高於實測
                else:
                    feels_like = temp - 2
            elif 18 <= temp < 27 and humidity >= 60:
                # 中溫高濕微調：隨濕度線性加成 0.5~2.5 度
                add = 0.5 + (min(humidity, 90) - 60) / 30 * 2.0
                feels_like = temp + add
            elif 10 < temp < 18 and wind_speed and wind_speed > 2:
                # 輕度風寒：風速>2 m/s 時扣 1~2 度
                feels_like = temp - min(2.0, 0.5 + (wind_speed / 5))
            elif temp > 26 and humidity > 60:
                # 保留原本輕量加成邏輯（高濕但未達 27 度，且未觸發上方中溫段）
                feels_like = temp + ((humidity - 60) / 100) * 3
            
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
