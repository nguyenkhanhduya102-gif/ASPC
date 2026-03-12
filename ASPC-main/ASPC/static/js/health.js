/**
 * File: health.js
 * Nhiệm vụ: Nhận dữ liệu 'sensor_data' từ Server (app.py) và hiển thị lên giao diện.
 * Không thực hiện tính toán phức tạp ở đây, chỉ hiển thị.
 */

const socket = io();

// Các ngưỡng đánh giá (để đổi màu)
const THRESHOLD_BAD = 60;
const THRESHOLD_GOOD = 80;

socket.on('connect', () => {
    console.log("✅ Đã kết nối tới Server Health Monitor");
});

socket.on('sensor_data', (data) => {
    // 1. Kiểm tra dữ liệu hợp lệ
    if (!data) return;

    // 2. Cập nhật các số liệu cơ bản
    // Lưu ý: data.p_actual và data.p_theory đã được server gửi xuống
    updateText('p-actual', (data.p_actual !== undefined ? data.p_actual : '--') + ' W');
    updateText('p-theory', (data.p_theory !== undefined ? data.p_theory : '--') + ' W');
    updateText('health-lux', (data.lux !== undefined ? data.lux : '--') + ' Lux');
    
    // Hiển thị % Sức khỏe
    const score = data.health_score !== undefined ? data.health_score : 0;
    updateText('health-percent', score + '%');

    // 3. Tính tổn thất hiển thị (100% - Sức khỏe)
    let loss = 100 - score;
    if (loss < 0) loss = 0;
    updateText('power-loss', loss.toFixed(1) + '%');

    // 4. Cập nhật Vòng tròn trạng thái (Visual Gauge)
    updateHealthGauge(score);

    // 5. Cập nhật Trạng thái & Lời khuyên
    updateAdvice(score, data.lux);
});

/**
 * Hàm cập nhật màu sắc vòng tròn
 */
function updateHealthGauge(score) {
    const circle = document.getElementById('health-circle');
    if (!circle) return;

    let color = '#28a745'; // Xanh (Tốt)
    
    if (score < THRESHOLD_BAD) color = '#dc3545'; // Đỏ (Kém)
    else if (score < THRESHOLD_GOOD) color = '#ffc107'; // Vàng (Khá)

    // Hiệu ứng xoay màu CSS
    circle.style.background = `conic-gradient(${color} ${score}%, #eee ${score}%)`;
}

/**
 * Hàm đưa ra lời khuyên dựa trên điểm số
 */
function updateAdvice(score, lux) {
    const statusBadge = document.getElementById('health-status');
    const adviceText = document.getElementById('health-advice');
    
    if (!statusBadge || !adviceText) return;

    // Nếu trời tối (Lux thấp), không đánh giá
    if (lux < 500) {
        statusBadge.innerText = "Chờ Nắng";
        statusBadge.style.background = "gray";
        adviceText.innerText = "Trời tối, hệ thống tạm nghỉ đánh giá.";
        return;
    }

    if (score >= THRESHOLD_GOOD) {
        statusBadge.innerText = "Rất Tốt";
        statusBadge.style.background = "#28a745"; // Xanh
        adviceText.innerText = "Tấm pin hoạt động hiệu quả. Không cần can thiệp.";
    } else if (score >= THRESHOLD_BAD) {
        statusBadge.innerText = "Cần Chú Ý";
        statusBadge.style.background = "#ffc107"; // Vàng
        adviceText.innerText = "Hiệu suất giảm nhẹ. Có thể do bụi hoặc nhiệt độ cao.";
    } else {
        statusBadge.innerText = "Cảnh Báo!";
        statusBadge.style.background = "#dc3545"; // Đỏ
        adviceText.innerText = "Hiệu suất giảm nghiêm trọng! Hãy kiểm tra bụi bẩn hoặc bật rửa pin.";
        
        // (Tùy chọn) Hiện badge đỏ trên menu nếu cần
        // showNavBadge(true); 
    }
}

// Hàm tiện ích cập nhật text an toàn
function updateText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
}