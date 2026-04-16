import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, optimizers
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Input, Dropout
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import os
import sys
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- CẤU HÌNH ---
DATA_USA_PATH = "data_usa.csv"
DATA_HANOI_PATH = "data_pin.csv"  
MODEL_STAGE1_PATH = "models_ai/lstm_stage1.h5"
SCALER_PATH = "models_ai/scaler_lstm.pkl"
MODEL_FINAL_PATH = "models_ai/lstm_final.h5"
TIME_STEPS = 10 

os.makedirs("models_ai", exist_ok=True)

def create_dataset(X, y, time_steps=1):
    Xs, ys = [], []
    for i in range(len(X) - time_steps + 1):
        Xs.append(X[i : (i + time_steps)])
        ys.append(y[i + time_steps - 1]) # Lấy nhãn tại bước cuối của cửa sổ
    return np.array(Xs), np.array(ys)

def prepare_usa_data():
    print(f"🇺🇸 Đang đọc dữ liệu USA từ {DATA_USA_PATH}...")
    try:
        df = pd.read_csv(DATA_USA_PATH)
        cols = df.columns.str.lower()
        
        t_env = df['t_amb'] if 't_amb' in cols else df.iloc[:, 1]
        lux = df['ghi'] * 116.0 if 'ghi' in cols else df.iloc[:, 2] * 116.0
        t_pv = df['t_module'] if 't_module' in cols else df.iloc[:, 3]
        humidity = df['humidity'] if 'humidity' in cols else np.random.uniform(40, 80, len(df))
        wind_speed = df['wind_speed'] if 'wind_speed' in cols else np.random.uniform(1, 5, len(df))
        
        df_clean = pd.DataFrame({
            't_env': t_env, 'humidity': humidity, 'lux': lux, 
            'wind_speed': wind_speed, 'pump_status': 0, 't_pv': t_pv
        }).dropna()

        df_clean['target_future'] = df_clean['t_pv'].shift(-15)
        df_clean = df_clean.dropna()

        X = df_clean[['t_env', 'humidity', 'lux', 'wind_speed', 'pump_status']].values
        y = df_clean[['t_pv', 'target_future']].values
        return X, y
    except Exception as e:
        print(f" Lỗi đọc file USA: {e}")
        return None, None

def create_synthetic_vn_data(num_samples=23951):
    print(f"🌴 Đang sinh {num_samples} mẫu dữ liệu SAPM (Khí hậu VN)...")
    np.random.seed(42)
    
    temp_env = np.random.normal(loc=29.5, scale=3.2, size=num_samples)
    ghi = np.clip(np.random.normal(loc=900.0, scale=150.0, size=num_samples), 0, 1500) 
    lux = ghi * 116.0 
    humidity = np.clip(np.random.normal(loc=72.0, scale=12.0, size=num_samples), 0, 100) 
    wind_speed = np.clip(np.random.normal(loc=2.1, scale=1.0, size=num_samples), 0, 20) 
    pump_status = np.random.choice([0, 1], size=num_samples)
    
    t_noct, t_ref, a, n = 48.0, 20.0, 0.94, 0.18        
    
    t_pv_base = temp_env + (ghi / 1000.0) * (t_noct - t_ref) + a * (1.0 - n) * (ghi / 100.0) * (1.0 - wind_speed / 25.0)
    pump_cooling_effect = pump_status * (15.0 - (humidity / 100.0) * 5.0)
    
    current_t_cell = np.clip(t_pv_base - pump_cooling_effect, temp_env, 85.0) 
    pred_15m = np.where(pump_status == 1, temp_env + 2.0, current_t_cell + (t_pv_base - current_t_cell) * 0.2)
    
    X = np.column_stack((temp_env, humidity, lux, wind_speed, pump_status))
    y = np.column_stack((current_t_cell, pred_15m))
    return X, y

def prepare_hanoi_data():
    print(f"🇻🇳 Đang đọc dữ liệu Hà Nội từ {DATA_HANOI_PATH}...")
    try:
        df = pd.read_csv(DATA_HANOI_PATH)
        df = df.iloc[:, 1:5] if len(df.columns) >= 5 else df
        df.columns = ['t_pv', 'lux', 't_env', 'humidity']
        
        np.random.seed(99)
        df['wind_speed'] = np.random.uniform(0.5, 3.5, len(df))
        df['pump_status'] = 0

        df = df[(df['t_env'] > 0) & (df['humidity'] > 0)].dropna()
        df['target_future'] = df['t_pv'].shift(-15)
        df = df.dropna()

        X = df[['t_env', 'humidity', 'lux', 'wind_speed', 'pump_status']].values
        y = df[['t_pv', 'target_future']].values
        return X, y
    except Exception as e:
        print(f"❌ Lỗi xử lý file Hà Nội: {e}")
        return None, None


# QUÁ TRÌNH HUẤN LUYỆN

def build_lstm_model():
    model = Sequential([
        # Shape LSTM: (time_steps=TIME_STEPS, features=5)
        Input(shape=(TIME_STEPS, 5)),
        LSTM(32, activation='tanh', return_sequences=False),
        Dropout(0.2),
        Dense(16, activation='relu'),
        Dense(2, activation='linear') # Output: [T_hien_tai, T_tuong_lai]
    ])
    model.compile(optimizer=optimizers.Adam(learning_rate=0.001), loss=tf.keras.losses.Huber(delta=1.0), metrics=['mae'])
    return model

def load_model_safe(path):
    try:
        return keras.models.load_model(path, compile=False)
    except:
        return None

def main():
    scaler = StandardScaler()
    
    
    # GIAI ĐOẠN 1: PRE-TRAIN (DỮ LIỆU USA)
    
    print("\n" + "="*50)
    print(" GIAI ĐOẠN 1: HỌC KIẾN THỨC NỀN TẢNG (DATA USA)")
    X_usa, y_usa = prepare_usa_data()
    
    if X_usa is not None:
        X_usa_scaled = scaler.fit_transform(X_usa)
        # Áp dụng Sliding Window
        X_usa_seq, y_usa_seq = create_dataset(X_usa_scaled, y_usa, TIME_STEPS)
        X_train_1, X_test_1, y_train_1, y_test_1 = train_test_split(X_usa_seq, y_usa_seq, test_size=0.2)
        
        model = build_lstm_model()
        model.fit(X_train_1, y_train_1, validation_data=(X_test_1, y_test_1), epochs=20, batch_size=64, verbose=1)
        model.save(MODEL_STAGE1_PATH)
        joblib.dump(scaler, SCALER_PATH)
        print(" Đã lưu Base Model Stage 1!")
    else:
        print(" Bỏ qua Giai đoạn 1 do không đọc được file USA.")

   
    # GIAI ĐOẠN 2: DOMAIN ADAPTATION (KHÍ HẬU VN)
    
    print("\n" + "="*50)
    print(" GIAI ĐOẠN 2: THÍCH NGHI KHÍ HẬU (MÔ HÌNH SAPM)")
    
    model = load_model_safe(MODEL_STAGE1_PATH) or build_lstm_model()
    
    X_vn, y_vn = create_synthetic_vn_data()
    if not os.path.exists(SCALER_PATH):
        X_vn_scaled = scaler.fit_transform(X_vn)
        joblib.dump(scaler, SCALER_PATH)
    else:
        scaler = joblib.load(SCALER_PATH)
        X_vn_scaled = scaler.transform(X_vn)
        
    X_vn_seq, y_vn_seq = create_dataset(X_vn_scaled, y_vn, TIME_STEPS)
    X_train_2, X_test_2, y_train_2, y_test_2 = train_test_split(X_vn_seq, y_vn_seq, test_size=0.2)
    
    # Đóng băng LSTM layer
    model.layers[0].trainable = False 
    model.compile(optimizer=optimizers.Adam(learning_rate=0.001), loss=tf.keras.losses.Huber(delta=1.0), metrics=['mae'])
    model.fit(X_train_2, y_train_2, validation_data=(X_test_2, y_test_2), epochs=15, batch_size=64, verbose=1)

    
    # GIAI ĐOẠN 3: FINE-TUNING (HÀ NỘI)
    
    print("\n" + "="*50)
    print(" GIAI ĐOẠN 3: TINH CHỈNH CHI TIẾT (HÀ NỘI)")
    
    early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
    checkpoint = ModelCheckpoint(MODEL_FINAL_PATH, monitor='val_loss', save_best_only=True) 

    X_hn, y_hn = prepare_hanoi_data()
    
    # Mở khóa toàn bộ mô hình
    model.layers[0].trainable = True 
    model.compile(optimizer=optimizers.Adam(learning_rate=0.0001), loss=tf.keras.losses.Huber(delta=1.0), metrics=['mae'])

    if X_hn is not None:
        X_hn_scaled = scaler.transform(X_hn)
        X_hn_seq, y_hn_seq = create_dataset(X_hn_scaled, y_hn, TIME_STEPS)
        X_train_3, X_test_3, y_train_3, y_test_3 = train_test_split(X_hn_seq, y_hn_seq, test_size=0.2)
        
        model.fit(X_train_3, y_train_3, validation_data=(X_test_3, y_test_3), epochs=30, batch_size=32, callbacks=[early_stop, checkpoint], verbose=1)
    else:
        print(" Không có data Hà Nội. Lấy một phần SAPM làm Fine-tune...")
        X_train_3, X_test_3, y_train_3, y_test_3 = train_test_split(X_vn_seq, y_vn_seq, train_size=2000)
        model.fit(X_train_3, y_train_3, validation_data=(X_test_3, y_test_3), epochs=50, batch_size=16, callbacks=[early_stop, checkpoint], verbose=1)

    model.save(MODEL_FINAL_PATH)
    print(f"🎉 Đã lưu Model AI LSTM Cuối Cùng tại: {MODEL_FINAL_PATH}")

if __name__ == "__main__":
    main()
   









