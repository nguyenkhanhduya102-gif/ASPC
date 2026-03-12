import json
import sqlite3
import datetime
import threading
import ssl
import math
import os
import time
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()
import random 
from flask import request, jsonify
from collections import deque
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
from ai_engine import SolarLSTM 
from health_engine import SolarHealthEngine
from optimizer import SolarOptimizer

# --- CẤU HÌNH ---
DB_NAME = "aspc_history.db"
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "False").lower() == "true"
# MQTT CẤU HÌNH KẾT NỐI (đọc từ biến môi trường)
BROKER = os.getenv("MQTT_BROKER", "localhost")
PORT = int(os.getenv("MQTT_PORT", "8883"))
TOPIC_SUB = os.getenv("MQTT_TOPIC_SUB", "aspc/data")
TOPIC_PUB = os.getenv("MQTT_TOPIC_PUB", "aspc/control")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

K_FACTOR = 0.00015
TEMP_COEFF = 0.0045
TEMP_STD = 25.0

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
# --- BIẾN TÍCH LŨY NĂNG LƯỢNG ---
energy_state = {
    "E_real_today": 0.0,
    "E_no_cool_today": 0.0,
    "E_real_month": 0.0,
    "E_no_cool_month": 0.0,
    "last_day": datetime.date.today().day,
    "last_month": datetime.date.today().month
}
app = Flask(__name__, static_folder='static', template_folder='static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key-please-change')
socketio = SocketIO(app, cors_allowed_origins="*")

# --- DATABASE & AI (GIỮ NGUYÊN) ---
def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp TEXT, user_id TEXT, command TEXT, action_type TEXT, source TEXT)''')
        conn.commit()
        conn.close()
    except: pass

init_db()
print("🧠 Đang khởi tạo AI Engine...")
ai_brain = SolarLSTM()
print("❤️ Đang khởi tạo Health Engine...")
health_brain = SolarHealthEngine()
print("💰 Đang khởi tạo Optimizer Engine...")
optimizer_brain = SolarOptimizer()

# --- [MỚI] QUẢN LÝ NĂNG LƯỢNG & HIỆU QUẢ ---
class EnergyManager:
    def __init__(self):
        self.last_update_time = time.time()
        
        # Biến tích lũy Hôm nay
        self.today_date = datetime.datetime.now().date()
        self.e_real_today = 0.0      # Wh thực tế
        self.e_no_cool_today = 0.0   # Wh giả định nếu không làm mát
        
        # Biến tích lũy Tháng này
        self.current_month = datetime.datetime.now().month
        self.e_real_month = 0.0
        self.e_no_cool_month = 0.0

    def reset_counters_if_needed(self):
        now = datetime.datetime.now()
        
        # Reset ngày
        if now.date() != self.today_date:
            self.e_real_today = 0.0
            self.e_no_cool_today = 0.0
            self.today_date = now.date()
            
        # Reset tháng
        if now.month != self.current_month:
            self.e_real_month = 0.0
            self.e_no_cool_month = 0.0
            self.current_month = now.month

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
        # B1: Dùng AI dự báo nhiệt độ tấm pin nếu tắt bơm (Pump=0)
        # Lưu ý: predict_scenario trả về nhiệt độ dự báo 5 phút tới, ta dùng nó làm nhiệt độ trung bình
        pred_temp_no_cool = ai_brain.predict_scenario(0) 
        
        if pred_temp_no_cool is None:
            # Fallback nếu AI chưa chạy: Giả sử nóng hơn môi trường 10-20 độ tùy nắng
            pred_temp_no_cool = temp_env + (lux / 4000) 

        # B2: Tính công suất giả định (Công thức vật lý tấm pin)
        # P = P_max * (Lux/100000) * [1 + alpha * (T - 25)]
        # Đây là công suất lý thuyết tại nhiệt độ nóng đó
        
        # Tỷ lệ cường độ sáng (Giả sử 100k lux đạt chuẩn)
        irradiance_ratio = lux / 100000.0 if lux > 0 else 0
        
        # Hệ số suy giảm do nhiệt (alpha thường là âm, ví dụ -0.004)
        # Trong optimizer.py bạn dùng alpha dương (0.004) rồi trừ, ở đây ta dùng logic tương tự
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
# --- DATABASE HELPERS ---
def save_history(user, cmd, action_type, source):
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO history (timestamp, user_id, command, action_type, source) VALUES (?, ?, ?, ?, ?)",
                  (now, user, cmd, action_type, source))
        conn.commit()
        conn.close()
    except: pass

# Hàng đợi để lưu 5 giá trị nhiệt độ gần nhất
temp_history = deque(maxlen=5) 

def get_smooth_temp(raw_temp):
    temp_history.append(raw_temp)
    # Trả về trung bình cộng
    return sum(temp_history) / len(temp_history)
# --- [LOGIC QUAN TRỌNG] KIỂM TRA & RA QUYẾT ĐỊNH ---
def check_system_decision(current_temp, lux, p_max, pump_status):
    global system_state
    current_time = time.time()
    
    # 1. Dự báo nhiệt độ cơ bản (cho Auto/Manual cũ)
    ai_result = ai_brain.predict()
    pred_temp_basic = ai_result['pred_temp_5min'] if ai_result else current_temp

    # ==========================================================
    # CHẾ ĐỘ 1: SMART ECO (TỐI ƯU KINH TẾ & AN TOÀN)
    # ==========================================================
    if system_state["mode"] == "SMART_ECO":
        # A. AI Dự báo 2 kịch bản tương lai
        pred_off = ai_brain.predict_scenario(0) # Nếu Tắt bơm
        pred_on = ai_brain.predict_scenario(1)  # Nếu Bật bơm

        # Fallback nếu AI chưa đủ dữ liệu (Dùng logic thô)
        if pred_off is None: pred_off = current_temp + 0.5
        if pred_on is None: pred_on = current_temp - 2.0

        # B. Tính toán G thực tế (dựa vào hệ số k đã học)
        g_meas = lux * health_brain.k_factor

        # C. Gọi Optimizer tính bài toán kinh tế
        should_run, delta_e, profit, reason = optimizer_brain.calculate_decision(
            g_meas, p_max, pred_off, pred_on
        )

        # D. Thực thi quyết định
        if should_run:
            # Nếu Optimizer bảo BẬT
            if pump_status == 0 and not system_state["is_auto_running"]:
                print(f"💰 SMART: Bật bơm. {reason}")
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
                
                is_cool_enough = current_temp < (safe_limit - 3.0) 
                
                if run_duration > MIN_RUN_TIME:
                    if is_cool_enough:
                        print(f"💰 SMART: Tắt bơm. {reason}")
                        mqtt_client.publish(TOPIC_PUB, json.dumps({"command": "0", "type": "COOL", "source": "SMART_ECO"}))
                        system_state["is_auto_running"] = False
                        socketio.emit('system_alert', {'level': 'info', 'message': f'SMART: Đã mát ({current_temp:.1f}°C). Tắt bơm tiết kiệm.'})
                        save_history("SMART_ECO", "TẮT", "Tối ưu kinh tế", "SMART_ECO")
                    else:
                        # Nếu chưa đủ mát thì KHÔNG TẮT, dù đang lỗ
                        pass
        # Gửi dữ liệu kinh tế để vẽ biểu đồ (nếu cần)
        socketio.emit('economic_data', {'profit': profit, 'delta_e': delta_e, 'reason': reason})

    # ==========================================================
    # CHẾ ĐỘ 2: AUTO (LOGIC CŨ - DỰA VÀO NGƯỠNG NHIỆT)
    # ==========================================================
    elif system_state["mode"] == "AUTO":
        # A. Logic BẬT
        if pred_temp_basic >= TEMP_THRESHOLD_HIGH:
            if system_state["warning_start_time"] is None:
                system_state["warning_start_time"] = current_time
                socketio.emit('system_alert', {'level': 'warning', 'message': f'AUTO: Dự báo {pred_temp_basic:.1f}°C. Chuẩn bị bật...'})

            elapsed = current_time - system_state["warning_start_time"]
            if elapsed > AUTO_DELAY_SECONDS and pump_status == 0 and not system_state["is_auto_running"]:
                mqtt_client.publish(TOPIC_PUB, json.dumps({"command": "2", "type": "COOL", "source": "AI_AUTO"}))
                system_state["is_auto_running"] = True
                system_state["last_auto_start"] = current_time
                save_history("AI_AUTO", "BẬT", "Quá nhiệt", "AUTO")
                socketio.emit('system_alert', {'level': 'danger', 'message': 'AUTO: Đã bật bơm bảo vệ!'})

        # B. Logic TẮT
        elif system_state["is_auto_running"]:
            run_duration = current_time - system_state["last_auto_start"]
            if current_temp < TEMP_THRESHOLD_SAFE and run_duration > MIN_RUN_TIME:
                mqtt_client.publish(TOPIC_PUB, json.dumps({"command": "0", "type": "COOL", "source": "AI_AUTO"}))
                system_state["is_auto_running"] = False
                system_state["warning_start_time"] = None
                save_history("AI_AUTO", "TẮT", "Đã mát", "AUTO")
                socketio.emit('system_alert', {'level': 'success', 'message': 'AUTO: Nhiệt độ ổn định. Tắt bơm.'})

    # ==========================================================
    # CHẾ ĐỘ 3: MANUAL (CHỈ ĐƯA RA LỜI KHUYÊN)
    # ==========================================================
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
# --- MQTT HANDLERS ---
def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC_SUB)

def on_message(client, userdata, msg):
    global system_state
    try:
        raw_msg = msg.payload.decode('utf-8')
        # [DEBUG] In ra để xem ESP32 gửi cái gì lên
        print(f"📥 ESP32 Payload: {raw_msg}") 
        
        data = json.loads(raw_msg)
        # 1. ÉP KIỂU DỮ LIỆU AN TOÀN (Tránh lỗi String/None)
        # Xử lý Nhiệt độ (Có lọc nhiễu)
        raw_temp_panel = data.get('temp_panel', 0)
        temp_panel = get_smooth_temp(raw_temp_panel) # Dùng giá trị đã làm mượt
        
        temp_env = float(data.get('temp_env', 0))
        humidity = float(data.get('humidity', 0))
        lux = float(data.get('lux_ref', 0))
        p_actual_W = float(data.get('power', 0))
        
        # Xử lý Trạng thái bơm (Quan trọng: Chấp nhận cả 1, "1", "true", "ON")
        raw_pump = data.get('pump_status', 0)
        pump_status = 1 if str(raw_pump).upper() in ['1', 'TRUE', 'ON'] else 0
        # ---------------------------------------------------------
        # [MỚI] QUY TRÌNH TÍNH SỨC KHỎE "TỰ HỌC"
        # ---------------------------------------------------------
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
        # Cập nhật AI (Dùng nhiệt độ đã làm mượt để AI không bị loạn)
        data_package = [lux, temp_panel, temp_env, humidity, pump_status]
        ai_brain.update_data(data_package)
        # Kiểm tra logic điều khiển (Gửi temp_panel đã mượt vào)
        check_system_decision(temp_panel, lux, health_brain.p_max, pump_status)

        ai_result = ai_brain.predict()
        if ai_result:
            socketio.emit('ai_data', {'ai': ai_result})

        # 3. Gửi dữ liệu ra Web
        socketio.emit('sensor_data', {
            'temp_panel': round(temp_panel,2),
            'temp_env': round(temp_env,2),
            'humidity': humidity,
            'lux': round(lux, 0),
            'health_score': health_score, # Dữ liệu từ thuật toán mới
            'p_actual': round(p_actual_W, 2),
            'p_theory': round(p_theory_val, 2),
            'g_meas': round(g_meas, 2),             # Gửi thêm Bức xạ tính toán để hiển thị nếu cần
            'pump_status': pump_status
        })
    except ValueError as e:
        print(f"❌ Lỗi dữ liệu không phải số: {e}")
    except Exception as e:
        print(f"❌ Lỗi xử lý MQTT: {e}")

mqtt_client = mqtt.Client()
if MQTT_USERNAME: mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def run_mqtt():
    try:
        mqtt_client.connect(BROKER, PORT, 60)
        mqtt_client.loop_forever()
    except: pass
# [API MỚI] Lưu thông số tấm pin từ trang Parameter
@app.route('/api/save_params', methods=['POST'])
def save_params_api():
    try:
        data = request.json
        
        # 1. Thông số kỹ thuật
        p_max = data.get('p_max')
        area = data.get('area')
        if p_max and area:
            health_brain.update_user_params(p_max, area)

        # 2. Thông số kinh tế (MỚI)
        p_pump = data.get('p_pump')       # Công suất bơm (W)
        monthly_kwh = data.get('monthly_kwh') # Số điện tiêu thụ tháng (kWh)
        alpha_p = data.get('alpha_p')     # Hệ số nhiệt (mặc định 0.4)
        
        if p_pump and monthly_kwh:
            # Nếu người dùng không nhập alpha, lấy mặc định 0.4
            a_p = alpha_p if alpha_p else 0.4
            optimizer_brain.update_params(a_p, p_pump, monthly_kwh)
            
        return jsonify({"status": "success", "message": "Đã cập nhật cấu hình & Giá điện Bậc thang!"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
# [API MỚI] Lấy thông số hiện tại để hiển thị lên form
@app.route('/api/get_params', methods=['GET'])
def get_params_api():
    return jsonify({
        # Thông số kỹ thuật
        "p_max": health_brain.p_max,
        "area": health_brain.area,
        
        # Thông số kinh tế (MỚI)
        "p_pump": optimizer_brain.p_pump_cons,
        # Ước lượng ngược lại số kWh từ giá (Chỉ mang tính tham khảo vì ta lưu giá chứ không lưu kWh)
        # Tuy nhiên để đơn giản, ở bước này ta có thể trả về 0 hoặc lưu monthly_kwh vào biến riêng nếu muốn hiển thị chính xác.
        # Ở đây tôi trả về giá trị mặc định để tránh lỗi JS
        "monthly_kwh": 0, 
        "alpha_p": optimizer_brain.alpha_p * 100 # Đổi lại về %
    })
# --- ROUTES & SOCKET EVENTS ---
@app.route('/')
def home(): return render_template('home_page.html')
@app.route('/index.html')
def dashboard(): return render_template('index.html')
@app.route('/health.html')
def health(): return render_template('health.html')
@app.route('/history.html')
def history(): return render_template('history.html')
@app.route('/parameter.html')
def parameter(): return render_template('parameter.html')
@app.route('/api/get_history')
def get_history_api():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM history ORDER BY id DESC LIMIT 50")
        return json.dumps([dict(row) for row in c.fetchall()])
    except: return "[]"

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
def handle_request_mode():
    emit('mode_update', {'mode': system_state['mode']})

@socketio.on('send_control')
def handle_control(data):
    global system_state
    
    # 1. Kiểm tra chế độ
    if system_state['mode'] != 'MANUAL':
        # ⛔ NẾU KHÔNG PHẢI THỦ CÔNG -> TỪ CHỐI
        print(f"⚠️ TỪ CHỐI LỆNH: Đang ở chế độ {system_state['mode']}")
        
        # Gửi thông báo ngược lại cho Web hiển thị
        emit('system_alert', {
            'level': 'warning', 
            'message': f'⛔ KHÔNG THỂ ĐIỀU KHIỂN! Hệ thống đang ở chế độ {system_state["mode"]}. Hãy chuyển sang THỦ CÔNG.'
        })
        return # Thoát hàm, không thực hiện lệnh

    # 2. NẾU LÀ THỦ CÔNG -> THỰC HIỆN BÌNH THƯỜNG
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

    # Hàm giả lập nhận lệnh (Cần gắn vào hệ thống chính nếu cần)
    def mock_command_receiver(cmd):
        nonlocal global_command
        global_command = cmd

    while True:
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

        # -----------------------------------------------------------
        # [QUAN TRỌNG] LOGIC TÁC ĐỘNG CỦA BƠM
        # -----------------------------------------------------------
        
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

        # -----------------------------------------------------------
        # 5. TÍNH CÔNG SUẤT (Để thấy hiệu quả kinh tế)
        sim_power = 0
        if sim_state['lux'] > 0:
            # Hiệu suất: Cứ nóng 1 độ (trên 25) thì mất 0.5% công suất
            loss = (sim_state['temp_panel'] - 25) * 0.005
            eff = 1.0 - loss
            if eff < 0.5: eff = 0.5
            sim_power = (sim_state['lux']/1000.0) * 0.5 * eff # Công thức giả định P=50W

        # -----------------------------------------------------------
        # GỬI DỮ LIỆU ĐI
        fake_payload = {
            'lux_ref': int(sim_state['lux']),
            'temp_panel': round(sim_state['temp_panel'], 2),
            'temp_env': round(sim_state['temp_env'], 2),
            'humidity': int(sim_state['humidity']),
            'pump_status': sim_state['pump_status'],
            'power': round(sim_power, 2)
        }
        
        # Gọi on_message giả lập
        class MockMsg:
            payload = json.dumps(fake_payload).encode('utf-8')
        try:
            on_message(None, None, MockMsg())
        except: pass
        
        # LOG MÀU MÈ ĐỂ DỄ NHÌN
        status_icon = "💦 MÁT" if sim_state['pump_status'] == 1 else "🔥 NÓNG"
        print(f"[{status_icon}] Temp: {fake_payload['temp_panel']:5.2f}°C (Target: {final_target:.1f}) | Lux: {fake_payload['lux_ref']}")

        # Kiểm tra nếu AI ra lệnh (đọc biến global hoặc logic Smart Eco)
        # Ở đây ta giả lập: Cứ nóng quá 55 độ thì tự bật, mát dưới 35 thì tự tắt (Hardcode test)
        # Bạn có thể bỏ đoạn này nếu muốn test bằng nút bấm trên Web
        # if sim_state['temp_panel'] > 60: sim_state['pump_status'] = 1
        # if sim_state['temp_panel'] < 35: sim_state['pump_status'] = 0

        time.sleep(1.0)
if __name__ == '__main__':
    # 1. Chạy luồng MQTT thực
    threading.Thread(target=run_mqtt, daemon=True).start()
    
    # 2. Nếu đang chế độ giả lập -> Chạy luồng giả lập
    if SIMULATION_MODE:
        threading.Thread(target=run_simulation, daemon=True).start()
        
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    print(f"🚀 Server ASPC khởi chạy tại http://localhost:{port}")
    
    # Chạy Flask Server
    socketio.run(app, host=host, port=port, debug=True, use_reloader=False)