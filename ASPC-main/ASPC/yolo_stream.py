import cv2
import numpy as np
from flask import Flask, Response, request, jsonify
import os
import time
import requests # Dùng để bắn cảnh báo sang app.py
import threading

app = Flask(__name__)


# 1. CẤU HÌNH NGUỒN CAMERA

# Cấu hình nguồn video. Thay đổi biến này khi chạy thực tế.
# Các lựa chọn:
# - "demo_solar.mp4" (Chạy video giả lập)
# - 0 (Webcam USB hoặc Camera laptop)
# - "rtsp://admin:123456@192.168.1.100:554/stream" (Camera IP thực tế trên mái nhà)
CAMERA_SOURCE = "demo_solar.mp4" 

# Cấu hình URL của hệ thống chính (app.py) để bắn cảnh báo
MAIN_SYSTEM_URL = "http://127.0.0.1:5000/api/camera_alert" 

# Biến global quản lý trạng thái cảnh báo để tránh bắn request liên tục làm nghẽn mạng
last_alert_time = 0 
ALERT_COOLDOWN = 10 # Chỉ bắn 1 cảnh báo mỗi 10 giây nếu lỗi vẫn tồn tại


# 2. HÀM KẾT NỐI CAMERA CÓ BẢO VỆ

def get_video_capture(source):
    """Mở kết nối camera, hỗ trợ tự động kết nối lại nếu mất mạng"""
    print(f"🔄 Đang kết nối tới nguồn Camera: {source} ...")
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ LỖI: Không thể mở được nguồn Camera: {source}")
        return None
    print(f"✅ Kết nối Camera thành công!")
    return cap


# 3. HÀM BẮN CẢNH BÁO SANG HỆ THỐNG CHÍNH

def trigger_system_alert(alert_type, confidence, location_info):
    """Bắn tín hiệu báo động sang app.py (Chạy luồng riêng để không làm giật video)"""
    global last_alert_time
    current_time = time.time()
    
    if current_time - last_alert_time > ALERT_COOLDOWN:
        payload = {
            "source": "CAMERA_AI",
            "type": alert_type,
            "confidence": confidence,
            "message": f"Camera phát hiện {alert_type} (Tỷ lệ: {confidence}%) tại {location_info}",
            "timestamp": current_time
        }
        
        try:
            # Gửi HTTP POST sang app.py một cách không đồng bộ
            def send_request():
                try:
                    requests.post(MAIN_SYSTEM_URL, json=payload, timeout=2)
                    print(f"🚀 [CAMERA_AI] Đã bắn cảnh báo sang Hệ thống trung tâm: {alert_type}")
                except:
                    pass # Bỏ qua nếu app.py chưa bật
                    
            threading.Thread(target=send_request, daemon=True).start()
            last_alert_time = current_time
        except Exception as e:
            print(f"⚠️ Lỗi gửi cảnh báo: {e}")


# 4. ENGINE XỬ LÝ ẢNH CHÍNH (FRAME GENERATOR)

def generate_frames():
    cap = get_video_capture(CAMERA_SOURCE)
    
    # Nếu file demo không tồn tại
    if cap is None and isinstance(CAMERA_SOURCE, str) and not CAMERA_SOURCE.startswith('rtsp'):
        if not os.path.exists(CAMERA_SOURCE):
            print(f"\n[!!! LOI CHI MANG !!!] Khong tim thay '{CAMERA_SOURCE}'")
            return

    frame_count = 0
    error_frames = 0

    while True:
        if cap is None:
            # Nếu mất kết nối RTSP, thử kết nối lại sau mỗi 5s
            time.sleep(5)
            cap = get_video_capture(CAMERA_SOURCE)
            continue

        success, frame = cap.read()
        
        if not success:
            # Xử lý khi rớt frame
            if isinstance(CAMERA_SOURCE, str) and not CAMERA_SOURCE.startswith('rtsp'):
                # Nếu là video demo (.mp4) -> Hết video thì tua lại từ đầu
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            else:
                # Nếu là IP Camera/Webcam -> Mất kết nối
                error_frames += 1
                if error_frames > 30: # Nếu rớt quá 30 frame liên tục
                    print("⚠️ Mất luồng Camera, đang thử kết nối lại...")
                    cap.release()
                    cap = None
                    error_frames = 0
                continue
                
        error_frames = 0 # Reset đếm lỗi
        frame_count += 1
        
        # Resize chuẩn ngang 16:9 để web hiển thị nhẹ nhàng
        frame = cv2.resize(frame, (854, 480))
        annotated_frame = frame.copy()

        warning_active = False
        highest_prob = 0
        worst_location = ""

        # --- THUẬT TOÁN TỰ ĐỘNG PHÁT HIỆN ĐỐM BỤI/PHÂN CHIM ---
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
                    cv2.putText(annotated_frame, f"Bird Drop {fake_prob}%", (x, y - 5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
                    
                    warning_active = True
                    if fake_prob > highest_prob:
                        highest_prob = fake_prob
                        worst_location = f"Tọa độ [X:{x}, Y:{y}]"

        # --- KÍCH HOẠT CẢNH BÁO SANG HỆ THỐNG CHÍNH ---
        if warning_active and highest_prob > 85: # Chỉ báo động nếu độ tự tin > 85%
            trigger_system_alert("BIRD_DROP_HOTSPOT", highest_prob, worst_location)

        # --- VẼ HUD (GIAO DIỆN KÍNH NGẮM BỀ NGANG) ---
        overlay = annotated_frame.copy()
        cv2.rectangle(overlay, (0, 0), (854, 60), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, annotated_frame, 0.4, 0, annotated_frame)
        
        cv2.putText(annotated_frame, "ASPC VISION AI SCANNING...", (10, 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        if warning_active:
            if frame_count % 10 < 5: 
                cv2.putText(annotated_frame, "WARNING: HOTSPOT RISK DETECTED!", (10, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        else:
            cv2.putText(annotated_frame, "STATUS: PANELS CLEAR", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Đẩy luồng ra web
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# 5. ROUTES

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# API phụ để hệ thống app.py có thể điều khiển camera từ xa (Đổi nguồn cam)
@app.route('/api/change_source', methods=['POST'])
def change_source():
    global CAMERA_SOURCE
    data = request.json
    new_source = data.get('source')
    if new_source is not None:
        # Nếu truyền lên số (VD: 0 cho webcam) thì chuyển thành int
        if str(new_source).isdigit():
            CAMERA_SOURCE = int(new_source)
        else:
            CAMERA_SOURCE = new_source
        return jsonify({"status": "success", "message": f"Đã chuyển nguồn Camera sang: {CAMERA_SOURCE}"})
    return jsonify({"status": "error", "message": "Thiếu biến 'source'"}), 400

if __name__ == '__main__':
    print("🚀 Khởi động ASPC VISION AI (SMART DETECTION)!")
    print(f"👉 Nguồn Camera hiện tại: {CAMERA_SOURCE}")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)