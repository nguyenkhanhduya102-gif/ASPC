# hotspot_engine.py
import math

class HotspotDetector:
    def __init__(self):
        self.consecutive_danger_count = 0
        # Các hằng số Vật lý Nhiệt (Có thể tinh chỉnh theo datasheet của tấm pin)
        self.NOCT = 45.0        # Nhiệt độ hoạt động định mức (Thường 45-47 độ C)
        self.G_NOCT = 800.0     # Bức xạ chuẩn tại NOCT (W/m2)
        
    def detect(self, t_panel, t_env, lux, p_actual, p_theory):
        # 1. ƯỚC LƯỢNG BỨC XẠ (G) TỪ LUX
        # Trong thực tế 100,000 Lux ~ 1000 W/m2 (Hệ số xấp xỉ 0.01)
        g_irr = lux * 0.01 
        
        # 2. BẢN SAO SỐ NHIỆT ĐỘNG LỰC HỌC (Thermodynamic Twin)
        if g_irr > 50:
            # Tính T_ideal theo mô hình vật lý NOCT
            t_ideal_base = t_env + (g_irr / self.G_NOCT) * (self.NOCT - 20.0)
            
            # Tinh chỉnh: Năng lượng quang không thành điện -> Biến thành nhiệt
            # Nếu P_actual sụt giảm, phần năng lượng đó đang bị đốt thành nhiệt cục bộ
            power_loss_ratio = max(0, (p_theory - p_actual) / p_theory) if p_theory > 0 else 0
            
            # Phạt thêm nhiệt độ (Penalty) nếu có năng lượng bị kẹt lại
            t_ideal = t_ideal_base + (power_loss_ratio * 3.0) 
        else:
            t_ideal = t_env
            power_loss_ratio = 0.0
            
        delta_t = t_panel - t_ideal
        
        # 3. MA TRẬN CHẨN ĐOÁN LỖI (Diagnostic Matrix)
        risk = 0.0
        status = "NORMAL"
        reason = "Cân bằng nhiệt động lực học ổn định."
        action = "Hệ thống hoạt động tối ưu."

        if g_irr > 200: # Chỉ phân tích khi trời có nắng rõ
            # Trọng số: Delta_T chiếm 60%, Sụt công suất chiếm 40%
            score_temp = min(max(delta_t, 0), 20.0) / 20.0  # Max rủi ro ở 20 độ lệch
            score_power = min(power_loss_ratio, 0.5) / 0.5  # Max rủi ro ở 50% sụt áp
            risk = (score_temp * 60) + (score_power * 40)

        risk_percent = round(risk, 1)

        # 4. CÂY QUYẾT ĐỊNH XỬ LÝ (Actionable AI)
        if risk_percent > 65:
            self.consecutive_danger_count += 1
            if self.consecutive_danger_count >= 3:
                status = "DANGER"
                # Phân tách rõ ràng giữa Bụi bẩn và Lỗi phần cứng
                if delta_t > 10.0 and power_loss_ratio > 0.3:
                    reason = "🔥 NGUY HIỂM: Phát hiện Hotspot cốt lõi (Cell/Diode hỏng) gây tích nhiệt."
                    action = "❌ Yêu cầu cô lập chuỗi pin. Gọi Drone/Kỹ thuật viên kiểm tra quang nhiệt."
                else:
                    reason = "Bề mặt thất thoát hiệu suất do bụi bẩn tích tụ dày."
                    action = "💦 Kích hoạt vòi phun nước rửa bề mặt."
        
        elif risk_percent > 35:
            status = "WARNING"
            reason = "Cảnh báo sớm: Lệch pha cân bằng nhiệt."
            action = "Theo dõi thêm, chờ AI lập kế hoạch phun nước."
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