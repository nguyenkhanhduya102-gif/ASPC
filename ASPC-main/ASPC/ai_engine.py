import numpy as np
import pandas as pd
import os
import threading
import joblib
from tensorflow.keras.models import load_model, Sequential
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score 
import tensorflow as tf
import time 

class SolarMLP:
    def __init__(self, mac_address="default"):
        self.mac_address = mac_address
        
        # Tạo thư mục models_ai nếu chưa có
        os.makedirs("models_ai", exist_ok=True)
        
        # Tạo tên file ĐỘC LẬP cho từng thiết bị trong thư mục models_ai
        self.model_path = f'models_ai/mlp16_{self.mac_address}.h5'
        self.data_file = f'models_ai/data_{self.mac_address}.csv'
        self.scaler_file = f'models_ai/scaler_{self.mac_address}.pkl'
        
        self.model = None
        self.scaler = None
        
        # Cấu hình MLP (Không cần window_size như LSTM)
        self.num_features = 5 # [temp_env, humidity, lux, wind_speed, pump_status]
        self.data_history = []     
        self.new_data_buffer = []  

        self.MAX_TRAIN_SIZE = 50000 
        self.is_training = False 
        
        self.retrain_interval = 30 * 24 * 60 * 60 # 30 ngày
        self.last_retrain_time = time.time()
        
        self.last_metrics = {"mae": 0, "rmse": 0, "r2": 0}

        self.load_scaler()
        self.load_ai_model()

    def load_scaler(self):
        if os.path.exists(self.scaler_file):
            try:
                self.scaler = joblib.load(self.scaler_file)
            except:
                self.scaler = StandardScaler()
        else:
            default_scaler = "models_ai/scaler_mlp16.pkl"
            if os.path.exists(default_scaler):
                try:
                    self.scaler = joblib.load(default_scaler)
                    joblib.dump(self.scaler, self.scaler_file)
                except:
                    self.scaler = StandardScaler()
            else:
                self.scaler = StandardScaler()

    def load_ai_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = load_model(self.model_path)
            except:
                self.model = None
        else:
            default_model = "models_ai/mlp16_final.h5"
            if os.path.exists(default_model):
                try:
                    self.model = load_model(default_model)
                    self.model.save(self.model_path) 
                    print(f"[{self.mac_address}] Đã copy Model gốc làm Base.")
                except:
                    self.model = None

    def update_data(self, basic_data):
        pass # MLP không cần update_data liên tục như LSTM, lưu ngầm ở hàm predict

    def predict(self, temp_env, humidity, lux, wind_speed, pump_status):
        """Hàm dự báo tức thời không phụ thuộc history (Do bản chất của MLP)"""
        if self.model and self.scaler:
            try:
                X_in = np.array([[temp_env, humidity, lux, wind_speed, pump_status]])
                X_scaled = self.scaler.transform(X_in)
                preds = self.model.predict(X_scaled, verbose=0)[0]
                
                # Model xuất ra 2 giá trị [T_hien_tai, T_tuong_lai_15p]
                if len(preds) == 2:
                    pred_now, pred_future = preds[0], preds[1]
                else:
                    pred_now = preds[0]
                    pred_future = pred_now + 1.5 if pump_status == 0 else pred_now - 2.0
            except:
                pred_now = temp_env + (lux / 4000.0)
                pred_future = pred_now + 1.0
        else:
            pred_now = temp_env + (lux / 4000.0)
            pred_future = pred_now + 1.0

        # Lưu ngầm
        self._save_background_data(temp_env, humidity, lux, wind_speed, pump_status, pred_now)

        return {
            "current_t_cell": round(float(pred_now), 2),
            "pred_temp_15min": round(float(pred_future), 2),
            "accuracy_mae": self.last_metrics["mae"]
        }

    def predict_scenario(self, temp_env, humidity, lux, wind_speed, target_pump_status):
        if not self.model or not self.scaler: 
            return temp_env + 2.0
            
        try:
            X_in = np.array([[temp_env, humidity, lux, wind_speed, target_pump_status]])
            X_scaled = self.scaler.transform(X_in)
            preds = self.model.predict(X_scaled, verbose=0)[0]
            
            # Lấy giá trị tương lai (index 1)
            if len(preds) == 2:
                return float(preds[1])
            else:
                return float(preds[0]) + (1.5 if target_pump_status == 0 else -2.0)
        except:
            return temp_env + 2.0

    def _save_background_data(self, temp_env, humidity, lux, wind_speed, pump_status, target_t_cell):
        """Lưu ngầm dữ liệu để phục vụ hàm retrain_model()"""
        try:
            cols = ['temp_env', 'humidity', 'lux', 'wind_speed', 'pump_status', 'target_t_cell']
            df = pd.DataFrame([[temp_env, humidity, lux, wind_speed, pump_status, target_t_cell]], columns=cols)
            header = not os.path.exists(self.data_file)
            df.to_csv(self.data_file, mode='a', header=header, index=False)
            
            current_time = time.time()
            if current_time - self.last_retrain_time >= self.retrain_interval and not self.is_training:
                with open(self.data_file, 'r') as f:
                    row_count = sum(1 for _ in f)
                
                if row_count > 1000:
                    print(f"[{self.mac_address}] Đã đến hạn bảo trì AI. Khởi động Retrain MLP-16...")
                    self.last_retrain_time = current_time
                    threading.Thread(target=self.retrain_model).start()
        except: pass

    def evaluate_model(self, X_test, y_test):
        try:
            y_pred_scaled = self.model.predict(X_test, verbose=0)
            if isinstance(y_pred_scaled, tf.Tensor):
                y_pred_scaled = y_pred_scaled.numpy()
                
            mae = mean_absolute_error(y_test, y_pred_scaled)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred_scaled))
            r2 = r2_score(y_test, y_pred_scaled)
            
            self.last_metrics = {
                "mae": round(mae, 3),   
                "rmse": round(rmse, 3), 
                "r2": round(r2, 3)      
            }
            print(f" ĐÁNH GIÁ TRẠM {self.mac_address}: MAE = {mae:.2f}°C | R2 = {r2:.2f}")
        except Exception as e:
            print(f" Lỗi đánh giá: {e}")

    def retrain_model(self):
        self.is_training = True
        try:
            if not os.path.exists(self.data_file): return
            
            df = pd.read_csv(self.data_file)
            if len(df) > self.MAX_TRAIN_SIZE: df = df.tail(self.MAX_TRAIN_SIZE)

            # Lọc đầu vào
            X = df[['temp_env', 'humidity', 'lux', 'wind_speed', 'pump_status']].values
            
            # NHÃN TƯƠNG LAI: Shift target lên 15 dòng
            df['target_future'] = df['target_t_cell'].shift(-15)
            df = df.dropna()
            
            X = df[['temp_env', 'humidity', 'lux', 'wind_speed', 'pump_status']].values
            # Target giờ bao gồm 2 cột: Hiện tại và Tương lai
            y = df[['target_t_cell', 'target_future']].values

            if len(X) < 300: return

            self.scaler.fit(X)
            joblib.dump(self.scaler, self.scaler_file)
            X_scaled = self.scaler.transform(X)

            split_idx = int(len(X) * 0.8)
            X_train, X_test = X_scaled[:split_idx], X_scaled[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]

            if self.model is None:
                self.model = Sequential([
                    Input(shape=(self.num_features,)),
                    Dense(16, activation='relu'),
                    Dense(8, activation='relu'),
                    Dense(2, activation='linear') # FIX QUAN TRỌNG: 2 Outputs!
                ])
                self.model.compile(optimizer='adam', loss='mse')
            else:
                for layer in self.model.layers:
                    layer.trainable = True
                self.model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001), loss='mse')

            early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
            
            self.model.fit(
                X_train, y_train, 
                validation_data=(X_test, y_test),
                batch_size=32, epochs=20, verbose=0, callbacks=[early_stop]
            )
            
            self.evaluate_model(X_test, y_test)
            self.model.save(self.model_path)
            
            df.tail(1000).to_csv(self.data_file, index=False)
            
        except Exception as e:
            print(f" Lỗi Retrain Trạm {self.mac_address}: {e}")
        finally: 
            self.is_training = False