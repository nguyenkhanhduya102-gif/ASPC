import json

class SolarOptimizer:
    def __init__(self):
        self.alpha_p = 0.004      # Hệ số nhiệt độ (0.4%/độ C)
        self.p_pump_cons = 20.0   # Công suất bơm (W)
        self.elec_price = 3015    # Giá mặc định (Bậc 6)
        self.temp_safe_max = 50.0  # Nhiệt độ an toàn tối đa 
        self.g_min = 200 
        
        # Bảng giá điện sinh hoạt EVN (Cập nhật 2024 - Tham khảo)
        # Cấu trúc: (Ngưỡng kWh, Giá VNĐ)
        self.evn_tiers = [
            (50, 1728),   # Bậc 1: 0-50 kWh
            (100, 1786),  # Bậc 2: 51-100 kWh
            (200, 2074),  # Bậc 3: 101-200 kWh
            (300, 2612),  # Bậc 4: 201-300 kWh
            (400, 2919),  # Bậc 5: 301-400 kWh
            (99999, 3015) # Bậc 6: 401 trở lên
        ]

    def update_params(self, alpha, p_pump, monthly_kwh):
        """
        Cập nhật tham số từ người dùng.
        monthly_kwh: Số điện trung bình nhà dùng mỗi tháng.
        """
        self.alpha_p = float(alpha) / 100.0
        self.p_pump_cons = float(p_pump)
        
        # Tự động xác định giá điện dựa trên bậc thang (Marginal Price)
        usage = float(monthly_kwh)
        detected_price = 0
        
        for limit, price in self.evn_tiers:
            detected_price = price
            if usage <= limit:
                break
        
        self.elec_price = detected_price
        print(f"💰 Optimizer: Với {usage} kWh/tháng -> Áp dụng giá Bậc thang: {self.elec_price} đ/kWh")

    def calculate_decision(self, g_meas, p_max_stc, t_pred_off, t_pred_on):
        # ... (Giữ nguyên logic tính toán cũ) ...
        
        # 1. Ràng buộc an toàn
        if t_pred_off > self.temp_safe_max:
            return True, 0, 0, "⚠️ BẬT bơm bảo vệ (Quá nhiệt)!"

        if g_meas < self.g_min:
            return False, 0, 0, "☁️ Bức xạ thấp, tắt bơm."

        # 2. Tính toán năng lượng
        loss_factor_off = self.alpha_p * (t_pred_off - 25)
        p_pv_off = p_max_stc * (1 - loss_factor_off)
        
        loss_factor_on = self.alpha_p * (t_pred_on - 25)
        p_pv_on = p_max_stc * (1 - loss_factor_on)

        time_hours = 5 / 60.0 # 5 phút
        
        # Lợi ích: Thêm được bao nhiêu Wh điện?
        e_gain = (p_pv_on - p_pv_off) * time_hours
        
        # Chi phí: Mất bao nhiêu Wh điện nuôi bơm?
        e_cost = self.p_pump_cons * time_hours
        
        delta_e = e_gain - e_cost

        # 3. Tính tiền (Dùng giá điện bậc thang đã xác định)
        profit_vnd = (delta_e / 1000.0) * self.elec_price

        if profit_vnd > 0:
            return True, delta_e, profit_vnd, f"✅ Có lãi ({profit_vnd:.1f}đ). Giá điện: {self.elec_price}đ"
        else:
            return False, delta_e, profit_vnd, f"📉 Lỗ ({profit_vnd:.1f}đ). Tắt tiết kiệm."