
import cv2
import numpy as np
from flask import Flask, Response
import os 
app = Flask(__name__)

# Tên video NGANG tải từ Youtube về
VIDEO_SOURCE = "demo_solar.mp4" 

def generate_frames():
    if not os.path.exists(VIDEO_SOURCE):
        print(f"\n[!!! LOI CHI MANG !!!]")
        print(f"Khong tim thay file '{VIDEO_SOURCE}' trong thu muc hien tai.")
        print(f"Thu muc hien tai la: {os.getcwd()}")
        print(f"Ban hay kiem tra lai ten file video da dung chua nhe!\n")
        return
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    
    if not cap.isOpened():
        print(f" khong tim thay video '{VIDEO_SOURCE}'.")
        return

    frame_count = 0

    while True:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
            
        frame_count += 1
        
        # Resize chuẩn ngang 16:9
        frame = cv2.resize(frame, (854, 480))
        annotated_frame = frame.copy()

        warning_active = False

        # --- THUẬT TOÁN TỰ ĐỘNG PHÁT HIỆN ĐỐM BỤI/PHÂN CHIM ---
        # 1. Chuyển ảnh sang hệ màu HSV để dễ lọc đốm sáng
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # 2. Định nghĩa dải màu của "Phân chim" / "Bụi xám sáng"
        # Bụi/phân chim thường có màu trắng xám, độ sáng cao, độ bão hòa màu thấp
        lower_white = np.array([0, 0, 160])    
        upper_white = np.array([180, 50, 255]) 

        # 3. Tạo mặt nạ (Mask) để tách các đốm đó ra khỏi nền đen của pin
        mask = cv2.inRange(hsv_frame, lower_white, upper_white)

        # 4. Làm sạch nhiễu nhỏ li ti (Blur/Morphology)
        kernel = np.ones((5,5), np.uint8)
        mask_clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 5. Tìm các đường viền bao quanh cục phân chim
        contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 6. Vẽ khung chữ nhật vào các đốm tìm được
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Chỉ lấy đốm to vừa phải (loại đốm quá nhỏ do nhiễu, hoặc quá to do ánh mặt trời chói)
            if 50 < area < 2000:
                # Lấy tọa độ khung chữ nhật
                x, y, w, h = cv2.boundingRect(contour)
                
                # Giả lập tỷ lệ % AI nhận diện (tùy theo diện tích đốm)
                fake_prob = min(99, 75 + (int(area) % 24))
                
                # Vẽ khung Cam
                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 165, 255), 2)
                
                # Ghi chữ lên khung (Chỉ ghi nếu đốm đủ lớn để đỡ rối mắt)
                if area > 300:
                    cv2.putText(annotated_frame, f"Bird Drop {fake_prob}%", (x, y - 5), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)
                
                warning_active = True

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

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print(" ASPC VISION AI (SMART DETECTION)!")
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)