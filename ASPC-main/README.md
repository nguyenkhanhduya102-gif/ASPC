# ☀️ ASPC Pro - Hệ Thống Trí Tuệ Nhân Tạo Tối Ưu Điện Mặt Trời
> Phiên bản Doanh nghiệp (Enterprise) - Tích hợp AI Dự báo, Computer Vision (Camera AI), Cảm biến ảo NREL và Tối ưu Kinh tế.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-lightgrey.svg)](https://flask.palletsprojects.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Vision_AI-green.svg)](https://opencv.org/)
[![MQTT](https://img.shields.io/badge/MQTT-HiveMQ-orange.svg)](https://www.hivemq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌟 Tóm tắt Phiên bản Pro (Có gì mới?)

ASPC Pro không chỉ là một hệ thống bật/tắt bơm đơn thuần, mà là một **trợ lý vận hành năng lượng** toàn diện:
- 👁️ **Vision AI (Camera Security):** Tự động phân tích luồng Video/RTSP bằng OpenCV để phát hiện phân chim, bụi bẩn, lá cây che khuất.
- 🌡️ **Cảm biến nhiệt độ Ảo (NREL):** Loại bỏ hoàn toàn cảm biến nhiệt bề mặt vật lý (hay hỏng). Tính toán ước lượng dựa trên học chuyển giao giai đoạn và mô hình AI tại biên.
- 💦 **Quản lý Bơm Kép (Dual Pump):** Điều khiển độc lập hệ thống **Phun sương (Làm mát)** và **Xịt rửa áp lực cao (Làm sạch)** dựa trên phân tích điểm nóng (Hotspot).
- ⛅ **Tích hợp Thời tiết (Weather API):** AI tự động kiểm tra xác suất mưa trong 3h tới để ra quyết định *Ngưng xịt nước* nhằm tiết kiệm chi phí.
- 🔐 **Multi-tenant & Security:** Hệ thống cơ sở dữ liệu SQLAlchemy hỗ trợ Đăng nhập, Đăng ký, Phân quyền người dùng (Free/Pro) và quản lý nhiều trạm ESP32 cùng lúc.

---

## 🏗️ Kiến trúc Hệ thống Tiên tiến

```text
[ CỤM PHẦN CỨNG & API ]                [ CỤM ĐỘNG CƠ TRÍ TUỆ NHÂN TẠO - AI ENGINES ]
 
 📷 IP Camera (RTSP) ────────┐         ┌──────────────────────────────────────────┐
                             │         │  👁️ Vision AI (OpenCV)                   │
 ⛅ OpenWeather API ────────┼────────▶│  🧠 SolarLSTM (Dự báo nhiệt 15 phút tới) │
                             │         │  ❤️ Health Engine (Tự học hiệu suất)     │
 📡 ESP32 (Các Trạm) ────────┘         │  🔥 Hotspot Detector (Phát hiện lỗi pin) │
    └─ Bức xạ sáng (Lux)               │  💰 Optimizer Engine (EVN Tiered Price)  │
    └─ Công suất, Dòng, Áp             └──────────────────────────────────────────┘
    └─ Nhiệt độ môi trường, Độ ẩm                            │
                                                             ▼
[ CƠ SỞ DỮ LIỆU SQLALCHEMY ] ◀─────── [ WEBSOCKET / FLASK SERVER ] ──────▶ [ WEB DASHBOARD PRO ]
    └─ Users (Auth, Avatars)                 (Xử lý Real-time)                 └─ Giao diện Bootstrap 5
    └─ Devices, Stations                                                       └─ Chart.js AI Projection
    └─ Sensor History & Logic Logs                                             └─ Bảng điều khiển Dual Pump
```

---

## ⚙️ Yêu cầu Hệ thống

- **Ngôn ngữ:** Python 3.8+
- **Database:** SQLite (Mặc định cho SQLAlchemy, có thể nâng cấp PostgreSQL/MySQL)
- **Thư viện AI/Xử lý ảnh:** `numpy`, `opencv-python`, `scikit-learn` (nếu dùng LSTM thật)
- **Khác:** Kết nối Internet (Để gọi OpenWeatherMap API & HiveMQ)

---

## 🚀 Cài đặt & Chạy dự án

### 1. Clone repository & Tạo môi trường ảo
```bash
git clone https://github.com/<your-username>/ASPC.git
cd ASPC

# Tạo & Kích hoạt venv (Khuyến nghị)
python -m venv venv
source venv/bin/activate  # Trên Windows dùng: venv\Scripts\activate
```

### 2. Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### 3. Cấu hình biến môi trường (`.env`)
Tạo file `.env` tại thư mục gốc và cấu hình các khoá sau:
```env
# Mật khẩu bảo mật cho Session/Login
SECRET_KEY=khoa_bi_mat_sieu_cap_aspc_2026

# Cấu hình MQTT
MQTT_BROKER=your-broker.hivemq.cloud
MQTT_PORT=8883
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password
MQTT_TOPIC_SUB=aspc/data
MQTT_TOPIC_PUB=aspc/control

# Cấu hình Thời Tiết (OpenWeatherMap)
WEATHER_API_KEY=your_openweathermap_api_key
WEATHER_LAT=10.762622
WEATHER_LON=106.660172

# Cấu hình Camera AI (Để trống nếu muốn chạy Video Demo)
CAMERA_URL=rtsp://admin:password@192.168.1.10:554/1

# Chế độ giả lập (Cho phép chạy không cần mạch thật)
SIMULATION_MODE=True
```

### 4. Khởi chạy Server
```bash
python app.py
```
> Trình duyệt sẽ chạy tại: **http://localhost:5000**
> Tài khoản mặc định hệ thống sẽ tự sinh nếu Database trống: `admin` / `123456`

---

## 🎮 Các Chế Độ Hoạt Động Cốt Lõi

| Chế độ | Biểu tượng | Chức năng hoạt động |
|---|:---:|---|
| **MANUAL** | 🕹️ | Chế độ Thủ công. Người dùng toàn quyền chọn BẬT/TẮT hệ thống Làm Mát hoặc Làm Sạch. AI chỉ đưa ra *Lời khuyên (Advice)* trên màn hình. |
| **AUTO** | 🤖 | Chế độ Tự động cơ bản. Dựa vào các ngưỡng nhiệt độ an toàn để kích hoạt hệ thống nhằm bảo vệ vật lý cho tấm pin. |
| **SMART ECO** | 🧠 | Chế độ Đặc quyền (VIP). AI tự động tính toán bài toán kinh tế: *Tiền điện tăng thêm nhờ giảm nhiệt* so với *Tiền điện chạy máy bơm*. Bơm chỉ chạy nếu sinh ra **LỢI NHUẬN (Profit > 0)**. Kết hợp kiểm tra Thời tiết để chặn bơm nếu sắp mưa. |

---

## 📡 Giao thức MQTT Payload (Từ ESP32)

Hệ thống hỗ trợ quản lý **Nhiều trạm (Multi-tenant)** thông qua địa chỉ MAC của từng ESP32.

**Payload mẫu ESP32 gửi lên (Topic: `aspc/data`):**
```json
{
  "mac_address": "ESP32_001",
  "temp_env": 34.5,
  "humidity": 60,
  "lux_ref": 95000,
  "power": 350.5,
  "voltage": 45.2,
  "current": 7.75,
  "pump_status": 0
}
```
*Lưu ý: `temp_panel` không còn bắt buộc gửi từ phần cứng vì Backend đã có Cảm biến Ảo NREL đảm nhiệm việc tính toán.*

---

## 🛡️ Tính năng Bảo vệ Phần cứng

ASPC Pro giám sát thời gian thực các thông số vật lý và kích hoạt tín hiệu Socket.IO để cảnh báo trên màn hình:
- ⚡ **Quá dòng / Ngắn mạch:** Dòng điện `I` vượt ngưỡng thiết kế.
- 📉 **Sụt áp / Hở mạch MC4:** Bức xạ sáng cao nhưng điện áp `U` tụt nghiêm trọng.
- 💧 **Chập nước:** Độ ẩm không khí cao bất thường (>95%) trong lúc máy bơm đang chạy.
- 📡 **Lỗi cảm biến:** Tích số `U x I` sai lệch quá 20% so với dữ liệu công suất `P` đo được.

---

## 📁 Cấu trúc Thư mục Hệ thống

```text
ASPC/
├── app.py                 # Core Backend (Flask + SocketIO + MQTT + Cam AI)
├── models.py              # Định nghĩa Database Schema (SQLAlchemy)
├── ai_engine.py           # Engine 1: Dự báo chuỗi thời gian (LSTM)
├── health_engine.py       # Engine 2: Tự học và đánh giá Sức khỏe tấm pin
├── optimizer.py           # Engine 3: Tối ưu Kinh tế (Điện bậc thang)
├── hotspot_engine.py      # Engine 4: Trí tuệ chuyên gia phát hiện Hotspot
├── aspc_production.db     # SQLite Database (Tự động sinh)
├── demo_solar.mp4         # Video dùng để test Vision AI
├── requirements.txt       # Danh sách thư viện Python
├── .env                   # File môi trường (Không push lên Git)
└── static/                # Web Dashboard Khách hàng
    ├── index.html         # Bảng điều khiển (Control Center)
    ├── hotspot.html       # Camera AI & Quét điểm nóng
    ├── health.html        # Biểu đồ hiệu suất & Báo cáo
    ├── parameter.html     # Nhập cấu hình vật lý & Giá điện EVN
    ├── weather.html       # Bản đồ dự báo thời tiết
    ├── profile.html       # Quản lý tài khoản
    ├── css/
    ├── js/
    └── uploads/           # Thư mục lưu trữ Avatar người dùng
```

---

## 📄 Bản quyền & Liên hệ

Được phát triển và thiết kế bởi **ASPC Team**.
Dự án tuân theo giấy phép **MIT License**. Vui lòng tham khảo file `LICENSE` để biết thêm chi tiết.
