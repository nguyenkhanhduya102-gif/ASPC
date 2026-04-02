import numpy as np
import pandas as pd
import os
import threading
import joblib
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import LSTM, Dense, Input, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.losses import Huber
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score 
import tensorflow as tf
import time 
class SolarLSTM:
    def __init__(self, mac_address="default"):
        self.mac_address = mac_address
        
        # Tạo tên file ĐỘC LẬP cho từng thiết bị
        self.model_path = f'model_{self.mac_address}.h5'
        self.data_file = f'data_{self.mac_address}.csv'
        self.scaler_file = f'scaler_{self.mac_address}.pkl'
        
        self.model = None
        self.scaler = None
        
        #Cấu hình tối ưu cho hệ thống
        self.window_size = 30 
        self.num_features = 5 
        
        self.data_history = []     
        self.new_data_buffer = []  

        

        self.MAX_TRAIN_SIZE = 50000 
        self.is_training = False 
        

        self.retrain_interval = 30 * 24 * 60 * 60 
        self.last_retrain_time = time.time() # Mốc thời gian lần cuối học
        # Biến lưu kết quả đánh giá gần nhất
        self.last_metrics = {"mae": 0, "rmse": 0, "r2": 0}


        self.load_scaler()
        self.load_ai_model()
        

    def load_scaler(self):
        if os.path.exists(self.scaler_file):
            try:
                self.scaler = joblib.load(self.scaler_file)
            except:
                self.scaler = MinMaxScaler(feature_range=(0, 1))
        else:
            self.scaler = MinMaxScaler(feature_range=(0, 1))

    def load_ai_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = load_model(self.model_path, custom_objects={'Huber': Huber})
                if self.model.input_shape[-1] != self.num_features:
                    print(f" Model không khớp input. Đã xóa.")
                    self.model = None
                    if os.path.exists(self.model_path): os.remove(self.model_path)
            except:
                self.model = None




    def update_data(self, basic_data):
        if any(v is None for v in basic_data): return
        
        full_features = basic_data 

        self.data_history.append(full_features)
        if len(self.data_history) > self.window_size:
            self.data_history.pop(0)

        self.save_to_csv(full_features)
        
        # [MỚI] KIỂM TRA ĐIỀU KIỆN THỜI GIAN ĐỂ RETRAIN
        current_time = time.time()
        time_elapsed = current_time - self.last_retrain_time
        # Nếu đã trôi qua khoảng thời gian định kỳ VÀ không có luồng nào đang học
        if time_elapsed >= self.retrain_interval and not self.is_training:
            # Kiểm tra xem có đủ dữ liệu để học không (tối thiểu 1000 dòng để bõ công học)
            if os.path.exists(self.data_file):
                # (Mẹo nhỏ: Đếm số dòng file CSV mà không load toàn bộ vào RAM)
                with open(self.data_file, 'r') as f:
                    row_count = sum(1 for row in f)

                if row_count > 1000:
                    print(f"[{self.mac_address}] Đã đến hạn bảo trì AI ({self.retrain_interval/(24*3600):.1f} ngày). Khởi động quá trình Retrain...")
                    self.last_retrain_time = current_time # Reset đồng hồ
                    threading.Thread(target=self.retrain_model).start()





    def save_to_csv(self, data_row):
        try:
            # Đổi 't_panel' thành 't_virtual'
            cols = ['lux', 't_virtual', 't_env', 'hum', 'pump']
            df = pd.DataFrame([data_row], columns=cols)
            header = not os.path.exists(self.data_file)
            df.to_csv(self.data_file, mode='a', header=header, index=False)
        except: pass

    
    def evaluate_model(self, X_test, y_test):
        try:
            # 1. Dự báo thử trên tập Test
            y_pred_scaled = self.model.predict(X_test, verbose=0)
        
            if isinstance(y_pred_scaled, tf.Tensor):
                y_pred_scaled = y_pred_scaled.numpy()
            # 2. Giải nén (Inverse Scale) để ra nhiệt độ thật (Độ C)
            
            dummy_pred = np.zeros((len(y_pred_scaled), self.num_features))
            dummy_test = np.zeros((len(y_test), self.num_features))
            
            dummy_pred[:, 1] = y_pred_scaled.flatten() # Gán vào cột Temp Panel (index 1)
            dummy_test[:, 1] = y_test.flatten()
            
            real_pred = self.scaler.inverse_transform(dummy_pred)[:, 1]
            real_test = self.scaler.inverse_transform(dummy_test)[:, 1]
            
            # 3. Tính toán sai số
            mae = mean_absolute_error(real_test, real_pred)
            rmse = np.sqrt(mean_squared_error(real_test, real_pred))
            r2 = r2_score(real_test, real_pred)
            
            self.last_metrics = {
                "mae": round(mae, 3),   
                "rmse": round(rmse, 3), 
                "r2": round(r2, 3)      
            }
            
            print(f" ĐÁNH GIÁ: Sai số MAE = {mae:.2f}°C | R2 Score = {r2:.2f}")
            
        except Exception as e:
            print(f" Lỗi đánh giá: {e}")

    def retrain_model(self):
        self.is_training = True
        try:
            if not os.path.exists(self.data_file): return
            
            df = pd.read_csv(self.data_file)
            if 'delta_t' in df.columns: df = df.drop(columns=['delta_t'])
            if len(df) > self.MAX_TRAIN_SIZE: df = df.tail(self.MAX_TRAIN_SIZE)

            dataset = df.values.astype('float32') 
            if len(dataset) < 300: return # Cần ít nhất 300 điểm để chia tập

            self.scaler.fit(dataset)
            joblib.dump(self.scaler, self.scaler_file)
            scaled_data = self.scaler.transform(dataset)

            X, y = [], []
            STEPS_AHEAD = 36 # giả sử 1 phút 1 mẫu và dự đoán trước 15 phút (12/5 -> 36/15)
            
            for i in range(self.window_size, len(scaled_data) - STEPS_AHEAD):
                X.append(scaled_data[i-self.window_size:i, :]) 
                y.append(scaled_data[i + STEPS_AHEAD, 1])
                
            X, y = np.array(X), np.array(y)

            
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]

            if self.model is None:
                self.model = Sequential()
                self.model.add(Input(shape=(self.window_size, self.num_features)))
                self.model.add(LSTM(64, return_sequences=True)) # Giữ nguyên lớp này
                self.model.add(Dropout(0.2))
                self.model.add(LSTM(32, return_sequences=False))
                self.model.add(Dropout(0.2))
                self.model.add(Dense(16, activation='relu'))
                self.model.add(Dense(1)) 
                
               
                
                self.model.compile(optimizer='adam', loss=Huber(), run_eagerly=True)
            
            early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
            
            # Train trên tập Train, Validate trên tập Test
            self.model.fit(
                X_train, y_train, 
                validation_data=(X_test, y_test),
                batch_size=32, epochs=10, verbose=0, callbacks=[early_stop]
            )
            
            # [MỚI] Gọi hàm đánh giá sau khi train xong
            self.evaluate_model(X_test, y_test)
            
            self.model.save(self.model_path)
            self.new_data_buffer = [] 
            
        except Exception as e:
            print(f" Lỗi Retrain: {e}")
        finally: 
            self.is_training = False

    def predict(self):
        if len(self.data_history) < self.window_size: return None
        current_temp_real = self.data_history[-1][1] 

        if self.model and self.scaler:
            try:
                input_raw = np.array(self.data_history) # Lấy đúng window_size dòng cuối
                # Nếu history dài hơn window, cắt lấy đuôi
                if len(input_raw) > self.window_size:
                    input_raw = input_raw[-self.window_size:]
                
                input_scaled = self.scaler.transform(input_raw)
                input_reshaped = input_scaled.reshape(1, self.window_size, self.num_features)
                
                pred_scaled = self.model.predict(input_reshaped, verbose=0)
                
                dummy_row = np.zeros((1, self.num_features))
                dummy_row[0, 1] = pred_scaled[0][0]
                inversed_row = self.scaler.inverse_transform(dummy_row)
                pred_temp_15min = inversed_row[0, 1]
            except:
                pred_temp_15min = current_temp_real
        else:
            pred_temp_15min = current_temp_real

        return {
            "current_temp": round(current_temp_real, 2),
            "pred_temp_15min": round(pred_temp_15min, 2),
            "accuracy_mae": self.last_metrics["mae"] # Trả về sai số để hiển thị lên Web nếu cần
        }

    def predict_scenario(self, pump_action):
        if len(self.data_history) < 1: return None
        current = self.data_history[-1][1]
        return (current - 2.5) if pump_action == 1 else (current + 1.0)