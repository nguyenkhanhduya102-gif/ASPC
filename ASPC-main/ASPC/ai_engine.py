import numpy as np
import pandas as pd
import os
import threading
import joblib
from collections import deque
from tensorflow.keras.models import load_model
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score 
import tensorflow as tf
import time 

class SolarLSTM:
    def __init__(self, mac_address="default"):
        self.mac_address = mac_address
        os.makedirs("models_ai", exist_ok=True)
        
        self.model_path = f'models_ai/lstm_{self.mac_address}.h5'
        self.data_file = f'models_ai/data_{self.mac_address}.csv'
        self.scaler_file = f'models_ai/scaler_lstm_{self.mac_address}.pkl'
        
        self.model = None
        self.scaler = None
        
        
        self.SEQ_LEN = 10 
        self.num_features = 5 
        
        
        self.sequence_buffer = deque(maxlen=self.SEQ_LEN)
        
        self.MAX_TRAIN_SIZE = 50000 
        self.is_training = False 
        self.retrain_interval = 30 * 24 * 60 * 60
        self.last_retrain_time = time.time()
        self.last_metrics = {"mae": 0, "rmse": 0, "r2": 0}

        self.load_scaler()
        self.load_ai_model()

    def load_scaler(self):
        if os.path.exists(self.scaler_file):
            try: self.scaler = joblib.load(self.scaler_file)
            except: self.scaler = StandardScaler()
        else:
            default_scaler = "models_ai/scaler_lstm.pkl"
            if os.path.exists(default_scaler):
                try:
                    self.scaler = joblib.load(default_scaler)
                    joblib.dump(self.scaler, self.scaler_file)
                except: self.scaler = StandardScaler()
            else: self.scaler = StandardScaler()

    def load_ai_model(self):
        if os.path.exists(self.model_path):
            try: self.model = load_model(self.model_path, compile=False)
            except: self.model = None
        else:
            default_model = "models_ai/lstm_final.h5" 
            if os.path.exists(default_model):
                try:
                    self.model = load_model(default_model, compile=False)
                    self.model.save(self.model_path) 
                except: self.model = None

    def _get_current_sequence(self, current_vector):
       
        # nhân bản phần tử hiện tại 
        if len(self.sequence_buffer) == 0:
            for _ in range(self.SEQ_LEN):
                self.sequence_buffer.append(current_vector)
        else:
            self.sequence_buffer.append(current_vector)
            
        return np.array(self.sequence_buffer)

    def predict(self, temp_env, humidity, lux, wind_speed, pump_status):
        if self.model and self.scaler:
            try:
                # 1. Scale vector hiện tại
                current_vec = np.array([[temp_env, humidity, lux, wind_speed, pump_status]])
                scaled_vec = self.scaler.transform(current_vec)[0]
                
                # 2. Đẩy vào bộ đệm để tạo Sliding Window shape = (10, 5)
                seq = self._get_current_sequence(scaled_vec)
                
                # 3. Reshape thành 3D (1, SEQ_LEN, 5)
                X_lstm = seq.reshape((1, self.SEQ_LEN, self.num_features))
                
                # 4. Dự báo
                preds = self.model.predict(X_lstm, verbose=0)[0]
                
                if len(preds) == 2:
                    pred_now, pred_future = preds[0], preds[1]
                else:
                    pred_now = preds[0]
                    pred_future = pred_now + 1.5 if pump_status == 0 else pred_now - 2.0
            except Exception as e:
                print(f"Lỗi AI Predict: {e}")
                pred_now = temp_env + (lux / 4000.0)
                pred_future = pred_now + 1.0
        else:
            pred_now = temp_env + (lux / 4000.0)
            pred_future = pred_now + 1.0

        self._save_background_data(temp_env, humidity, lux, wind_speed, pump_status, pred_now)

        return {
            "current_t_cell": round(float(pred_now), 2),
            "pred_temp_15min": round(float(pred_future), 2),
            "accuracy_mae": self.last_metrics["mae"]
        }

    def predict_scenario(self, temp_env, humidity, lux, wind_speed, target_pump_status):
        if not self.model or not self.scaler: return temp_env + 2.0
        try:
            # 1. Tạo vector giả định
            scenario_vec = np.array([[temp_env, humidity, lux, wind_speed, target_pump_status]])
            scaled_scenario = self.scaler.transform(scenario_vec)[0]
            
            # 2. Tạo sequence ảo (lấy 9 bước thật trong quá khứ + 1 bước ảo ở tương lai)
            virtual_seq = list(self.sequence_buffer)
            if len(virtual_seq) == self.SEQ_LEN:
                virtual_seq.pop(0) # Bỏ phần tử cũ nhất
            virtual_seq.append(scaled_scenario)
            
            while len(virtual_seq) < self.SEQ_LEN:
                virtual_seq.append(scaled_scenario)
                
            seq = np.array(virtual_seq)
            X_lstm = seq.reshape((1, self.SEQ_LEN, self.num_features))
            
            preds = self.model.predict(X_lstm, verbose=0)[0]
            
            if len(preds) == 2: return float(preds[1])
            else: return float(preds[0]) + (1.5 if target_pump_status == 0 else -2.0)
        except:
            return temp_env + 2.0
            
    def _save_background_data(self, temp_env, humidity, lux, wind_speed, pump_status, target_t_cell):
        #Lưu data phục vụ retrain
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
                    print(f"[{self.mac_address}] Đã đến hạn bảo trì AI. Khởi động Retrain LSTM...")
                    self.last_retrain_time = current_time
                    threading.Thread(target=self.retrain_model).start()
        except: pass

    def evaluate_model(self, X_test, y_test):
        try:
            y_pred = self.model.predict(X_test, verbose=0)
            if isinstance(y_pred, tf.Tensor):
                y_pred = y_pred.numpy()
                
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)
            
            self.last_metrics = {
                "mae": round(mae, 3),   
                "rmse": round(rmse, 3), 
                "r2": round(r2, 3)      
            }
            print(f" ĐÁNH GIÁ TRẠM {self.mac_address}: MAE = {mae:.2f}°C | R2 = {r2:.2f}")
        except Exception as e:
            print(f" Lỗi đánh giá: {e}")

    def create_dataset(self, X, y):
        #Tạo siling cho qtrinh retrain
        Xs, ys = [], []
        for i in range(len(X) - self.SEQ_LEN + 1):
            Xs.append(X[i : (i + self.SEQ_LEN)])
            ys.append(y[i + self.SEQ_LEN - 1])
        return np.array(Xs), np.array(ys)

    def retrain_model(self):
        self.is_training = True
        try:
            if not os.path.exists(self.data_file): return
            
            df = pd.read_csv(self.data_file)
            if len(df) > self.MAX_TRAIN_SIZE: df = df.tail(self.MAX_TRAIN_SIZE)

            # NHÃN TƯƠNG LAI: Shift target lên 15 dòng
            df['target_future'] = df['target_t_cell'].shift(-15)
            df = df.dropna()
            
            X = df[['temp_env', 'humidity', 'lux', 'wind_speed', 'pump_status']].values
            y = df[['target_t_cell', 'target_future']].values

            # Đảm bảo có đủ data cho window size
            if len(X) < self.SEQ_LEN + 100: return

            # Fit lại Scaler
            self.scaler.fit(X)
            joblib.dump(self.scaler, self.scaler_file)
            X_scaled = self.scaler.transform(X)

            # ÁP DỤNG SLIDING WINDOW 
            X_lstm, y_lstm = self.create_dataset(X_scaled, y)

            split_idx = int(len(X_lstm) * 0.8)
            X_train, X_test = X_lstm[:split_idx], X_lstm[split_idx:]
            y_train, y_test = y_lstm[:split_idx], y_lstm[split_idx:]

            # Mở khóa các layer để fine-tune
            if self.model is not None:
                for layer in self.model.layers:
                    layer.trainable = True
                
                # Cập nhật Huber Loss 
                self.model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001), loss=tf.keras.losses.Huber(delta=1.0), metrics=['mae'])
                
                early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
                
                self.model.fit(
                    X_train, y_train, 
                    validation_data=(X_test, y_test),
                    batch_size=32, epochs=20, verbose=0, callbacks=[early_stop]
                )
                
                self.evaluate_model(X_test, y_test)
                self.model.save(self.model_path)
            
            # Xóa bớt data cũ 
            df.tail(1000).to_csv(self.data_file, index=False)
            
        except Exception as e:
            print(f" Lỗi Retrain Trạm {self.mac_address}: {e}")
        finally: 
            self.is_training = False









    