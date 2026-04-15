from ultralytics import YOLO
import os

def main():
    # Tự động lấy đường dẫn tuyệt đối của file data.yaml đang nằm cạnh file này
    current_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(current_dir, 'data.yaml')

    print("🚀 Khởi tạo mô hình YOLOv8 Nano...")
    model = YOLO('yolov8n.pt') 

    print(f"🧠 Bắt đầu huấn luyện...")
    print(f"📁 Đang đọc cấu hình tại: {yaml_path}")
    
    # Bắt đầu train
        # Bắt đầu train (Đã tối ưu cho tập dữ liệu ít ảnh)
    results = model.train(
        data=yaml_path,      
        epochs=50,          # TĂNG LÊN 100 (Vì ít ảnh nên phải cho nó học đi học lại nhiều lần)
        patience=20,         # Nếu sau 20 epoch không thông minh hơn thì tự động dừng sớm
        imgsz=640,           
        batch=8,             
        workers=0,           
        device='cpu',
        
        # --- BẬT CÁC TÍNH NĂNG AUGMENTATION (TỰ ĐỘNG NHÂN BẢN ẢNH) ---
        degrees=15.0,        # Tự động xoay nghiêng ảnh ngẫu nhiên 15 độ
        translate=0.1,       # Dịch chuyển ảnh ngẫu nhiên (tránh việc lỗi luôn nằm ở giữa)
        scale=0.5,           # Tự động phóng to/thu nhỏ ảnh 50%
        fliplr=0.5,          # Lật ngang ảnh (Tỉ lệ 50%)
        flipud=0.5,          # Lật dọc ảnh (Vì camera của bạn chĩa từ trên xuống)
        hsv_s=0.5,           # Tự động thay đổi độ bão hòa màu (Giả lập trời nắng gắt/râm mát)
        hsv_v=0.4,           # Tự động thay đổi độ sáng
        mosaic=1.0,          # (SIÊU VŨ KHÍ) Cắt ghép 4 bức ảnh thành 1 bức để AI học được nhiều bối cảnh
        erasing=0.4          # Tự động che đi một phần ảnh để ép AI phải nhìn kỹ hơn
    )

    print("✅ Hoàn tất huấn luyện!")
    metrics = model.val()

    # Trích xuất và in các chỉ số quan trọng nhất (nhân 100 để ra phần trăm)
    precision = metrics.box.mp * 100  # Mean Precision
    recall = metrics.box.mr * 100     # Mean Recall
    map50 = metrics.box.map50 * 100   # mAP tại ngưỡng IoU 0.5 (Chỉ số quan trọng nhất)
    map75 = metrics.box.map * 100     # mAP trung bình (0.5 - 0.95)

    print(f" Độ chính xác (Precision): {precision:.2f}%")
    print(f" Độ phủ (Recall):          {recall:.2f}%")
    print(f" Chỉ số mAP50 : {map50:.2f}%")
    print(f" Chỉ số mAP75:      {map75:.2f}%")
    print("="*40)
    print("💡 MẸO: Hãy mở thư mục 'runs/detect/train/' để lấy các biểu đồ vẽ sẵn đưa vào Slide !")


if __name__ == '__main__':
    main()