# ASPC - PROJECT
# ASPC_new sẽ loại bỏ cảm biến nhiệt bề mặt - thay vào đó tập trung vào nhiệt độ môi trường và ánh sáng để dự báo, nhằm tăng độ ổn định và giảm lỗi cảm biến.
import json
import sqlite3
import datetime
import threading
import ssl
import math
import os
import socket
import sys
import time
from dotenv import load_dotenv
import requests
from flask import session, redirect, url_for, flash , Response
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import cv2
import numpy as np

# Load biến môi trường từ file .env (cố định theo thư mục file này)
try:
    _dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(dotenv_path=_dotenv_path)
except Exception:
    load_dotenv()

# Tránh crash UnicodeEncodeError trên Windows console (cp1258/cp1252...)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import random 
from flask import request, jsonify
from collections import deque
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from models import Notification, db, User, Station, Device, SensorData,CommandHistory
from sqlalchemy import func, extract
from ai_engine import SolarMLP
from health_engine import SolarHealthEngine
from optimizer import SolarOptimizer
from hotspot_engine import HotspotDetector


DB_NAME = "aspc_history.db"


SIMULATION_MODE = True #bật data giả lập
#os.getenv("SIMULATION_MODE", "False").lower() == "true" 



# MQTT CẤU HÌNH KẾT NỐI (đọc từ biến môi trường)
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "8883"))
TOPIC_SUB = os.getenv("MQTT_TOPIC_SUB", "aspc/data")
TOPIC_PUB = os.getenv("MQTT_TOPIC_PUB", "aspc/control")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
#Hệ số thích nghi K
K_FACTOR = 0.00015
TEMP_COEFF = 0.0045
TEMP_STD = 25.0

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_LAT = os.getenv("WEATHER_LAT", "")
WEATHER_LON = os.getenv("WEATHER_LON", "")
WEATHER_UNITS = os.getenv("WEATHER_UNITS", "metric")

# --- CẤU HÌNH CẢNH BÁO ---
TEMP_THRESHOLD_HIGH = 40
TEMP_THRESHOLD_SAFE = 35
AUTO_DELAY_SECONDS = 60     
MIN_RUN_TIME = 60



# [CẬP NHẬT] Biến trạng thái hệ thống
system_state = {
    "mode": "MANUAL",
    "warning_start_time": None, 
    "is_auto_running": False,
    "last_auto_start": 0,
    # Tách làm 2 biến riêng biệt
    "last_advice_on_time": 0, 
    "last_advice_off_time": 0
}

# BIẾN TÍCH LŨY NĂNG LƯỢNG
energy_state = {
    "E_real_today": 0.0,
    "E_no_cool_today": 0.0,
    "E_real_month": 0.0,
    "E_no_cool_month": 0.0,
    "last_day": time.localtime().tm_mday,
    "last_month": time.localtime().tm_mon
}

#Cấu hình cảnh báo sụt áp
ALERT_THRESHOLDS = {
    "current_overload": 1.5,  # 150% P_max (quá dòng)
    "voltage_min": 340,       # V (sụt điện áp, giả định 400V chuẩn)
    "humidity_max": 95,       # % (chập nước)
    "lux_max": 150000         # Lux (cảm biến lỗi)
}




#Sử dụng database mới
app = Flask(__name__, static_folder='static', template_folder='static')

app.secret_key = os.getenv('SECRET_KEY', 'khoa_bi_mat_sieu_cap_aspc_2026')



# BẮT ĐẦU THÊM CẤU HÌNH SQLALCHEMY 
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'aspc_production.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# CẤU HÌNH UPLOAD ẢNH
UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Tự tạo thư mục nếu chưa có
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

# Tạo các bảng tự động dựa trên models.py
with app.app_context():
    db.create_all()
    print(" Đã khởi tạo Database Multi-tenant!")
# KẾT THÚC THÊM CẤU HÌNH 













socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")














def _find_free_port(host: str, start_port: int, max_tries: int = 30) -> int:
    """
    Tránh WinError 10048 khi port đang bị chiếm.
    Thử start_port, nếu bận thì tăng dần cho tới khi bind được.
    """
    port = int(start_port)
    for _ in range(max_tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return port
        except OSError:
            port += 1
        finally:
            try:
                s.close()
            except Exception:
                pass
    return int(start_port)



# DATABASE & AI
# def init_db():
#     try:
#         conn = sqlite3.connect(DB_NAME)
#         c = conn.cursor()
#         c.execute('''CREATE TABLE IF NOT EXISTS history
#                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
#                       timestamp TEXT, 
#                       user_id TEXT, 
#                       command TEXT, 
#                       action_type TEXT, 
#                       source TEXT)''')
#         # Table lưu lịch sử dài hạn 
#         c.execute('''
#         CREATE TABLE IF NOT EXISTS sensor_history (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             timestamp TEXT,
#             temp_panel REAL,
#             temp_env REAL,
#             humidity REAL,
#             lux REAL,
#             power REAL,
#             pump_status INTEGER,
#             current REAL,
#             voltage REAL,
#             health_score REAL,
#             profit REAL,
#             delta_e REAL
#         )
#     ''')
        
#         conn.commit()
#         conn.close()
#     except: pass
# init_db() 




print(" Đang khởi tạo hệ thống AI/Logic Engine Multi-tenant...")

# Dictionary lưu trữ các engine cho từng thiết bị
device_engines = {}

def get_engines(mac_address):
    """Lấy hoặc tạo mới bộ não cho thiết bị cụ thể"""
    if mac_address not in device_engines:
        print(f"⚙️ Khởi tạo bộ máy AI & Logic cho thiết bị: {mac_address}")
        device_engines[mac_address] = {
            "ai": SolarMLP(mac_address=mac_address),
            "health": SolarHealthEngine(mac_address=mac_address),
            "optimizer": SolarOptimizer(), # Optimizer không lưu file nên dùng mặc định
            "hotspot": HotspotDetector()   # Hotspot chỉ tính toán tức thời nên dùng mặc định
        }
    return device_engines[mac_address]


class WeatherCache:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl_seconds = ttl_seconds
        self._last_fetch_ts = 0.0
        self._last_payload = None

    def get(self):
        return self._last_payload

    def is_stale(self):
        return (time.time() - self._last_fetch_ts) > self.ttl_seconds

    def set(self, payload):
        self._last_payload = payload
        self._last_fetch_ts = time.time()


weather_cache = WeatherCache(ttl_seconds=int(os.getenv("WEATHER_CACHE_TTL", "600")))


def fetch_weather_forecast():
    """Gọi OpenWeatherMap One Call API / forecast đơn giản"""
    if not WEATHER_API_KEY or not WEATHER_LAT or not WEATHER_LON:
        return None

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={WEATHER_LAT}&lon={WEATHER_LON}&units={WEATHER_UNITS}&appid={WEATHER_API_KEY}"
    )

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        # Lấy thông tin gọn: dự báo vài mốc đầu
        simplified = []
        rain_soon = False
        rain_reason = None

        for item in data.get("list", [])[:8]:  # khoảng 24h tới (3h x 8)
            w0 = (item.get("weather") or [{}])[0] or {}
            main = (w0.get("main") or "").lower()
            desc = (w0.get("description") or "").lower()
            has_rain_volume = "rain" in item  # OpenWeather trả 'rain': {'3h': ...} khi có mưa
            is_rain = ("rain" in main) or ("rain" in desc) or has_rain_volume
            if is_rain and not rain_soon:
                rain_soon = True
                rain_reason = item.get("dt_txt") or "soon"

            simplified.append({
                "time": item["dt_txt"],
                "temp": item["main"]["temp"],
                "humidity": item["main"]["humidity"],
                "clouds": item["clouds"]["all"],
                "wind_speed": item["wind"]["speed"],
                "weather": w0.get("description", ""),
                "pop": item.get("pop", 0) * 100,  # % (API trả 0-1, nhân 100)
                "rain": item.get("rain", {})    
            })

        return {
            "location": data.get("city", {}).get("name", ""),
            "lat": WEATHER_LAT,
            "lon": WEATHER_LON,
            "forecast": simplified,
            "rain_soon": rain_soon,
            "rain_reason": rain_reason
        }
    except Exception as e:
        print(f" Lỗi gọi API thời tiết: {e}")
        return None


def get_weather_cached():
    
    if weather_cache.get() is None or weather_cache.is_stale():
        payload = fetch_weather_forecast()
        if payload is not None:
            weather_cache.set(payload)
        else:
            # Nếu fetch fail thì vẫn trả cache cũ (nếu có)
            return weather_cache.get()
    return weather_cache.get()
# HÀM MỚI NẰM TÁCH BIỆT BÊN NGOÀI
def get_current_wind_speed():
    try:
        weather_data = get_weather_cached()
        if weather_data and 'forecast' in weather_data and len(weather_data['forecast']) > 0:
            return float(weather_data['forecast'][0].get('wind_speed', 0))
    except:
        pass
    return 0.0




#  [MỚI] QUẢN LÝ NĂNG LƯỢNG & HIỆU QUẢ 

class EnergyManager:
    def __init__(self):
        self.last_update_time = time.time()
        
        # SỬ DỤNG time.localtime() để tránh hoàn toàn lỗi của thư viện datetime
        current_time_struct = time.localtime()
        
        # Biến tích lũy Hôm nay
        self.today_day = current_time_struct.tm_mday
        self.e_real_today = 0.0      # Wh thực tế
        self.e_no_cool_today = 0.0   # Wh giả định nếu không làm mát
        
        # Biến tích lũy Tháng này
        self.current_month = current_time_struct.tm_mon
        self.e_real_month = 0.0
        self.e_no_cool_month = 0.0

    def reset_counters_if_needed(self):
        current_time_struct = time.localtime()
        
        # Reset ngày
        if current_time_struct.tm_mday != self.today_day:
            self.e_real_today = 0.0
            self.e_no_cool_today = 0.0
            self.today_day = current_time_struct.tm_mday
            
        # Reset tháng
        if current_time_struct.tm_mon != self.current_month:
            self.e_real_month = 0.0
            self.e_no_cool_month = 0.0
            self.current_month = current_time_struct.tm_mon

    def calculate_step(self, p_real_W, lux, temp_env, p_max, alpha_p):
        """
        Tính toán năng lượng trong khoảng thời gian giữa 2 lần nhận tin (dt)
        """
        current_time = time.time()
        dt_seconds = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # Tránh lỗi dt quá lớn khi mới khởi động hoặc mất kết nối lâu
        if dt_seconds > 300: dt_seconds = 2 # Giả định mặc định nếu mất tín hiệu quá lâu
        
        dt_hours = dt_seconds / 3600.0 # Đổi sang giờ
        
        # 1. Tính Wh thực tế
        wh_real_step = p_real_W * dt_hours
        
        # 2. Tính Wh giả định "Nếu không làm mát" (No Cool)
        # Giả sử nóng hơn môi trường 10-20 độ tùy nắng
        pred_temp_no_cool = temp_env + (lux / 4000) 

        # B2: Tính công suất giả định (Công thức vật lý tấm pin)
        # P = P_max * (Lux/100000) * [1 + alpha * (T - 25)]
        irradiance_ratio = lux / 100000.0 if lux > 0 else 0
        loss_factor = alpha_p * (pred_temp_no_cool - 25)
        p_no_cool_W = p_max * irradiance_ratio * (1 - loss_factor)
        
        # Đảm bảo không âm
        if p_no_cool_W < 0: p_no_cool_W = 0
        
        # B3: Tính Wh giả định
        wh_no_cool_step = p_no_cool_W * dt_hours

        # 3. Cộng dồn
        self.reset_counters_if_needed()
        
        self.e_real_today += wh_real_step
        self.e_no_cool_today += wh_no_cool_step
        
        self.e_real_month += wh_real_step
        self.e_no_cool_month += wh_no_cool_step
        
        return {
            "p_real": p_real_W,
            "p_no_cool": p_no_cool_W,
            "t_no_cool": pred_temp_no_cool
        }

    def get_stats(self, elec_price):
        # Tính X (Tăng thêm kWh hôm nay)
        x_gain_wh = self.e_real_today - self.e_no_cool_today
        x_gain_kwh = x_gain_wh / 1000.0
        
        # Tính Y (Tiền tiết kiệm hôm nay)
        y_saved_vnd = x_gain_kwh * elec_price
        
        # Tính Z (% Tăng trưởng tháng này)
        if self.e_no_cool_month > 0:
            z_percent = ((self.e_real_month - self.e_no_cool_month) / self.e_no_cool_month) * 100
        else:
            z_percent = 0
            
        return {
            "x_today_kwh": round(x_gain_kwh, 3),
            "y_today_vnd": round(y_saved_vnd, 1),
            "z_month_percent": round(z_percent, 1),
            "total_real_kwh_today": round(self.e_real_today / 1000, 3)
        }
# Khởi tạo Global
energy_manager = EnergyManager()
# DATABASE HELPERS 
def save_history(user, cmd, action_type, source):
    try:
        with app.app_context():
            new_record = CommandHistory(
                user_id=str(user),
                command=str(cmd),
                action_type=str(action_type),
                source=str(source)
            )
            db.session.add(new_record)
            db.session.commit()
    except Exception as e: 
        print(f"Lỗi lưu history: {e}")

# Hàng đợi để lưu 5 giá trị nhiệt độ gần nhất
temp_history = deque(maxlen=5)








# xuất báo cáo theo tháng
def get_monthly_report(year, month):
    try:
        with app.app_context():
            # 1. Tính tổng tiền và điện
            econ_result = db.session.query(
                func.sum(SensorData.profit), 
                func.sum(SensorData.delta_e)
            ).filter(
                extract('year', SensorData.timestamp) == year,
                extract('month', SensorData.timestamp) == month
            ).first()

            # 2. Tính trung bình sức khỏe và tổng số bản ghi
            health_result = db.session.query(
                func.avg(SensorData.health_score), 
                func.count(SensorData.id)
            ).filter(
                extract('year', SensorData.timestamp) == year,
                extract('month', SensorData.timestamp) == month
            ).first()

            # 3. ĐẾM SỐ BẢN GHI TỐT (Sức khỏe >= 80%) [ĐÃ XÓA GIẢ LẬP]
            good_records = db.session.query(func.count(SensorData.id)).filter(
                extract('year', SensorData.timestamp) == year,
                extract('month', SensorData.timestamp) == month,
                SensorData.health_score >= 80.0
            ).scalar() or 0

            total_profit = econ_result[0] or 0 if econ_result else 0
            total_energy_saved = econ_result[1] or 0 if econ_result else 0
            avg_health = health_result[0] or 0 if health_result else 0
            total_records = health_result[1] or 0 if health_result else 0

            return {
                "month": f"{year}-{month:02d}",
                "economic": {
                    "total_profit": total_profit,
                    "total_energy_saved": total_energy_saved
                },
                "health": {
                    "avg_health_score": round(avg_health, 2),
                    "total_records": total_records,
                    "good_days": good_records, # Hiển thị số mẫu Tốt thực tế
                    "bad_days": total_records - good_records # Hiển thị số mẫu Xấu thực tế
                }
            }
    except Exception as e:
        print(f"Lỗi xuất báo cáo: {e}")
        return {"error": str(e)}











def get_smooth_temp(raw_temp):
    temp_history.append(raw_temp)
    # Trả về trung bình cộng
    return sum(temp_history) / len(temp_history)


def should_skip_cooling_due_to_rain(pred_temp=None):
   
    try:
        # Lấy forecast từ weather cache (giả sử đã có)
        weather_data = weather_cache.get()
        if not weather_data or 'forecast' not in weather_data:
            return False, "Không có dữ liệu forecast"
        
        # Lấy mốc forecast gần nhất (3h tới)
        next_forecast = weather_data.get('forecast', [{}])[0] if weather_data.get('forecast') else {}
        
        rain_prob = next_forecast.get('pop', 0)  # Xác suất mưa (0-100%)
        rain_mm = next_forecast.get('rain', {}).get('3h', 0) if 'rain' in next_forecast else 0  # Lượng mưa 3h (mm)
        
        # Logic thông minh
        if rain_prob > 70 and rain_mm > 5:
            # Mưa chắc chắn và nhiều → Skip cooling
            return True, f"Mưa to sắp tới ({rain_prob}% xác suất, {rain_mm}mm). Bỏ qua cooling."
        elif rain_prob < 30:
            # Mưa không chắc → Tiếp tục cooling
            return False, f"Ít mưa ({rain_prob}% xác suất). Tiếp tục cooling."
        else:
            # Không chắc (30-70%) → Cân nhắc với AI pred_temp
            if pred_temp and pred_temp > 45:
                # Nếu AI dự báo nóng quá → Vẫn cooling
                return False, f"Mưa không chắc ({rain_prob}%), nhưng nhiệt độ dự báo cao ({pred_temp:.1f}°C). Tiếp tục cooling."
            else:
                # Ngược lại → Skip để an toàn
                return True, f"Mưa có thể xảy ra ({rain_prob}%). Skip cooling để tránh lãng phí."
    except Exception as e:
        print(f"Lỗi dự báo mưa: {e}")
        return False, "Lỗi kiểm tra mưa"
    



# Cảnh báo bảo vệ vật lý tự động nội suy
def check_protection_alerts(temp_panel, temp_env, humidity, lux, p_actual, pump_status, current=None, voltage=None):
    """Kiểm tra các cảnh báo bảo vệ vật lý và gửi alert qua Socket.IO"""
    alerts = []
    
    # Lấy Pmax từ cấu hình
    mac_address = "ESP32_DEFAULT" 
    health_brain = get_engines(mac_address)["health"]
    p_max = health_brain.p_max 

    # 1. Ước lượng I_max và U_max dựa trên Pmax
    estimated_u_max = 20.0 if p_max <= 200 else 50.0 
    estimated_i_max = p_max / estimated_u_max * 1.5 # Nhân hệ số an toàn 1.5 lần

    # 2. KIỂM TRA QUÁ DÒNG / NGẮN MẠCH
    if current is not None and current > estimated_i_max:
        alerts.append({
            "level": "CRITICAL",
            "type": "insulation",
            "message": f"⚡ CẢNH BÁO: Dòng điện cao bất thường ({current}A). Nguy cơ ngắn mạch!"
        })

    # 3. KIỂM TRA SỤT ÁP / HỞ MẠCH
    if lux > 50000 and voltage is not None and voltage < 5.0:
        alerts.append({
            "level": "CRITICAL",
            "type": "voltage_drop",
            "message": f"📉 CẢNH BÁO: Sụt áp nghiêm trọng ({voltage}V) khi trời nắng. Kiểm tra rắc cắm MC4!"
        })

    # 4. KIỂM TRA LỖI CẢM BIẾN U, I, P
    if voltage is not None and current is not None and lux > 10000:
        p_calc = voltage * current
        if p_actual > 0 and abs(p_calc - p_actual) / p_actual > 0.2:
            alerts.append({
                "level": "WARNING",
                "type": "sensor_malfunction",
                "message": "📡 CẢNH BÁO: Dữ liệu P, U, I không khớp. Cảm biến có thể bị lỗi!"
            })

    # 5. KIỂM TRA CHẬP NƯỚC KHI BƠM
    if pump_status == 1 and humidity > 95 and current is not None and current > (estimated_i_max * 0.8):
        alerts.append({
            "level": "CRITICAL",
            "type": "hardware_failure",
            "message": "💧 CẢNH BÁO: Độ ẩm quá cao khi đang bơm. Nguy cơ chập nước!"
        })

    # Gửi tất cả các alert qua Socket.IO nếu có
    for alert in alerts:
        socketio.emit('system_alert', alert)
        print(f"ALERT: {alert['level']} - {alert['message']}")







#  [LOGIC QUAN TRỌNG] KIỂM TRA & RA QUYẾT ĐỊNH 
def check_system_decision(mac_address, temp_panel, temp_env, humidity, lux, wind_speed, p_max, pump_status):
    global system_state
    current_time = time.time()

    engines = get_engines(mac_address)
    ai_brain = engines["ai"]
    health_brain = engines["health"]
    optimizer_brain = engines["optimizer"]

    # 1. Truyền 5 tham số vào AI
    ai_result = ai_brain.predict(temp_env, humidity, lux, wind_speed, pump_status)
    pred_temp_basic = ai_result['pred_temp_15min'] if ai_result else temp_panel

    
    # CHẾ ĐỘ 1: SMART ECO (TỐI ƯU KINH TẾ & AN TOÀN)
    
    if system_state["mode"] == "SMART_ECO":
        # A. AI Dự báo 2 kịch bản tương lai
        pred_off = ai_brain.predict_scenario(temp_env, humidity, lux, wind_speed, 0) # Nếu Tắt bơm
        pred_on = ai_brain.predict_scenario(temp_env, humidity, lux, wind_speed, 1)  # Nếu Bật bơm
        # Fallback nếu AI chưa đủ dữ liệu (Dùng logic thô)
        if pred_off is None: pred_off = temp_panel + 0.5
        if pred_on is None: pred_on = temp_panel - 2.0

        # B. Tính toán G thực tế (dựa vào hệ số k đã học)
        g_meas = lux * health_brain.k_factor

        # C. Gọi Optimizer tính bài toán kinh tế
        should_run, delta_e, profit, reason = optimizer_brain.calculate_decision(
            g_meas, health_brain.p_max, pred_off, pred_on
        )

        # D. Thực thi quyết định
        if should_run:
            # Nếu Optimizer bảo BẬT
            if pump_status == 0 and not system_state["is_auto_running"]:
                skip, rain_reason = should_skip_cooling_due_to_rain(pred_temp_basic)
                if skip:
                    msg = f"SMART: AI đề xuất làm mát nhưng dự báo sắp mưa ({rain_reason}). Tạm không phun để tiết kiệm."
                    print(f" {msg}")
                    socketio.emit('system_alert', {'level': 'info', 'message': msg})
                else:
                    print(f" SMART: Bật bơm. {reason}")
                    mqtt_client.publish(TOPIC_PUB, json.dumps({"command": "2", "type": "COOL", "source": "SMART_ECO"}))
                    system_state["is_auto_running"] = True
                    socketio.emit('system_alert', {'level': 'success', 'message': f'SMART: Đã bật bơm. {reason}'})
                    save_history("SMART_ECO", "BẬT", "Tối ưu kinh tế", "SMART_ECO")
        else:
            # Nếu Optimizer bảo TẮT (Vì lỗ tiền)
            if system_state["is_auto_running"]:
                # --- [LOGIC CHỐNG RUNG LẮC MỚI] ---
                
                # 1. Lấy thời gian đã chạy
                run_duration = current_time - system_state.get("last_auto_start", 0)
                
                # 2. Lấy ngưỡng an toàn hiện tại (ví dụ 45 độ)
                safe_limit = optimizer_brain.temp_safe_max
                
                # 3. QUY TẮC TẮT:
                # - Phải chạy đủ 60s (Bảo vệ động cơ)
                # - VÀ: Nhiệt độ phải giảm sâu hơn ngưỡng an toàn ít nhất 3 độ (Vùng trễ)
                #   (Ví dụ: An toàn là 45, thì phải xuống dưới 42 mới được tắt)
                
                is_cool_enough = temp_panel < (safe_limit - 3.0) 
                
                if run_duration > MIN_RUN_TIME:
                    if is_cool_enough:
                        print(f"💰 SMART: Tắt bơm. {reason}")
                        mqtt_client.publish(TOPIC_PUB, json.dumps({"command": "0", "type": "COOL", "source": "SMART_ECO"}))
                        system_state["is_auto_running"] = False
                        socketio.emit('system_alert', {'level': 'info', 'message': f'SMART: Đã mát ({temp_panel:.1f}°C). Tắt bơm tiết kiệm.'})
                        save_history("SMART_ECO", "TẮT", "Tối ưu kinh tế", "SMART_ECO")
                    else:
                        # Nếu chưa đủ mát thì KHÔNG TẮT, dù đang lỗ
                        pass
        # Gửi dữ liệu kinh tế để vẽ biểu đồ (nếu cần)
        socketio.emit('economic_data', {'profit': profit, 'delta_e': delta_e, 'reason': reason})
   
    # CHẾ ĐỘ 2: AUTO (DỰA VÀO NGƯỠNG NHIỆT)
    
    elif system_state["mode"] == "AUTO":
        # A. Logic bật bơm 
        if pred_temp_basic >= TEMP_THRESHOLD_HIGH:
            if system_state["warning_start_time"] is None:
                system_state["warning_start_time"] = current_time
                socketio.emit('system_alert', {'level': 'warning', 'message': f'AUTO: Dự báo {pred_temp_basic:.1f}°C. Chuẩn bị bật...'})

            elapsed = current_time - system_state["warning_start_time"]
            if elapsed > AUTO_DELAY_SECONDS and pump_status == 0 and not system_state["is_auto_running"]:
                skip, rain_reason = should_skip_cooling_due_to_rain(pred_temp_basic)
                if skip:
                    socketio.emit('system_alert', {
                        'level': 'info',
                        'message': f"AUTO: Dự báo sắp quá nhiệt ({pred_temp_basic:.1f}°C) nhưng sắp mưa ({rain_reason}). Tạm không phun để tiết kiệm."
                    })
                else:
                    
                    mqtt_client.publish(TOPIC_PUB, json.dumps({"command": "2", "type": "COOL", "source": "AI_AUTO"}))
                    system_state["is_auto_running"] = True
                    system_state["last_auto_start"] = current_time
                    save_history("AI_AUTO", "BẬT", "Quá nhiệt", "AUTO")
                    socketio.emit('system_alert', {'level': 'danger', 'message': 'AUTO: Đã bật bơm bảo vệ!'})

# B. Logic tắt bơm có kết hợp ngưỡng nhiệt  
        elif system_state["is_auto_running"]:
            run_duration = current_time - system_state["last_auto_start"]
            if temp_panel < TEMP_THRESHOLD_SAFE and run_duration > MIN_RUN_TIME:
                mqtt_client.publish(TOPIC_PUB, json.dumps({"command": "0", "type": "COOL", "source": "AI_AUTO"}))
                system_state["is_auto_running"] = False
                system_state["warning_start_time"] = None
                save_history("AI_AUTO", "TẮT", "Đã mát", "AUTO")
                socketio.emit('system_alert', {'level': 'success', 'message': 'AUTO: Nhiệt độ ổn định. Tắt bơm.'})

    
    # CHẾ ĐỘ 3: MANUAL (Đưa ra lời khuyên hoạt động)
   

    else: 
        # Lời khuyên BẬT
        if pred_temp_basic >= TEMP_THRESHOLD_HIGH and pump_status == 0:
            if current_time - system_state["last_advice_on_time"] > 60: 
                msg = f"💡 LỜI KHUYÊN: Dự báo nóng ({pred_temp_basic:.1f}°C). Bạn nên BẬT bơm!"
                socketio.emit('system_alert', {'level': 'warning', 'message': msg})
                system_state["last_advice_on_time"] = current_time
        
        # Lời khuyên TẮT
        elif pred_temp_basic < TEMP_THRESHOLD_SAFE and pump_status == 1:
            if current_time - system_state["last_advice_off_time"] > 60:
                msg = f"💡 LỜI KHUYÊN: Đã mát ({pred_temp_basic:.1f}°C). Nên TẮT bơm tiết kiệm."
                socketio.emit('system_alert', {'level': 'success', 'message': msg})
                system_state["last_advice_off_time"] = current_time
        
        system_state["is_auto_running"] = False
    





#MQTT HANDLERS 
def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC_SUB)




def on_message(client, userdata, msg):
    global system_state
    try:
        raw_msg = msg.payload.decode('utf-8')
        # [DEBUG] In ra để xem ESP32 gửi cái gì lên
        print(f"📥 ESP32 Payload: {raw_msg}") 
        
        data = json.loads(raw_msg)
#  BẮT ĐẦU THÊM MỚI 
        # Lấy mã thiết bị, nếu không có thì mặc định là ESP32_DEFAULT
        mac_address = data.get("mac_address", "ESP32_DEFAULT")
        
        # Gọi "bộ não" tương ứng của thiết bị này ra
        engines = get_engines(mac_address)
        ai_brain = engines["ai"]
        health_brain = engines["health"]
        optimizer_brain = engines["optimizer"]
        hotspot_brain = engines["hotspot"]
        #  KẾT THÚC THÊM MỚI 

        current = data.get("current", None)  # A (dòng điện)
        voltage = data.get("voltage", None)  # V (điện áp)





        # 1. ÉP KIỂU DỮ LIỆU AN TOÀN (Tránh lỗi String/None)
        # Xử lý Nhiệt độ (Có lọc nhiễu)
        
        
        temp_env = float(data.get('temp_env', 0) or 0)
        humidity = float(data.get('humidity', 0) or 0)
        lux = float(data.get('lux_ref', data.get('lux' , 0)) or 0)
        pump_status = int(data.get('pump_status', 0) or 0)
        p_actual_W = float(data.get('power', 0) or 0)


       

        # Xử lý Trạng thái bơm (Quan trọng: Chấp nhận cả 1, "1", "true", "ON")
        raw_pump = data.get('pump_status', 0)
        pump_status = 1 if str(raw_pump).upper() in ['1', 'TRUE', 'ON'] else 0
        # Lấy gió từ API
        wind_speed = get_current_wind_speed()

        # Dùng AI để tính Nhiệt độ ảo và Dự báo
        ai_result = ai_brain.predict(temp_env, humidity, lux, wind_speed, pump_status)
        
        if ai_result:
            calc_t = ai_result["current_t_cell"]
            socketio.emit('ai_data', {'ai': ai_result})
        else:
            calc_t = temp_env + (lux / 4000.0) # Fallback

        temp_panel = get_smooth_temp(calc_t)
        #chèn thêm
        check_protection_alerts(temp_panel, temp_env, humidity, lux, p_actual_W, pump_status, current, voltage)

      
    
        



        # [MỚI] QUY TRÌNH TÍNH SỨC KHỎE "TỰ HỌC"
       
        # B1: Dạy cho hệ thống học (nếu trời đẹp)
        health_brain.learn(lux, p_actual_W)
        
        # B2: Nhờ hệ thống tính toán Sức khỏe & Bức xạ (G)
        health_result = health_brain.calculate_health(lux, p_actual_W)
        
        if isinstance(health_result, tuple) and len(health_result) == 3:
            # Nếu trả về đủ 3 giá trị (Phiên bản mới)
            health_score, g_meas, p_theory_val = health_result
        else:
            # Nếu chỉ trả về 2 giá trị (Phiên bản cũ hoặc lỗi)
            health_score, g_meas = health_result if len(health_result) >= 2 else (0, 0)
            p_theory_val = 0 # Gán mặc định để không bị crash




        # Lấy tham số từ Optimizer và Health Engine
        p_max_current = health_brain.p_max
        alpha_p = optimizer_brain.alpha_p
        elec_price = optimizer_brain.elec_price
        
        # Tính toán bước
        energy_manager.calculate_step(p_actual_W, lux, temp_env, p_max_current, alpha_p)
        stats = energy_manager.get_stats(elec_price)      
        socketio.emit('efficiency_data', stats)

         # BẮT ĐẦU ĐOẠN LƯU DATABASE MỚI 
        try:
            with app.app_context():
                # Tìm hoặc tạo thiết bị mặc định (để hệ thống cũ vẫn chạy được)
                default_device = Device.query.first()
                if not default_device:
                    # Khởi tạo dữ liệu mẫu nếu DB trống
                    user = User(username="admin0202@gmail.com", password_hash=generate_password_hash("02022005D@", method='pbkdf2:sha256')
)
                    db.session.add(user)
                    db.session.commit()
                    
                    station = Station(user_id=user.id, name="Trạm Mặc Định")
                    db.session.add(station)
                    db.session.commit()
                    
                    default_device = Device(station_id=station.id, mac_address="ESP32_DEFAULT")
                    db.session.add(default_device)
                    db.session.commit()

                # Thêm dòng dữ liệu mới
                new_data = SensorData(
                    device_id=default_device.id,
                    temp_panel=temp_panel,
                    temp_env=temp_env,
                    humidity=humidity,
                    lux=lux,
                    power=p_actual_W,
                    pump_status=pump_status,
                    current=current,
                    voltage=voltage,
                    health_score=health_result[0] if isinstance(health_result, tuple) else 0,
                    profit=stats.get('y_today_vnd', 0),
                    delta_e=stats.get('x_today_kwh', 0)
                )
                db.session.add(new_data)
                db.session.commit()
        except Exception as e:
            print(f"Lỗi lưu sensor history: {e}")
        # KẾT THÚC ĐOẠN LƯU DATABASE MỚI 


        # Cập nhật AI (Dùng nhiệt độ đã làm mượt để AI không bị loạn)
        data_package = [lux, temp_panel, temp_env, humidity, pump_status]
        ai_brain.update_data(data_package)
        # Kiểm tra logic điều khiển (Gửi temp_panel đã mượt vào)
        check_system_decision(
            mac_address, temp_panel, lux, health_brain.p_max, pump_status,
            temp_env, humidity, wind_speed  # Thêm 3 biến này vào cuối
        )

        ai_result = ai_brain.predict(temp_env, humidity, lux, wind_speed, pump_status)
        if ai_result:
            socketio.emit('ai_data', {'ai': ai_result})



        hotspot_result = hotspot_brain.detect(temp_panel, temp_env, lux, p_actual_W, p_theory_val)
# Chuẩn hóa type để UI xử lý
        reason_lower = (hotspot_result.get('reason') or "").lower()
        hotspot_type = "normal"
        if "bụi" in reason_lower:
            hotspot_type = "dust"
        elif "cell" in reason_lower or "diode" in reason_lower or "hotspot cốt lõi" in reason_lower:
            hotspot_type = "core_fault"

        dust_level = hotspot_result.get('risk_percent', 0) if hotspot_type == "dust" else 0


        
        #  DỊCH TRẠNG THÁI BƠM (DỮ LIỆU THẬT)
        pump_mode = "IDLE"
        pump_reason = "Đang chờ"
        
        if pump_status == 1:
            if system_state["mode"] == "MANUAL":
                # Đọc lại xem người dùng vừa bấm nút nào
                manual_type = system_state.get('last_manual_type', 'COOL')
                if manual_type == 'CLEAN':
                    pump_mode = "CLEANING"
                    pump_reason = "Người dùng bật Làm Sạch"
                else:
                    pump_mode = "COOLING"
                    pump_reason = "Người dùng bật Làm Mát"
                    
            elif hotspot_result['status'] == 'DANGER':
                pump_mode = "COOLING"
                pump_reason = "Phun làm mát khẩn cấp (Hotspot)"
                
            # Logic Tự Động / Smart: Ưu tiên Làm Sạch nếu phát hiện rác/bụi/phân chim
            elif health_score < 85 and lux > 20000 and temp_panel < 50.0:
                pump_mode = "CLEANING"
                pump_reason = "Rửa trôi bề mặt (Bụi/Phân chim)"
                
            # Nếu không có rác, mà bơm vẫn chạy -> Chắc chắn là đang Làm mát
            else:
                pump_mode = "COOLING"
                pump_reason = "Tối ưu nhiệt độ (AI)"
        else:
            if system_state["mode"] == "MANUAL":
                pump_mode = "IDLE"
                pump_reason = "Đã tắt (Thủ công)"
            else:
                pump_mode = "IDLE"
                pump_reason = "Hệ thống tối ưu"

        # 3. Gửi dữ liệu ra web để hiển thị 
        socketio.emit('sensor_data', {
            'temp_panel': round(temp_panel,2),
            'temp_env': round(temp_env,2),
            'humidity': humidity,
            'lux': round(lux, 0),
            'health_score': health_score, # Dữ liệu từ thuật toán mới
            'p_actual': round(p_actual_W, 2),
            'p_theory': round(p_theory_val, 2),
            'g_meas': round(g_meas, 2),             # Gửi thêm Bức xạ tính toán để hiển thị nếu cần
            'pump_status': pump_status,
            'pump_mode': pump_mode,      
            'pump_reason': pump_reason, 

            'hotspot_risk': hotspot_result['risk_percent'],
            'hotspot_status': hotspot_result['status'],
            'hotspot_reason': hotspot_result['reason'],
            'hotspot_action': hotspot_result['action'],
            'hotspot_delta_t': hotspot_result['delta_t'],
            'hotspot_type': hotspot_type,
            'dust_level': round(dust_level, 1)
        })
        # Safety override khi DANGER: dùng format command thống nhất với hệ thống
        if hotspot_result['status'] == 'DANGER' and pump_status == 0:
            mqtt_client.publish(TOPIC_PUB, json.dumps({
                "command": "2",
                "type": "COOL",
                "source": "HOTSPOT_AI"
            }))
            pump_status = 1
            system_state["is_auto_running"] = True
            system_state["last_auto_start"] = time.time()










            socketio.emit('system_alert', {
                'level': 'CRITICAL',
                'message': f"🚨 AI phát hiện HOTSPOT nguy hiểm. Tự động bật phun làm mát. Lý do: {hotspot_result['reason']}"
            })
            save_history("HOTSPOT_AI", "BẬT", "HOTSPOT_DANGER", "HOTSPOT_AI")

    except ValueError as e:
        print(f" Lỗi dữ liệu không phải số: {e}")
    except Exception as e:
        print(f" Lỗi xử lý MQTT: {e}")

mqtt_client = mqtt.Client()
if MQTT_USERNAME: mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
#hàm gọi vad chạy giao thức MQTT
def run_mqtt():
    try:
        mqtt_client.connect(BROKER, PORT, 60)
        mqtt_client.loop_forever()
    except: pass









# KHỐI LOGIC: XỬ LÝ VIDEO CAMERA AI 


# 1. CẤU HÌNH NGUỒN CAMERA THÔNG MINH
# Nếu trong file .env có CAMERA_URL (VD: rtsp://admin:pass@192.168.1.10:554/1), nó sẽ dùng Camera thật.
# Nếu bỏ trống, hệ thống tự động fallback về video Demo.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_camera_url = os.getenv("CAMERA_URL", "").strip()

if env_camera_url:
    VIDEO_SOURCE = env_camera_url
    print(f"📷 [VISION AI] Đã kết nối luồng Camera thực tế: {VIDEO_SOURCE}")
else:
    VIDEO_SOURCE = os.path.join(BASE_DIR, "demo_solar.mp4")
    print(f"🎬 [VISION AI] Đang chạy chế độ Demo Video: {VIDEO_SOURCE}")

def generate_video_frames():
    """Hàm tạo luồng hình ảnh liên tục cho Camera AI trên Web"""
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    
    # Nếu không mở được video, trả về ảnh đen báo lỗi
    if not cap.isOpened():
        error_img = np.zeros((480, 854, 3), dtype=np.uint8)
        cv2.putText(error_img, f"ERROR: CANNOT LOAD CAMERA STREAM", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        ret, buffer = cv2.imencode('.jpg', error_img)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        return
    
    frame_count = 0
    last_alert_time = 0  # Biến chống spam cảnh báo
    ALERT_COOLDOWN = 60  # Thời gian chờ giữa 2 lần báo động (60 giây)

    while True:
        success, frame = cap.read()
        if not success:
            # Nếu là camera IP thật bị rớt mạng -> Cố gắng kết nối lại
            if env_camera_url:
                time.sleep(0.1)
                cap = cv2.VideoCapture(VIDEO_SOURCE)
                continue
            else:
                # Nếu là video demo hết -> Tua lại từ đầu
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            
        frame_count += 1
        
        # Resize nhẹ để mượt mà trên web
        frame = cv2.resize(frame, (854, 480))
        annotated_frame = frame.copy()

        warning_active = False

        # --- Thuật toán lọc đốm bẩn / phân chim ---
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_white = np.array([0, 0, 160])    
        upper_white = np.array([180, 50, 255]) 
        mask = cv2.inRange(hsv_frame, lower_white, upper_white)

        kernel = np.ones((5,5), np.uint8)
        mask_clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if 50 < area < 2000:
                x, y, w, h = cv2.boundingRect(contour)
                fake_prob = min(99, 75 + (int(area) % 24))
                
                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 165, 255), 2)
                
                if area > 300:
                    cv2.putText(annotated_frame, f"Bird Drop {fake_prob}%", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
                
                warning_active = True

        # --- LOGIC PHÁT CẢNH BÁO CHO HỆ THỐNG CHÍNH ---
        if warning_active:
            current_time = time.time()
            # Bắn cảnh báo xuống web nếu đã qua thời gian Cooldown (60s/lần)
            if current_time - last_alert_time > ALERT_COOLDOWN:
                socketio.emit('system_alert', {
                    'level': 'WARNING',
                    'type': 'camera_ai',
                    'message': '📷 CẢNH BÁO CAMERA: AI phát hiện có vết bẩn / phân chim chặn sáng trên tấm pin!'
                })
                last_alert_time = current_time

        # --- Vẽ HUD (Giao diện Kính ngắm trên góc) ---
        overlay = annotated_frame.copy()
        cv2.rectangle(overlay, (0, 0), (854, 60), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, annotated_frame, 0.4, 0, annotated_frame)
        
        cv2.putText(annotated_frame, "ASPC VISION AI SCANNING...", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        if warning_active:
            if frame_count % 10 < 5: 
                cv2.putText(annotated_frame, "WARNING: HOTSPOT RISK DETECTED!", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        else:
            cv2.putText(annotated_frame, "STATUS: PANELS CLEAR", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Chuyển thành chuỗi byte JPG
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        
        # Trả về từng frame cho Web
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')







@app.route('/video_feed')
def video_feed():
    """Route xuất luồng Video cho thẻ <img> trên giao diện hotspot.html"""
    return Response(generate_video_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# [API MỚI] Lưu thông số tấm pin từ trang Parameter
@app.route('/api/save_params', methods=['POST'])
def save_params_api():
    try:
        data = request.get_json(silent=True) or {}
        # Thêm lệnh để lấy bộ não ra
        mac_address = data.get('mac_address', 'ESP32_DEFAULT')
        engines = get_engines(mac_address)
        health_brain = engines["health"]
        optimizer_brain = engines["optimizer"]
        # 1. Thông số kỹ thuật
        p_max = data.get('p_max' , None)
        area = data.get('area' , None)
        if p_max is not None and area is not None:
            health_brain.update_user_params(float(p_max), float(area))

        # 2. Thông số kinh tế (MỚI)
        p_pump = data.get('p_pump' , None)       # Công suất bơm (W)
        monthly_kwh = data.get('monthly_kwh' , None) # Số điện tiêu thụ tháng (kWh)
        alpha_p = data.get('alpha_p' , None)     # Hệ số nhiệt (mặc định 0.4)
        
        if p_pump is not None and monthly_kwh is not None:
            # Nếu người dùng không nhập alpha, lấy mặc định 0.4
            a_p = float(alpha_p) if alpha_p is not None else float(getattr(optimizer_brain , "alpha_p" , 0.4))
            optimizer_brain.update_params(a_p, float(p_pump), float(monthly_kwh))
            
        return jsonify({"status": "success", "message": "Đã cập nhật cấu hình & Giá điện Bậc thang!"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500






#gọi API thời tiết
@app.route('/api/weather', methods=['GET'])
def get_weather_api():
    missing = []
    if not WEATHER_API_KEY:
        missing.append("WEATHER_API_KEY")
    if not WEATHER_LAT:
        missing.append("WEATHER_LAT")
    if not WEATHER_LON:
        missing.append("WEATHER_LON")
    if missing:
        return jsonify({
            "status": "error",
            "message": f"Thiếu cấu hình: {', '.join(missing)}. Hãy tạo file .env trong thư mục ASPC và điền giá trị."
        }), 400

    result = get_weather_cached()
    if result is None:
        return jsonify({
            "status": "error",
            "message": "Không lấy được dữ liệu thời tiết (kiểm tra API key, internet, hoặc giới hạn API)."
        }), 502
    return jsonify({"status": "success", "data": result})


# [API MỚI] NHẬN CẢNH BÁO TỪ TRẠM AI YOLO (CỔNG 5001)

@app.route('/api/camera_alert', methods=['POST'])
def camera_alert_api():
    try:
        data = request.get_json()
        if data:
            # Lấy thông tin lỗi YOLO gửi sang
            alert_type = data.get('type', 'LỖI KHÔNG XÁC ĐỊNH')
            confidence = data.get('confidence', 0)
            message = data.get('message', 'AI phát hiện vật cản bất thường!')
            
            # 1. Phát cảnh báo đỏ chót lên giao diện Web ngay lập tức
            socketio.emit('system_alert', {
                'level': 'CRITICAL',      # Báo động đỏ
                'type': 'camera_ai',      # Phân loại là lỗi từ Camera
                'issue_name': alert_type, # Tên lỗi (Ví dụ: Dusty, Bird Drop)
                'message': message,
                'confidence': confidence
            })
            
            # 2. Lưu vào Lịch sử hệ thống
            save_history("YOLO_VISION", "PHÁT HIỆN LỖI", alert_type, "CAMERA_AI")
            
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# [API MỚI] Lấy thông số hiện tại để hiển thị lên form
@app.route('/api/get_params', methods=['GET'])
def get_params_api():
    # Thêm 4 dòng để lấy bộ não ra
    mac_address = request.args.get('mac_address', 'ESP32_DEFAULT')
    engines = get_engines(mac_address)
    health_brain = engines["health"]
    optimizer_brain = engines["optimizer"]
    monthly_kwh_val = getattr(optimizer_brain, "monthly_kwh", None)
    if monthly_kwh_val is None:
        monthly_kwh_val = getattr(optimizer_brain, "monthly_consumption_kwh", 0)
    return jsonify({
        # Thông số kỹ thuật
        "p_max": health_brain.p_max,
        "area": health_brain.area,
        
        # Thông số kinh tế (MỚI)
        "p_pump": optimizer_brain.p_pump_cons,
        # Ước lượng ngược lại số kWh từ giá (Chỉ mang tính tham khảo vì ta lưu giá chứ không lưu kWh)
        # Tuy nhiên để đơn giản, ở bước này ta có thể trả về 0 hoặc lưu monthly_kwh vào biến riêng nếu muốn hiển thị chính xác.
        # Ở đây tôi trả về giá trị mặc định để tránh lỗi JS
        "monthly_kwh": monthly_kwh_val, 
        "alpha_p": optimizer_brain.alpha_p * 100 # Đổi lại về %
    })










# --- CƠ CHẾ BẢO VỆ TRANG (LOGIN REQUIRED) ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Nếu chưa đăng nhập -> Đẩy về trang Login và báo lỗi
        if 'user_id' not in session:
            flash("Bạn cần đăng nhập để truy cập hệ thống!", "danger")
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function







# --- TÌM VÀ THAY THẾ HÀM LOGIN CŨ BẰNG ĐOẠN NÀY ---
@app.route('/login', methods=['GET', 'POST'])
def login_page():
    # Nếu đã đăng nhập từ trước
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['avatar'] = user.avatar or ""
            session['tier'] = user.tier
            
            # [LOGIC PHÂN QUYỀN]: Chỉ định 'admin' làm sếp
            if user.username.lower() == 'admin0202@gmail.com':
                session['role'] = 'admin'
                return redirect(url_for('admin_dashboard'))
            else:
                session['role'] = 'customer'
                return redirect(url_for('dashboard'))
        else:
            flash("Tên đăng nhập hoặc mật khẩu không chính xác!", "danger")
            return redirect(url_for('login_page'))
            
    return render_template('login.html')

# --- DÁN THÊM ĐOẠN NÀY NGAY DƯỚI HÀM LOGIN ---
# ==========================================
# KHU VỰC SUPER ADMIN (COMMAND CENTER)
# ==========================================
# ==========================================
# API HỘP THƯ THÔNG BÁO (NOTIFICATION)
# ==========================================

# 1. ADMIN GỬI THÔNG BÁO TỚI KHÁCH HÀNG
@app.route('/api/admin/send_notification', methods=['POST'])
@login_required
def admin_send_notification():
    if session.get('role') != 'admin':
        return jsonify({"status": "error"}), 403
        
    data = request.json
    target_user_id = data.get('user_id', 'ALL') # Mặc định gửi tất cả
    message = data.get('message', '')
    msg_type = data.get('type', 'info')
    
    if message:
        # Lưu vào Database
        new_noti = Notification(user_id=str(target_user_id), message=message, type=msg_type)
        db.session.add(new_noti)
        db.session.commit()
        
        # Bắn realtime Socket qua Web ngay lập tức
        socketio.emit('new_notification', {
            'user_id': target_user_id,
            'message': message,
            'type': msg_type,
            'time': datetime.now().strftime("%H:%M")
        })
        return jsonify({"status": "success", "message": "Đã gửi thông báo!"})
    return jsonify({"status": "error"}), 400

# 2. KHÁCH HÀNG LẤY DANH SÁCH THÔNG BÁO CỦA MÌNH
@app.route('/api/user/get_notifications', methods=['GET'])
@login_required
def get_user_notifications():
    user_id = str(session.get('user_id'))
    # Lấy thông báo gửi riêng cho User này HOẶC gửi chung cho ALL
    notis = Notification.query.filter(
        (Notification.user_id == user_id) | (Notification.user_id == 'ALL')
    ).order_by(Notification.id.desc()).limit(10).all()
    
    data = [{
        "id": n.id,
        "message": n.message,
        "type": n.type,
        "is_read": n.is_read,
        "time": n.timestamp.strftime("%d/%m - %H:%M")
    } for n in notis]
    
    return jsonify({"status": "success", "data": data})




# KHU VỰC SUPER ADMIN (COMMAND CENTER) - BẢN FULL CHỨC NĂNG

@app.route('/admin')
@login_required
def admin_dashboard():
    # 1. Bức tường lửa: Chặn khách hàng vào trang Admin
    if session.get('role') != 'admin':
        flash("⛔ Lỗi: Khu vực quân sự, cấm xâm nhập!", "danger")
        return redirect(url_for('dashboard'))
        
    # 2. Lấy danh sách khách hàng (Quản lý CRM)
    users = User.query.filter(User.username != 'admin0202@gmail.com').all()
    
    # Tính toán doanh thu thực tế
    premium_count = sum(1 for u in users if u.tier == 'PREMIUM')
    pro_count = sum(1 for u in users if u.tier == 'PRO')
    revenue = (premium_count * 19.99) + (pro_count * 9.99)
    
    # 3. [TÍNH NĂNG MỚI] Thống kê dữ liệu IoT thực tế từ Database
    total_stations = Device.query.count() # Tổng số trạm IoT đang quản lý
    if total_stations == 0: total_stations = 1 # Mặc định luôn có ít nhất 1 trạm ESP32_DEFAULT
    
    total_records = SensorData.query.count() # Tổng số dòng dữ liệu cảm biến đã thu thập
    
    # 4. [TÍNH NĂNG MỚI] Lấy Log hệ thống thật (10 hành động gần nhất)
    recent_logs = CommandHistory.query.order_by(CommandHistory.id.desc()).limit(8).all()
    
    # Truyền toàn bộ dữ liệu siêu khủng này ra file HTML
    return render_template('admin.html', 
                           users=users, 
                           session_user=session.get('username'),
                           revenue=round(revenue, 2),
                           total_users=len(users),
                           total_stations=total_stations,
                           total_records=total_records,
                           recent_logs=recent_logs)

@app.route('/api/admin/upgrade_tier', methods=['POST'])
@login_required
def admin_upgrade_tier():
    if session.get('role') != 'admin':
        return jsonify({"status": "error", "message": "Không đủ thẩm quyền!"}), 403
        
    data = request.json
    user = User.query.get(data.get('user_id'))
    # TÌM ĐOẠN ĐỔI TIER CŨ VÀ SỬA THÀNH:
    if user:
        old_tier = user.tier
        user.tier = data.get('new_tier')
        
        # Tự động tạo tin nhắn thông báo
        auto_msg = f"🎉 Chúc mừng! Tài khoản của bạn đã được nâng cấp từ {old_tier} lên gói {user.tier} thành công."
        new_noti = Notification(user_id=str(user.id), message=auto_msg, type="success")
        db.session.add(new_noti)
        
        db.session.commit()
        
        # Bắn realtime sang Web khách
        socketio.emit('new_notification', {'user_id': str(user.id), 'message': auto_msg, 'type': 'success', 'time': 'Vừa xong'})
        
        return jsonify({"status": "success", "message": f"Đã cấp gói {user.tier}!"})


#





@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('reg_username')
    password = request.form.get('reg_password')
    
    # Check trùng tên
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash("Tên tài khoản này đã có người sử dụng!", "danger")
        return redirect(url_for('login_page'))
        
    if len(password) < 6:
        flash("Mật khẩu phải dài ít nhất 6 ký tự!", "danger")
        return redirect(url_for('login_page'))
        
    # Tạo acc mới
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
    new_user = User(username=username, password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    
    flash("Đăng ký thành công! Bạn có thể đăng nhập ngay.", "success")
    return redirect(url_for('login_page'))

@app.route('/logout')
def logout():
    session.clear() # Xóa phiên
    return redirect(url_for('home'))



# --- ROUTES GIAO DIỆN CHÍNH (ĐÃ KHÓA) ---
@app.route('/')
def home(): 
    return render_template('home_page.html')



@app.route('/index.html')
@login_required 
def dashboard(): 
    return render_template('index.html', avatar=session.get('avatar', ''), tier=session.get('tier', 'FREE'))
    
@app.route('/health.html')
@login_required
def health(): 
    return render_template('health.html', avatar=session.get('avatar', ''), tier=session.get('tier', 'FREE'))

@app.route('/history.html')
@login_required
def history(): 
    return render_template('history.html', avatar=session.get('avatar', ''), tier=session.get('tier', 'FREE'))

@app.route('/parameter.html')
@login_required
def parameter(): 
    return render_template('parameter.html', avatar=session.get('avatar', ''), tier=session.get('tier', 'FREE'))

@app.route('/hotspot.html')
@login_required
def hotspot_page(): 
    return render_template('hotspot.html', avatar=session.get('avatar', ''), tier=session.get('tier', 'FREE'))

@app.route('/weather.html')
@login_required
def weather_page(): 
    return render_template('weather.html', avatar=session.get('avatar', ''), tier=session.get('tier', 'FREE'))

@app.route('/profile.html')
@login_required
def profile_page():
    return render_template('profile.html', avatar=session.get('avatar', ''), tier=session.get('tier', 'FREE'))




# CÁC HÀM API DỮ LIỆU

@app.route('/api/get_history')
def get_history_api():
    try:
        records = CommandHistory.query.order_by(CommandHistory.id.desc()).limit(50).all()
        data = []
        for r in records:
            data.append({
                "id": r.id,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "user_id": r.user_id,
                "command": r.command,
                "action_type": r.action_type,
                "source": r.source
            })
        return jsonify(data)
    except Exception as e: 
        return jsonify([])

@app.route('/api/economic_report/<int:year>/<int:month>')
#Báo cáo kinh tế + Sức khỏe 
def get_economic_report_api(year, month):
    report = get_monthly_report(year, month)
    if "error" in report:
        return jsonify(report), 500
    #trả dạng phẳng
    return jsonify({
        "month": report.get("month"),
        "total_profit": report.get("economic", {}).get("total_profit", 0),
        "total_energy_saved": report.get("economic", {}).get("total_energy_saved", 0)
    })
    


# API QUẢN LÝ HỒ SƠ NGƯỜI DÙNG (PROFILE)

@app.route('/api/profile/update_tier', methods=['POST'])
@login_required
def update_tier():
    user = User.query.get(session['user_id'])
    new_tier = request.json.get('tier', 'FREE')
    user.tier = new_tier
    db.session.commit()
    session['tier'] = new_tier
    return jsonify({"status": "success", "message": f"Đã chuyển sang gói {new_tier}"})

@app.route('/api/profile/get', methods=['GET'])
@login_required
def get_profile():
    user = User.query.get(session['user_id'])
    return jsonify({
        "username": user.username,
        "full_name": user.full_name or "",
        "phone": user.phone or "",
        "address": user.address or "",
        "avatar": user.avatar or "",
        "last_password_change": user.last_password_change.strftime("%d/%m/%Y") if user.last_password_change else "Chưa từng đổi"
    })

@app.route('/api/profile/update_info', methods=['POST'])
@login_required
def update_info():
    user = User.query.get(session['user_id'])
    data = request.json
    user.full_name = data.get('full_name')
    user.phone = data.get('phone')
    user.address = data.get('address')
    db.session.commit()
    return jsonify({"status": "success", "message": "Cập nhật thông tin thành công!"})

@app.route('/api/profile/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({"status": "error", "message": "Không tìm thấy file!"}), 400
    
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Chưa chọn file!"}), 400

    # Lưu file
    filename = secure_filename(f"user_{session['user_id']}_{int(time.time())}.png")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Cập nhật DB
    user = User.query.get(session['user_id'])
    user.avatar = filename
    db.session.commit()
    
    session['avatar'] = filename # Lưu vào session để dùng chung
    return jsonify({"status": "success", "avatar_url": f"/static/uploads/{filename}"})

@app.route('/api/profile/change_password', methods=['POST'])
@login_required
def change_password():
    user = User.query.get(session['user_id'])
    data = request.json
    old_pass = data.get('old_password')
    new_pass = data.get('new_password')

    # 1. Kiểm tra mật khẩu cũ
    if not check_password_hash(user.password_hash, old_pass):
        return jsonify({"status": "error", "message": "Mật khẩu cũ không chính xác!"})

    # 2. KIỂM TRA ĐIỀU KIỆN 30 NGÀY
    if user.last_password_change:
        days_passed = (datetime.utcnow() - user.last_password_change).days
        if days_passed < 30:
            return jsonify({"status": "error", "message": f"Bạn vừa đổi mật khẩu gần đây! Vui lòng đợi {30 - days_passed} ngày nữa."})

    # 3. Đổi pass thành công
    user.password_hash = generate_password_hash(new_pass, method='pbkdf2:sha256')
    user.last_password_change = datetime.utcnow()
    db.session.commit()
    
    return jsonify({"status": "success", "message": "Đổi mật khẩu thành công!"})



# [MỚI] Xử lý chuyển chế độ
@socketio.on('switch_mode')
def handle_switch_mode(data):
    global system_state
    new_mode = data.get('mode', 'MANUAL')
    system_state['mode'] = new_mode
    print(f"🔄 CHUYỂN CHẾ ĐỘ: {new_mode}")
    emit('mode_update', {'mode': new_mode}, broadcast=True)
    save_history("SYSTEM", "CHUYỂN_CHẾ_ĐỘ", new_mode, "SYSTEM")

# [MỚI] Client mới vào thì gửi chế độ hiện tại
@socketio.on('request_current_mode')
def handle_request_mode(data=None):
    emit('mode_update', {'mode': system_state['mode']})

@socketio.on('send_control')
def handle_control(data):
    global system_state
    
    # 1. Kiểm tra chế độ
    if system_state['mode'] != 'MANUAL':
        #  NẾU KHÔNG PHẢI THỦ CÔNG -> TỪ CHỐI
        print(f"⚠️ TỪ CHỐI LỆNH: Đang ở chế độ {system_state['mode']}")
        
        # Gửi thông báo ngược lại cho Web hiển thị
        emit('system_alert', {
            'level': 'warning', 
            'message': f' KHÔNG THỂ ĐIỀU KHIỂN! Hệ thống đang ở chế độ {system_state["mode"]}. Hãy chuyển sang THỦ CÔNG.'
        })
        return # Thoát hàm, không thực hiện lệnh
#  Ghi nhớ người dùng vừa bấm COOL hay CLEAN
    system_state['last_manual_type'] = data.get('type', 'COOL')
    # 2. Truyền tín hiệu bật/tắt (1/0) vào thẳng biến toàn cục cho Giả Lập đọc
    system_state['mock_pump'] = 1 if str(data.get('command')) == '2' else 0
    
    mqtt_client.publish(TOPIC_PUB, json.dumps(data))
    
    cmd_text = "BẬT" if str(data['command']) == '2' else "TẮT"
    save_history(data.get('user_id'), cmd_text, data.get('type'), "WEB")



@app.route('/favicon.ico')
def favicon(): return "", 204

@app.route('/<path:filename>')
def serve_static(filename): 
    if filename.endswith('.html'):
        try: return render_template(filename)
        except: return "File not found", 404
    return "", 404










# --- GIẢ LẬP THÔNG MINH (SMART SIMULATION) ---
def run_simulation():
    print("🌊 [SIMULATION] KÍCH HOẠT CHẾ ĐỘ 'LÀM MÁT CỰC MẠNH'...")
    print("   - Mục tiêu: Tạo ra sự sụt giảm nhiệt độ rõ rệt để AI dễ học.")
    
    # Cấu hình thời gian
    virtual_hour = 10.0 # Bắt đầu lúc 10h trưa cho nắng to luôn
    
    # Trạng thái ban đầu
    sim_state = {
        'temp_panel': 55.0,  # Bắt đầu nóng luôn
        'temp_env': 32.0,
        'lux': 80000,
        'pump_status': 0,
        'humidity': 60
    }

    # CẤU HÌNH VẬT LÝ (Đã tinh chỉnh để tác động Bơm cực mạnh)
    # Nhiệt độ tăng thêm do nắng (35 độ ở 100k Lux)
    SUN_HEATING_POWER = 35.0 
    
    # Tốc độ phản ứng (0.0 - 1.0)
    INERTIA_HEATING = 0.05  # Nóng lên từ từ (Khô)
    INERTIA_COOLING = 0.25  # Lạnh đi cực nhanh (Ướt) -> AI dễ nhận biết

    # Biến để nhận lệnh từ App
    global_command = None
    
    

    while True:
        if 'mock_pump' in system_state and system_state['mode'] == 'MANUAL':
            sim_state['pump_status'] = system_state['mock_pump']
        # 1. THỜI GIAN TRÔI (Chậm lại chút để kịp quan sát)
        virtual_hour += 0.05 
        if virtual_hour >= 24.0: virtual_hour = 0.0

        # 2. TẠO NẮNG (Giữ nắng to để test bơm)
        # Giả lập nắng từ 6h-18h, đỉnh 12h
        if 6 <= virtual_hour <= 18:
            angle = (virtual_hour - 6) * (math.pi / 12)
            base_lux = 100000 * math.sin(angle)
            sim_state['lux'] = int(base_lux + random.randint(-1000, 1000))
        else:
            sim_state['lux'] = 0

        # 3. NHIỆT ĐỘ MÔI TRƯỜNG
        sim_state['temp_env'] = 30 + 5 * math.sin((virtual_hour - 9) * (math.pi / 12))

        
        # [QUAN TRỌNG] LOGIC TÁC ĐỘNG CỦA BƠM
        
        
        # A. Tính nhiệt độ mục tiêu khi KHÔ (Chỉ có nắng)
        # T_dry = Môi trường + (Lux * Hệ số nóng)
        target_temp_dry = sim_state['temp_env'] + (sim_state['lux'] / 100000.0) * SUN_HEATING_POWER

        # B. Tính nhiệt độ mục tiêu khi ƯỚT (Có bơm)
        # T_wet = Môi trường + xíu nhiệt (Nước làm mát rất tốt, chỉ cao hơn MT 2 độ)
        target_temp_wet = sim_state['temp_env'] + 2.0

        # C. Quyết định hướng đi của nhiệt độ
        current = sim_state['temp_panel']
        
        if sim_state['pump_status'] == 1:
            # --- TRƯỜNG HỢP BẬT BƠM ---
            # Mục tiêu là T_wet (thấp)
            final_target = target_temp_wet
            # Tốc độ thay đổi nhanh (Nước dội vào là mát ngay)
            inertia = INERTIA_COOLING 
            
            # Hiệu ứng visual: Thêm độ ẩm giả lập tăng lên khi bơm bật
            sim_state['humidity'] = 95 
        else:
            # --- TRƯỜNG HỢP TẮT BƠM ---
            # Mục tiêu là T_dry (cao)
            final_target = target_temp_dry
            # Tốc độ thay đổi chậm (Cần thời gian để khô nước và nóng lại)
            inertia = INERTIA_HEATING
            
            # Độ ẩm giảm dần về bình thường
            if sim_state['humidity'] > 60: sim_state['humidity'] -= 1

        # D. Cập nhật nhiệt độ theo công thức quán tính
        sim_state['temp_panel'] = current + (final_target - current) * inertia

        



       
        # 5. TÍNH CÔNG SUẤT (Tuân thủ định luật NREL để kiểm thử Nhiệt độ ảo)
        P_max_sim = 5000.0 # Giả lập hệ thống 5kW
        alpha_p_sim = -0.004 # Hệ số nhiệt (Gamma)
        
        if sim_state['lux'] > 0:
            g_w_m2 = sim_state['lux'] / 116.0
            p_theory_stc = (g_w_m2 / 1000.0) * P_max_sim
            
            # Tính công suất bị suy hao do nhiệt độ (Công thức thuận)
            loss_factor = alpha_p_sim * (sim_state['temp_panel'] - 25.0)
            sim_power = p_theory_stc * (1.0 + loss_factor)
            
            if sim_power < 0: sim_power = 0.0
        else:
            sim_power = 0.0
        # 6. TÍNH U VÀ I (MÔ PHỎNG VẬT LÝ) ĐỂ TEST HỆ THỐNG CẢNH BÁO
        if sim_power > 0:
            sim_voltage = 45.0 + random.uniform(-1.0, 1.0) # Áp giả định 45V
            sim_current = sim_power / sim_voltage
        else:
            sim_voltage = 0.0
            sim_current = 0.0
# BẮT ĐẦU CHÈN THÊM ĐỂ WEB HIỂN THỊ ĐỦ THÔNG SỐ
       

        # 1. Bơm dữ liệu AI dự báo (Tạo cái đuôi nét đứt trên biểu đồ)
        mock_pred_temp = sim_state['temp_panel'] + (target_temp_dry - sim_state['temp_panel']) * 0.2
        socketio.emit('ai_data', {'ai': {'pred_temp_15min': round(mock_pred_temp, 2)}})

              
        # LOGIC XÁC ĐỊNH BƠM THEO CHẾ ĐỘ THỰC TẾ
        
        pump_mode = "IDLE"
        pump_reason = "Đang chờ"
        
        current_lux = sim_state['lux']
        current_temp_panel = sim_state['temp_panel']
        health_score = random.uniform(80.0, 100.0)
        
        # Đọc trực tiếp biến system_state["mode"] do người dùng bấm trên Web
        if system_state["mode"] in ["AUTO", "SMART_ECO"]:
            if health_score < 85 and current_lux > 20000 and current_temp_panel < 50.0:
                sim_state['pump_status'] = 1  
                pump_mode = "CLEANING"
                pump_reason = "Rửa trôi bề mặt (Bụi/Phân chim)"
                
            elif current_temp_panel >= 45.0:
                sim_state['pump_status'] = 1  
                pump_mode = "COOLING"
                pump_reason = "Phun sương hạ nhiệt độ"
                
            else:
                sim_state['pump_status'] = 0  
                pump_mode = "IDLE"
                pump_reason = "Hệ thống tối ưu"
        
                    
        else:
            # CHẾ ĐỘ THỦ CÔNG (MANUAL)
             if sim_state['pump_status'] == 1:
                # Đọc chữ CLEAN từ hệ thống chính
                if system_state.get('last_manual_type') == 'CLEAN':
                    pump_mode = "CLEANING"
                    pump_reason = "Người dùng bật Làm Sạch"
                else:
                    pump_mode = "COOLING"
                    pump_reason = "Người dùng bật Làm Mát"
             else:
                pump_mode = "IDLE"
                pump_reason = "Đã tắt (Thủ công)"



        # 2. Bơm dữ liệu Kinh tế ảo (Để 2 thẻ màu xanh lá + cam nó nhảy)
        socketio.emit('efficiency_data', {
            "x_today_kwh": round(random.uniform(2.5, 5.0), 3),
            "y_today_vnd": int(random.uniform(50000, 120000))
        })
        # GỬI DỮ LIỆU ĐI
        fake_payload = {
            'lux_ref': int(sim_state['lux']),
            'temp_panel': round(sim_state['temp_panel'], 2),
            'temp_env': round(sim_state['temp_env'], 2),
            'humidity': int(sim_state['humidity']),
            'wind_speed': 2.5,
            'pump_status': sim_state['pump_status'],
            'pump_mode': pump_mode,       
            'pump_reason': pump_reason,   
            'power': round(sim_power, 2),
            'voltage': round(sim_voltage, 2), 
            'current': round(sim_current, 2)  
        }
        
        # Gọi on_message giả lập
        class MockMsg:
            payload = json.dumps(fake_payload).encode('utf-8')
        try:
            on_message(None, None, MockMsg())
        except: pass
       
        # KẾT THÚC CHÈN THÊM
        



        # LOG MÀU MÈ ĐỂ DỄ NHÌN
        status_icon = "💦 MÁT" if sim_state['pump_status'] == 1 else "🔥 NÓNG"
        print(f"[{status_icon}] Temp: {fake_payload['temp_panel']:5.2f}°C (Target: {final_target:.1f}) | Lux: {fake_payload['lux_ref']}")

        # Kiểm tra nếu AI ra lệnh (đọc biến global hoặc logic Smart Eco)
        # Ở đây ta giả lập: Cứ nóng quá 55 độ thì tự bật, mát dưới 35 thì tự tắt (Hardcode test)
       
        # if sim_state['temp_panel'] > 60: sim_state['pump_status'] = 1
        # if sim_state['temp_panel'] < 35: sim_state['pump_status'] = 0

        time.sleep(2)
















#from flask_cors import CORS
#app = Flask(__name__)
#CORS(app) # Dòng này cực kỳ quan trọng để mở cổng kết nối





if __name__ == '__main__':
    # 1. Chạy luồng MQTT thực
    threading.Thread(target=run_mqtt, daemon=True).start()
    
    # 2. Nếu đang chế độ giả lập -> Chạy luồng giả lập
    if SIMULATION_MODE:
        threading.Thread(target=run_simulation, daemon=True).start()
        


    # Render sẽ cấp cổng qua biến môi trường PORT
    port = int(os.environ.get("PORT", 5000))
    
    
    host = "0.0.0.0" if os.environ.get("RENDER") else "127.0.0.1"

    print(f"🚀 ASPC đang 'cất cánh' tại http://{host}:{port}")
    
    # Chạy server (Bỏ cái _find_free_port đi cho đỡ lỗi cổng)
    socketio.run(app, host=host, port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
