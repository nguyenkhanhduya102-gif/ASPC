import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, optimizers
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import os
import sys

# Khắc phục lỗi in Unicode/Emoji trên Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- CẤU HÌNH ---
# SỬA LẠI ĐÚNG TÊN FILE DATA HÀ NỘI BẠN VỪA GỬI
DATA_HANOI_PATH = "data_pin.csv"  
MODEL_STAGE1_PATH = "models_ai/mlp16_solar.h5"
SCALER_PATH = "models_ai/scaler_mlp16.pkl"
MODEL_FINAL_PATH = "models_ai/mlp16_final.h5"
TFLITE_PATH = "models_ai/mlp16_esp32.tflite"

def create_synthetic_vn_data(num_samples=23951):
    """
    Tạo dữ liệu tổng hợp đại diện cho thời tiết nhiệt đới bằng Mô hình Sandia (SAPM).
    Công thức SAPM: T_pv = T_amb + GHI/1000 * (T_NOCT - T_ref) + a * (1 - n) * GHI * (1 - w_s/25)
    """
    print(f"🌴 Đang sinh {num_samples} mẫu dữ liệu tổng hợp Khí hậu Nhiệt đới (SAPM Model)...")
    np.random.seed(42)
    
    temp_env = np.random.normal(loc=29.5, scale=3.2, size=num_samples)
    ghi = np.random.normal(loc=900.0, scale=150.0, size=num_samples)
    ghi = np.clip(ghi, 0, 1500) 
    lux = ghi * 116.0 
    
    humidity = np.random.normal(loc=72.0, scale=12.0, size=num_samples)
    humidity = np.clip(humidity, 0, 100) 
    
    wind_speed = np.random.normal(loc=2.1, scale=1.0, size=num_samples)
    wind_speed = np.clip(wind_speed, 0, 20) 
    
    pump_status = np.random.choice([0, 1], size=num_samples)
    
    t_noct = 48.0   
    t_ref = 20.0    
    a = 0.94        
    n = 0.18        
    
    t_pv_base = temp_env + (ghi / 1000.0) * (t_noct - t_ref) + a * (1.0 - n) * (ghi / 100.0) * (1.0 - wind_speed / 25.0)
    pump_cooling_effect = pump_status * (15.0 - (humidity / 100.0) * 5.0)
    
    current_t_cell = t_pv_base - pump_cooling_effect
    current_t_cell = np.clip(current_t_cell, temp_env, 85.0) 
    
    pred_15m = current_t_cell + (t_pv_base - current_t_cell) * 0.2
    pred_15m = np.where(pump_status == 1, temp_env + 2.0, pred_15m)
    
    X = np.column_stack((temp_env, humidity, lux, wind_speed, pump_status))
    y = np.column_stack((current_t_cell, pred_15m)) # T_cell là cột 0, T_future là cột 1
    return X, y

def prepare_hanoi_data():
    """Đọc và xử lý file CSV thực tế tại Hà Nội"""
    print(f"📖 Đang đọc dữ liệu thực tế Hà Nội từ {DATA_HANOI_PATH}...")
    try:
        # Load bỏ cột đầu tiên (index) nếu có
        df = pd.read_csv(DATA_HANOI_PATH)
        
        # Xác định tên cột thực tế (đề phòng file bị lỗi tên cột)
        if len(df.columns) >= 5:
            # Format: Index, T_PV, I, T_mt, Do_am
            df = df.iloc[:, 1:5] # Bỏ cột đầu, lấy 4 cột sau
            df.columns = ['t_pv', 'lux', 't_env', 'humidity']
        else:
            # Nếu lỡ có 4 cột:
            df.columns = ['t_pv', 'lux', 't_env', 'humidity']

        # Vì Data Hà Nội không có đo Gió và Trạng thái Bơm, ta phải sinh ẢO để khớp với Input 5 biến của AI
        np.random.seed(99)
        # Gió ở Hà Nội dao động từ 0.5 đến 3.5 m/s
        df['wind_speed'] = np.random.uniform(0.5, 3.5, len(df))
        
        # Vì đo thực tế không dùng bơm, pump = 0 toàn bộ
        df['pump_status'] = 0

        # Lọc nhiễu dữ liệu rác (Ví dụ bị âm hoặc NaN)
        df = df.dropna()
        df = df[(df['t_env'] > 0) & (df['humidity'] > 0)]

        # Tạo nhãn dự báo (Target Future - dịch lên 15 dòng)
        df['target_future'] = df['t_pv'].shift(-15)
        df = df.dropna() # Bỏ 15 dòng cuối bị NaN

        # Trích xuất biến (Đúng thứ tự: temp_env, humidity, lux, wind_speed, pump_status)
        X = df[['t_env', 'humidity', 'lux', 'wind_speed', 'pump_status']].values
        
        # Y trả về 2 cột [T_cell_hien_tai, T_cell_tuong_lai] cho giống Giai đoạn 2
        y = df[['t_pv', 'target_future']].values
        
        print(f"✔️ Đã chuẩn bị xong {len(X)} mẫu dữ liệu Hà Nội!")
        return X, y
    except Exception as e:
        print(f"❌ Lỗi xử lý file Hà Nội: {e}")
        return None, None



def main():
    if not os.path.exists(MODEL_STAGE1_PATH) or not os.path.exists(SCALER_PATH):
        print("❌ Chưa có Model Stage 1. Vui lòng chạy code cũ để tạo mlp16_solar.h5 trước!")
        return

    # Load Model Stage 1 và Scaler
    print("🧠 Đang tải Model và Scaler từ Giai đoạn 1...")
    # [FIX LỖI KERAS Ở ĐÂY]: Thêm compile=False
    model = keras.models.load_model(MODEL_STAGE1_PATH, compile=False)
    scaler = joblib.load(SCALER_PATH)

    
    # GIAI ĐOẠN 2: DOMAIN ADAPTATION (Học Khí Hậu VN - SAPM)
    
    print("\n" + "="*50)
    print("🚀 BẮT ĐẦU GIAI ĐOẠN 2: DOMAIN ADAPTATION (VN - SAPM)")
    
    X_vn, y_vn = create_synthetic_vn_data()
    X_vn_scaled = scaler.transform(X_vn)
    
    X_train_2, X_test_2, y_train_2, y_test_2 = train_test_split(X_vn_scaled, y_vn, test_size=0.2)
    
    # Đóng băng lớp ẩn đầu tiên (Giữ lại kiến thức Vật lý Mỹ), chỉ train phần còn lại
    model.layers[0].trainable = False 
    model.compile(optimizer=optimizers.Adam(learning_rate=0.001), loss='mse', metrics=['mae'])
    
    model.fit(X_train_2, y_train_2, validation_data=(X_test_2, y_test_2), epochs=20, batch_size=64, verbose=2)
    print("✅ Hoàn thành Giai đoạn 2!")

    
    # GIAI ĐOẠN 3: FINE-TUNING (Tinh chỉnh bằng Dữ liệu thực tế Hà Nội)
   
    print("\n" + "="*50)
    print("🎯 BẮT ĐẦU GIAI ĐOẠN 3: FINE-TUNING (HÀ NỘI)")
    
    # Mở khóa toàn bộ Nơ-ron để học chi tiết
    model.layers[0].trainable = True 
    model.compile(optimizer=optimizers.Adam(learning_rate=0.0001), loss='mse', metrics=['mae'])

    if os.path.exists(DATA_HANOI_PATH):
        print(f"📖 Đang đọc dữ liệu thực tế từ: {DATA_HANOI_PATH}")
        df = pd.read_csv(DATA_HANOI_PATH)
        
        # Đổi tên cột từ Dataset_AI_Chen sang chuẩn AI
        df['temp_env'] = df['T_mt']
        df['humidity'] = df['Do_am']
        df['lux'] = df['I']
        df['target_t_cell'] = df['T_PV']
        
        # Thêm 2 cột bị thiếu trong data gốc (Giả định lúc đo không bật bơm và gió nhẹ)
        df['wind_speed'] = 2.0
        df['pump_status'] = 0
        
        # Tạo nhãn dự báo 15p (Shift 15 dòng)
        df['pred_15m'] = df['target_t_cell'].shift(-15)
        df = df.dropna()
        
        # Gom tính năng
        X_hn = df[['temp_env', 'humidity', 'lux', 'wind_speed', 'pump_status']].values
        y_hn = df[['target_t_cell', 'pred_15m']].values
        
        X_hn_scaled = scaler.transform(X_hn)
        X_train_3, X_test_3, y_train_3, y_test_3 = train_test_split(X_hn_scaled, y_hn, test_size=0.2)
        
        model.fit(X_train_3, y_train_3, validation_data=(X_test_3, y_test_3), epochs=30, batch_size=32, verbose=2)
    else:
        print(f"⚠️ Không tìm thấy file {DATA_HANOI_PATH}. Vui lòng kiểm tra lại tên file!")
        print("Đang lấy 10% data Nhiệt đới làm Mồi (Warm-up) cho Giai đoạn 3...")
        X_train_3, X_test_3, y_train_3, y_test_3 = train_test_split(X_vn_scaled, y_vn, train_size=2000)
        model.fit(X_train_3, y_train_3, validation_data=(X_test_3, y_test_3), epochs=10, batch_size=16, verbose=2)

    # Lưu Model Cuối Cùng cho Web chạy
    model.save(MODEL_FINAL_PATH)
    print(f"🎉 Đã lưu Model AI Gốc tại: {MODEL_FINAL_PATH}")

if __name__ == "__main__":
    main()
   









