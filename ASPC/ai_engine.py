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
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score # [MỚI] Thư viện chấm điểm

class SolarLSTM:
    def __init__(self, model_path='model_multivariate.h5', data_file='solar_data_multi.csv', scaler_file='scaler.pkl'):
        self.model_path = model_path
        self.data_file = data_file
        self.scaler_file = scaler_file
        
        self.model = None
        self.scaler = None
        
        # --- CẤU HÌNH TỐI ƯU ---
        # [MẸO 1] Tăng Window Size lên 30 (nhìn lại 2.5 phút) để thấy rõ xu hướng hơn
        self.window_size = 30 
        
        self.num_features = 5 
        
        self.data_history = []     
        self.new_data_buffer = []  
        self.RETRAIN_THRESHOLD = 100 # Gom nhiều dữ liệu hơn chút rồi mới học
        self.MAX_TRAIN_SIZE = 20000 
        self.is_training = False 
        
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
                    print(f"⚠️ Model không khớp input. Đã xóa.")
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
        
        self.new_data_buffer.append(full_features)
        if len(self.new_data_buffer) >= self.RETRAIN_THRESHOLD and not self.is_training:
             threading.Thread(target=self.retrain_model).start()

    def save_to_csv(self, data_row):
        try:
            cols = ['lux', 't_panel', 't_env', 'hum', 'pump']
            df = pd.DataFrame([data_row], columns=cols)
            header = not os.path.exists(self.data_file)
            df.to_csv(self.data_file, mode='a', header=header, index=False)
        except: pass

    # [MỚI] Hàm chuyên dụng để chấm điểm mô hình
    def evaluate_model(self, X_test, y_test):
        try:
            # 1. Dự báo thử trên tập Test
            y_pred_scaled = self.model.predict(X_test, verbose=0)
            
            # 2. Giải nén (Inverse Scale) để ra nhiệt độ thật (Độ C)
            # Vì scaler đang scale cả 5 cột, ta phải tạo mảng giả để inverse
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
                "mae": round(mae, 3),   # Sai số trung bình (Độ C)
                "rmse": round(rmse, 3), # Sai số bình phương
                "r2": round(r2, 3)      # Độ khớp (Càng gần 1 càng tốt)
            }
            
            print(f"📊 ĐÁNH GIÁ: Sai số MAE = {mae:.2f}°C | R2 Score = {r2:.2f}")
            
        except Exception as e:
            print(f"⚠️ Lỗi đánh giá: {e}")

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
            STEPS_AHEAD = 12 
            
            for i in range(self.window_size, len(scaled_data) - STEPS_AHEAD):
                X.append(scaled_data[i-self.window_size:i, :]) 
                y.append(scaled_data[i + STEPS_AHEAD, 1])
                
            X, y = np.array(X), np.array(y)

            # [QUAN TRỌNG] Chia tập Train (80%) và Test (20%)
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
                
                # [MẸO 2] Dùng Huber Loss thay cho MSE 
                # Huber chịu nhiễu tốt hơn (nếu cảm biến thỉnh thoảng bị gai)
                self.model.compile(optimizer='adam', loss=Huber())
            
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
            print(f"❌ Lỗi Retrain: {e}")
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
                pred_temp_5min = inversed_row[0, 1]
            except:
                pred_temp_5min = current_temp_real
        else:
            pred_temp_5min = current_temp_real

        return {
            "current_temp": round(current_temp_real, 2),
            "pred_temp_5min": round(pred_temp_5min, 2),
            "accuracy_mae": self.last_metrics["mae"] # Trả về sai số để hiển thị lên Web nếu cần
        }

    def predict_scenario(self, pump_action):
        if len(self.data_history) < 1: return None
        current = self.data_history[-1][1]
        return (current - 2.5) if pump_action == 1 else (current + 1.0)