# hotspot_engine.py

class HotspotDetector:
    def __init__(self):
        self.consecutive_danger_count = 0

    def detect(self, t_panel, t_env, lux, p_actual, p_theory):
        
        # 1. Tính nhiệt độ lý thuyết (Physics-Informed)
        # Tấm pin thường nóng hơn môi trường dựa trên cường độ bức xạ (Lux)
        irradiance_ratio = lux / 80000.0 if lux > 0 else 0
        t_ideal = t_env + (28.0 * irradiance_ratio) # 28°C là hằng số chênh lệch chuẩn NOCT
        
        delta_t = t_panel - t_ideal
        
        # 2. Tính độ sụt giảm hiệu suất thực tế
        power_drop_ratio = 0.0
        if p_theory > 0:
            power_drop_ratio = max(0, (p_theory - p_actual) / p_theory)

        # 3. Tính toán chỉ số rủi ro (Risk Score 0-100)
        risk = 0.0
        if lux > 10000: # Chỉ phân tích khi có nắng
            # Trọng số 70% nhiệt độ, 30% công suất
            score_temp = min(max(delta_t, 0), 25.0) / 25.0 
            score_power = min(power_drop_ratio, 0.6) / 0.6
            risk = (score_temp * 70) + (score_power * 30)

        risk_percent = round(risk, 1)

        # 4. Phân loại trạng thái và đưa ra chỉ dẫn Bảo trì dự báo
        status = "NORMAL"
        reason = "Hệ thống hoạt động ổn định."
        action = "Tiếp tục giám sát."

        if risk_percent > 65:
            self.consecutive_danger_count += 1
            if self.consecutive_danger_count >= 3:
                status = "DANGER"
                # Phân loại nguyên nhân dựa trên dữ liệu
                if power_drop_ratio < 0.25:
                    reason = "Phát hiện tích tụ nhiệt cục bộ (Bụi bẩn/Vật cản nhẹ)."
                    action = "Kích hoạt phun nước làm sạch bề mặt."
                else:
                    reason = "Sụt giảm công suất nghiêm trọng (Nứt cell/Lỗi Diode)."
                    action = "Cần kiểm tra kỹ thuật trực tiếp tại tấm pin."
        elif risk_percent > 35:
            status = "WARNING"
            reason = "Nhiệt độ hơi cao so với lý thuyết."
            action = "Theo dõi thêm hoặc vệ sinh nhẹ."
            self.consecutive_danger_count = 0
        else:
            self.consecutive_danger_count = 0

        return {
            "risk_percent": risk_percent,
            "delta_t": round(delta_t, 1),
            "status": status,
            "reason": reason,
            "action": action
        }