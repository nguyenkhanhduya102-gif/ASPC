# ☀️ ASPC - Automatic Solar Panel Cooling System

> Hệ thống giám sát và điều khiển làm mát tấm pin mặt trời tự động, tích hợp AI dự báo nhiệt độ và tối ưu kinh tế.

---

## 📋 Mục Lục
- [Giới thiệu](#giới-thiệu)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Yêu cầu](#yêu-cầu)
- [Cài đặt & Chạy](#cài-đặt--chạy)
- [Cấu hình MQTT](#cấu-hình-mqtt)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Các chế độ hoạt động](#các-chế-độ-hoạt-động)

---

## 🌟 Giới thiệu

**ASPC** (Automatic Solar Panel Cooling) là hệ thống IoT gồm:
- 🖥️ **Backend Flask**: Web server real-time với WebSocket (Socket.IO)
- 🧠 **AI Engine (LSTM)**: Dự báo nhiệt độ tấm pin 5 phút tới
- ❤️ **Health Engine**: Tính toán "sức khỏe" và hiệu suất tấm pin
- 💰 **Optimizer Engine**: Tối ưu kinh tế — quyết định bật/tắt bơm có lời không
- 📡 **MQTT**: Giao tiếp với vi điều khiển ESP32

## 🏗️ Kiến trúc Hệ thống

```
ESP32 (Cảm biến)
     │  MQTT (TLS)
     ▼
HiveMQ Cloud Broker
     │
     ▼
┌──────────────────────────────────┐
│         Flask + Socket.IO        │
│  ┌───────────┐ ┌──────────────┐  │
│  │ AI Engine │ │Health Engine │  │
│  │  (LSTM)   │ │(Self-learning│  │
│  └───────────┘ └──────────────┘  │
│  ┌───────────────────────────┐   │
│  │     Optimizer Engine      │   │
│  │  (EVN Tiered Pricing)     │   │
│  └───────────────────────────┘   │
└──────────────────────────────────┘
     │
     ▼
Web Dashboard (HTML/CSS/JS)
```

---

## ⚙️ Yêu cầu

- **Python** 3.8 trở lên
- **pip**
- Kết nối MQTT broker (HiveMQ Cloud hoặc tự host)
- *(Tuỳ chọn)* ESP32 với firmware phù hợp

---

## 🚀 Cài đặt & Chạy

### 1. Clone repository

```bash
git clone https://github.com/<your-username>/ASPC.git
cd ASPC
```

### 2. Tạo môi trường ảo (khuyến nghị)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Cài đặt dependencies

```bash
cd ASPC
pip install -r requirements.txt
```

### 4. Cấu hình biến môi trường

```bash
# Sao chép file mẫu
cp .env.example .env

# Mở file .env và điền thông tin MQTT của bạn
```

Sửa file `.env`:
```env
MQTT_BROKER=your-broker.hivemq.cloud
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password
```

### 5. Chạy server

```bash
python app.py
```

Truy cập dashboard tại: **http://localhost:5000**

---

## 🧪 Chế độ Giả lập (Simulation Mode)

Nếu chưa có phần cứng ESP32, bật chế độ giả lập trong file `.env`:

```env
SIMULATION_MODE=True
```

---

## 📡 Cấu hình MQTT

Dự án sử dụng **HiveMQ Cloud** với kết nối TLS (port 8883). Bạn có thể đăng ký miễn phí tại [hivemq.com](https://www.hivemq.com/mqtt-cloud-broker/).

| Topic | Chiều | Mô tả |
|---|---|---|
| `aspc/data` | Subscribe | Dữ liệu cảm biến từ ESP32 |
| `aspc/control` | Publish | Lệnh điều khiển đến ESP32 |

**Payload từ ESP32** (JSON format):
```json
{
  "temp_panel": 55.2,
  "temp_env": 32.1,
  "humidity": 65,
  "lux_ref": 85000,
  "power": 42.3,
  "pump_status": 0
}
```

---

## 📁 Cấu trúc Thư mục

```
ASPC/
├── README.md               ← Tài liệu này
├── .gitignore
└── ASPC/                   ← Source code chính
    ├── app.py              ← Flask server chính + MQTT handler
    ├── ai_engine.py        ← LSTM Model: dự báo nhiệt độ
    ├── health_engine.py    ← Tính sức khỏe tấm pin (tự học)
    ├── optimizer.py        ← Tối ưu kinh tế (giá điện EVN bậc thang)
    ├── requirements.txt    ← Python dependencies
    ├── .env.example        ← Mẫu cấu hình (copy → .env)
    ├── calibration.json    ← Thông số tấm pin (lưu tự động)
    └── static/             ← Web Dashboard
        ├── index.html      ← Dashboard chính
        ├── health.html     ← Trang sức khỏe tấm pin
        ├── history.html    ← Lịch sử lệnh
        ├── parameter.html  ← Cài đặt thông số
        ├── css/
        └── js/
```

---

## 🎮 Các Chế Độ Hoạt Động

| Chế độ | Mô tả |
|---|---|
| **MANUAL** | Điều khiển thủ công, AI đưa ra lời khuyên |
| **AUTO** | AI tự động bật/tắt bơm theo ngưỡng nhiệt độ |
| **SMART ECO** | AI tối ưu kinh tế — bật bơm chỉ khi có lời về điện |

---

## 📊 Tính Năng AI

- **LSTM Multivariate**: Học từ 5 features (lux, nhiệt độ tấm, nhiệt độ môi trường, độ ẩm, trạng thái bơm)
- **Online Learning**: Tự retrain sau mỗi 100 mẫu dữ liệu mới
- **Scenario Prediction**: Dự báo nhiệt độ trong 2 kịch bản (bơm bật / bơm tắt)

---

## 👥 Đóng Góp

1. Fork repository
2. Tạo branch mới: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m "feat: thêm tính năng X"`
4. Push: `git push origin feature/ten-tinh-nang`
5. Tạo Pull Request

---

## 📄 Giấy Phép

MIT License — xem file [LICENSE](LICENSE) để biết thêm chi tiết.
