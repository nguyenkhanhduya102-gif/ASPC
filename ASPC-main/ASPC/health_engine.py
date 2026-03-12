import numpy as np
import json
import os
from sklearn.linear_model import LinearRegression

# Tên file lưu cấu hình
CALIB_FILE = 'calibration.json'

class SolarHealthEngine:
    def __init__(self):
        # Giá trị mặc định (sẽ bị ghi đè nếu có file save)
        self.p_max = 100.0   # Công suất danh định (Watt)
        self.area = 1.0      # Diện tích (m2) - Dùng để tính hiệu suất quang điện nếu cần
        
        # Các tham số tự học
        self.k_factor = 0.00015 
        self.a = 0.0
        self.b = 0.0
        self.use_regression = False
        
        # Bộ đệm training
        self.training_buffer_lux = [] 
        self.training_buffer_G = []
        
        self.load_calibration()

    def load_calibration(self):
        """Đọc toàn bộ thông số (User cài đặt + AI học được)"""
        if os.path.exists(CALIB_FILE):
            try:
                with open(CALIB_FILE, 'r') as f:
                    data = json.load(f)
                    # Load thông số người dùng nhập
                    self.p_max = float(data.get('p_max', 100.0))
                    self.area = float(data.get('area', 1.0))
                    
                    # Load thông số AI học
                    self.k_factor = data.get('k', 0.00015)
                    self.a = data.get('a', 0.0)
                    self.b = data.get('b', 0.0)
                    self.use_regression = data.get('use_regression', False)
                    print(f"✅ Health Engine: Đã load cấu hình (Pmax={self.p_max}W, Area={self.area}m2)")
            except: pass

    def save_calibration(self):
        """Lưu tất cả xuống file"""
        data = {
            'p_max': self.p_max,
            'area': self.area,
            'k': self.k_factor,
            'a': self.a,
            'b': self.b,
            'use_regression': self.use_regression
        }
        with open(CALIB_FILE, 'w') as f:
            json.dump(data, f)

    def update_user_params(self, p_max, area):
        """Hàm để Web gọi khi người dùng nhập thông số mới"""
        if float(p_max) > 0:
            self.p_max = float(p_max)
            self.area = float(area)
            self.save_calibration() # Lưu ngay lập tức
            print(f"🔄 Đã cập nhật thông số tấm pin: {self.p_max}W - {self.area}m2")
            return True
        return False

    def learn(self, lux, power_watts):
        # 1. Kiểm tra điều kiện
        if lux < 10000 or power_watts <= 0: return
        
        # Dùng self.p_max thay vì hằng số
        ratio = power_watts / self.p_max 
        if ratio < 0.3: return

        # 2. Tính G inverted
        G_derived = (power_watts * 1000) / self.p_max

        self.training_buffer_lux.append(lux)
        self.training_buffer_G.append(G_derived)
        
        if len(self.training_buffer_lux) > 500:
            self.training_buffer_lux.pop(0)
            self.training_buffer_G.pop(0)

        # 3. Học (Chỉ chạy khi đủ dữ liệu)
        if len(self.training_buffer_lux) >= 50:
            np_lux = np.array(self.training_buffer_lux).reshape(-1, 1)
            np_G = np.array(self.training_buffer_G)

            # Pha 1: k
            k_values = np_G / np_lux.flatten()
            new_k = np.mean(k_values)
            self.k_factor = (self.k_factor * 0.9) + (new_k * 0.1)

            # Pha 2: Hồi quy
            reg = LinearRegression().fit(np_lux, np_G)
            self.a = reg.coef_[0]
            self.b = reg.intercept_
            
            if reg.score(np_lux, np_G) > 0.85:
                self.use_regression = True
            
            self.save_calibration()

    def calculate_health(self, lux, power_watts):
        if lux <= 0: return 0.0, 0.0, 0.0

        # Tính G_meas
        if self.use_regression:
            G_meas = (self.a * lux) + self.b
        else:
            G_meas = self.k_factor * lux

        if G_meas < 50: return 0.0, 0.0, 0.0

        # Tính công suất lý thuyết dựa trên P_MAX động
        theoretical_power = (G_meas * self.p_max) / 1000.0
        
        if theoretical_power == 0: return 0.0, 0.0, 0.0
        
        health_score = (power_watts / theoretical_power) * 100.0
        health_score = max(0, min(100, health_score))
        
        return round(health_score, 1), round(G_meas, 1), round(theoretical_power, 2)