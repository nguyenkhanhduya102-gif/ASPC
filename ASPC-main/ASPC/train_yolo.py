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
    results = model.train(
        data=yaml_path,      # Truyền đường dẫn tuyệt đối tự động vào đây
        epochs=30,           
        imgsz=640,           
        batch=8,             
        workers=0,           
        device='cpu'         
    )

    print("✅ Hoàn tất huấn luyện!")

if __name__ == '__main__':
    main()