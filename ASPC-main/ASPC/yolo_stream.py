import cv2
import numpy as np
from flask import Flask, Response, request, jsonify
import os
import time
import requests
import threading

# Nhúng thư viện YOLO
from ultralytics import YOLO

app = Flask(__name__)

# Cấu hình nguồn và API
CAMERA_SOURCE = 0
# "demo_solar.mp4" 
MAIN_SYSTEM_URL = "http://127.0.0.1:5000/api/camera_alert" 

last_alert_time = 0 
ALERT_COOLDOWN = 10 

# LOAD MÔ HÌNH YOLO BẠN VỪA TRAIN XONG (Chỉ load 1 lần khi bật server)
print("🧠 Đang tải Model YOLO Vision AI...")
yolo_model = YOLO(r"C:\Users\nguye\Downloads\ASPC-main\ASPC-main\models_ai\yolo_solar.pt")

def get_video_capture(source):
    print(f"🔄 Đang kết nối tới nguồn Camera: {source} ...")
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"❌ LỖI: Không thể mở được nguồn Camera: {source}")
        return None
    print(f"✅ Kết nối Camera thành công!")
    return cap

def trigger_system_alert(alert_type, confidence, location_info):
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
            def send_request():
                try:
                    requests.post(MAIN_SYSTEM_URL, json=payload, timeout=2)
                    print(f"🚀 [CAMERA_AI] Đã bắn cảnh báo: {alert_type}")
                except:
                    pass 
            threading.Thread(target=send_request, daemon=True).start()
            last_alert_time = current_time
        except Exception as e:
            print(f"⚠️ Lỗi gửi cảnh báo: {e}")

def generate_frames():
    cap = get_video_capture(CAMERA_SOURCE)
    
    if cap is None and isinstance(CAMERA_SOURCE, str) and not CAMERA_SOURCE.startswith('rtsp'):
        if not os.path.exists(CAMERA_SOURCE):
            print(f"\n[!!! LOI CHI MANG !!!] Khong tim thay '{CAMERA_SOURCE}'")
            return

    frame_count = 0
    error_frames = 0

    while True:
        if cap is None:
            time.sleep(5)
            cap = get_video_capture(CAMERA_SOURCE)
            continue

        success, frame = cap.read()
        
        if not success:
            if isinstance(CAMERA_SOURCE, str) and not CAMERA_SOURCE.startswith('rtsp'):
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            else:
                error_frames += 1
                if error_frames > 30: 
                    print("⚠️ Mất luồng Camera, đang thử kết nối lại...")
                    cap.release()
                    cap = None
                    error_frames = 0
                continue
                
        error_frames = 0 
        frame_count += 1
        
        frame = cv2.resize(frame, (854, 480))
        annotated_frame = frame.copy()

        warning_active = False
        highest_prob = 0
        worst_location = ""
        detected_issues = []

        # =========================================================
        # AI YOLO NHẬN DIỆN TẠI ĐÂY
        # conf=0.4: Bỏ qua các vật thể AI không chắc chắn (dưới 40%)
        # =========================================================
        results = yolo_model.predict(source=frame, conf=0.4, verbose=False)

        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Lấy tọa độ
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Lấy độ tự tin và tên lỗi
                conf = int(box.conf[0] * 100)
                cls_id = int(box.cls[0])
                class_name = yolo_model.names[cls_id]

                # Nếu là pin bình thường (Non Defective) thì bỏ qua không báo động
                if class_name == 'Non Defective':
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated_frame, f"Normal {conf}%", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    continue

                # Nếu là LỖI (Bụi, nứt, phân chim...)
                warning_active = True
                detected_issues.append(class_name)
                
                # Vẽ khung màu đỏ cho lỗi
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(annotated_frame, f"{class_name} {conf}%", (x1, y1 - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                if conf > highest_prob:
                    highest_prob = conf
                    worst_location = f"Tọa độ [X:{x1}, Y:{y1}]"

        # Gửi cảnh báo về app.py
        if warning_active and highest_prob > 50: 
            issue_str = " + ".join(set(detected_issues))
            trigger_system_alert(f"LỖI: {issue_str.upper()}", highest_prob, worst_location)

        # Vẽ HUD giao diện
        overlay = annotated_frame.copy()
        cv2.rectangle(overlay, (0, 0), (854, 60), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, annotated_frame, 0.4, 0, annotated_frame)
        
        cv2.putText(annotated_frame, "ASPC VISION AI SCANNING...", (10, 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        if warning_active:
            if frame_count % 10 < 5: 
                cv2.putText(annotated_frame, "WARNING: DEFECT DETECTED!", (10, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        else:
            cv2.putText(annotated_frame, "STATUS: PANELS CLEAR", (10, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# API
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/change_source', methods=['POST'])
def change_source():
    global CAMERA_SOURCE
    data = request.json
    new_source = data.get('source')
    if new_source is not None:
        if str(new_source).isdigit():
            CAMERA_SOURCE = int(new_source)
        else:
            CAMERA_SOURCE = new_source
        return jsonify({"status": "success", "message": f"Đã chuyển nguồn Camera: {CAMERA_SOURCE}"})
    return jsonify({"status": "error", "message": "Thiếu biến 'source'"}), 400

if __name__ == '__main__':
    print("🚀 Khởi động ASPC VISION AI (YOLO DETECTION)!")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)