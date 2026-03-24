# weather_engine.py
import os
import time
import requests

class WeatherForecaster:
    def __init__(self, ttl_seconds=600):
        # Thông số cấu hình API (Lấy từ file .env)
        self.api_key = os.getenv("WEATHER_API_KEY", "")
        self.lat = os.getenv("WEATHER_LAT", "")
        self.lon = os.getenv("WEATHER_LON", "")
        self.units = os.getenv("WEATHER_UNITS", "metric")
        
        # Hệ thống Cache
        self.ttl_seconds = ttl_seconds
        self._last_fetch_ts = 0.0
        self._cached_data = None

    def fetch_forecast(self):
        """Gọi API OpenWeatherMap để lấy dự báo 12h tới (4 mốc, mỗi mốc 3h)"""
        if not self.api_key or not self.lat or not self.lon:
            return None

        # Trả về cache nếu chưa hết 10 phút
        if time.time() - self._last_fetch_ts < self.ttl_seconds and self._cached_data:
            return self._cached_data

        url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={self.lat}&lon={self.lon}&units={self.units}&appid={self.api_key}&lang=vi"
        )

        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            simplified = []
            rain_soon = False
            rain_reason = None
            future_temps = []
            future_clouds = []

            # Lấy 4 mốc (tương đương 12 giờ tới)
            for item in data.get("list", [])[:4]:  
                weather_main = item.get("weather", [{}])[0].get("main", "").lower()
                weather_desc = item.get("weather", [{}])[0].get("description", "").lower()
                
                # Check mưa trong tương lai
                is_rain = ("rain" in weather_main) or ("mưa" in weather_desc) or ("rain" in item)
                if is_rain and not rain_soon:
                    rain_soon = True
                    # Lấy giờ dự báo (ví dụ: 15:00)
                    rain_reason = item.get("dt_txt", "").split(' ')[1][:5] 

                simplified.append({
                    "time": item["dt_txt"],
                    "temp": item["main"]["temp"],
                    "description": weather_desc,
                    "clouds": item["clouds"]["all"]
                })
                future_temps.append(item["main"]["temp"])
                future_clouds.append(item["clouds"]["all"])

            self._cached_data = {
                "forecast": simplified,
                "rain_soon": rain_soon,
                "rain_reason": rain_reason,
                "avg_temp": sum(future_temps)/len(future_temps) if future_temps else 0,
                "avg_clouds": sum(future_clouds)/len(future_clouds) if future_clouds else 0
            }
            self._last_fetch_ts = time.time()
            return self._cached_data
        except Exception as e:
            print(f"⚠️ Weather Engine Error: {e}")
            return self._cached_data

    def analyze_with_current_data(self, current_weather):
        """
        NHẬN dữ liệu hiện tại từ app.py và KẾT HỢP với dự báo tương lai.
        Duy gọi hàm này trong check_system_decision.
        """
        forecast = self.fetch_forecast()
        
        # 1. Kiểm tra hiện tại (Dữ liệu Duy truyền từ app.py sang)
        curr_desc = current_weather.get('description', '').lower()
        if "rain" in curr_desc or "mưa" in curr_desc:
            return True, "Trời đang mưa thực tế."

        # 2. Kiểm tra tương lai (Từ API Forecast)
        if forecast and forecast.get('rain_soon'):
            return True, f"Dự báo có mưa lúc {forecast['rain_reason']}."

        return False, "Thời tiết thuận lợi."

    def get_future_features(self):
        """Cung cấp dữ liệu cho AI LSTM (Duy nên giữ lại để nâng cấp sau)"""
        data = self.fetch_forecast()
        if data:
            return {"f_temp": data['avg_temp'], "f_clouds": data['avg_clouds']}
        return {"f_temp": 30, "f_clouds": 50}
    

    def get_weather():
    # Lấy từ Render (Ưu tiên số 1)
      api_key = os.environ.get('WEATHER_API_KEY')
      lat = os.environ.get('WEATHER_LAT')
      lon = os.environ.get('WEATHER_LON')

      if not api_key:
        # Nếu vẫn không thấy, Dashboard sẽ báo lỗi này thay vì mã 400 trống rỗng
          return {"error": "Chưa nhận được API Key từ Render"}, 400
        
    # Tiếp tục logic gọi API OpenWeather của Duy ở đây...git add .
    
      return {"status": "success", "temp": 30} # Ví dụ trả về