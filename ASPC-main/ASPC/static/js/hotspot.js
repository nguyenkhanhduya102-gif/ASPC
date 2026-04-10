/**
 * ASPC Hotspot Radar System
 * Chịu trách nhiệm hiển thị chẩn đoán AI thời gian thực
 */
document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    // Mapping các element trên HTML
    const ui = {
        riskDisplay: document.getElementById('risk-display'),
        reasonDisplay: document.getElementById('hotspot-reason'),
        actionDisplay: document.getElementById('hotspot-action'),
        deltaTDisplay: document.getElementById('delta-t'),
        mainCard: document.getElementById('main-card'),
        statusBadge: document.getElementById('status-badge')
    };


    
        
        socket.on('sensor_data', (data) => {
            if (data.hotspot_risk !== undefined) {
                ui.riskDisplay.innerText = data.hotspot_risk + '%';
            }
            ui.reasonDisplay.innerText = data.hotspot_reason || "Đang phân tích...";
            ui.actionDisplay.innerText = data.hotspot_action || "--";
            ui.deltaTDisplay.innerText = data.hotspot_delta_t ?? "0";
    
            const status = (data.hotspot_status || "NORMAL").toUpperCase();
    
            ui.mainCard.classList.remove('status-danger', 'status-warning', 'status-success');
            ui.statusBadge.classList.remove('bg-danger', 'bg-warning', 'bg-success', 'text-dark');
    
            if (status === 'DANGER') {
                ui.mainCard.classList.add('status-danger');
                ui.statusBadge.classList.add('bg-danger');
                ui.statusBadge.innerHTML = '<i class="fas fa-radiation-alt"></i> NGUY HIỂM: HOTSPOT';
            } else if (status === 'WARNING') {
                ui.mainCard.classList.add('status-warning');
                ui.statusBadge.classList.add('bg-warning', 'text-dark');
                ui.statusBadge.innerHTML = '<i class="fas fa-exclamation-triangle"></i> CẢNH BÁO NHẸ';
            } else {
                ui.mainCard.classList.add('status-success');
                ui.statusBadge.classList.add('bg-success');
                ui.statusBadge.innerHTML = '<i class="fas fa-check-circle"></i> HỆ THỐNG AN TOÀN';
            }
        });
    





        // 1. NẾU LÀ CẢNH BÁO TỪ CAMERA AI (YOLO)
if(alert.type === 'camera_ai') {
    const box = document.getElementById('hotspot-status-box');
    
    // Cập nhật thanh Bụi nếu là lỗi Dusty
    let issueName = alert.issue_name.toLowerCase();
    if(issueName.includes('dusty')) {
        document.getElementById('ai-dust-val').innerText = alert.confidence + '%';
        document.getElementById('ai-dust-bar').style.width = alert.confidence + '%';
        document.getElementById('ai-dust-bar').className = 'progress-bar bg-warning';
    }

    // ==========================================
    // [LOGIC MỚI] ĐƯA RA LỜI KHUYÊN THEO TỪNG LỖI
    // ==========================================
    let action_msg = "";
    let alert_color = "#ef4444"; // Mặc định màu đỏ
    let bg_color = "#fef2f2";

    if (issueName.includes('defective') || issueName.includes('crack')) {
        action_msg = "⚠️ NGUY HIỂM: Hỏng vật lý/Nứt kính. Yêu cầu NGẮT ĐIỆN và thay thế. TUYỆT ĐỐI KHÔNG BẬT BƠM NƯỚC để tránh chập điện!";
        alert_color = "#dc2626"; // Đỏ đậm
    } 
    else if (issueName.includes('dusty')) {
        action_msg = "💡 LỜI KHUYÊN: Bề mặt bám bụi diện rộng. Kích hoạt Robot lau chùi hoặc Bơm nước rửa trôi để phục hồi hiệu suất.";
        alert_color = "#f59e0b"; // Màu cam vàng
        bg_color = "#fffbeb";
    }
    else if (issueName.includes('bird')) {
        action_msg = "💡 LỜI KHUYÊN: Bám phân chim (Điểm nóng cục bộ). Cần phun sương làm mềm và kích hoạt gạt nước.";
        alert_color = "#f97316"; // Màu cam
        bg_color = "#fff7ed";
    }
    else {
        action_msg = "Phát hiện vật cản bất thường. Cử nhân viên kiểm tra bề mặt.";
    }

    // Đổ giao diện ra Web
    box.innerHTML = `
        <div class="alert-item" style="animation: pulse 1s infinite alternate; background-color: ${bg_color}; border-left: 4px solid ${alert_color}; padding: 15px; border-radius: 8px;">
            <div class="fw-bold mb-1" style="color: ${alert_color};"><i class="fas fa-crosshairs me-1"></i> AI PHÁT HIỆN: ${alert.issue_name.toUpperCase()}</div>
            <span class="small text-danger fw-bold">${alert.message}</span>
            <div class="mt-2 small fw-bold text-dark p-2 rounded" style="background: rgba(0,0,0,0.05); border-left: 2px solid ${alert_color};">${action_msg}</div>
        </div>
    `;

    // Tự động trả về An toàn sau 10s nếu hết lỗi
    setTimeout(() => {
        box.innerHTML = `
            <div class="alert-item safe" style="border-left: 4px solid #10b981; background: #ecfdf5; padding: 15px; border-radius: 8px;">
                <div class="fw-bold text-success mb-1"><i class="fas fa-check-circle me-1"></i> Bề mặt an toàn</div>
                <span class="small text-muted">AI đang liên tục quét và phân tích. Chưa phát hiện vật cản.</span>
            </div>
        `;
    }, 10000);
}
    







    console.log("🚀 ASPC Hotspot Radar Engine đã sẵn sàng!");



});