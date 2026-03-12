/**
 * File: index.js
 * Tính năng: Vẽ biểu đồ với hiệu ứng "Đuôi dự báo" (Projection Tail)
 */

const socket = io();
let currentMode = 'MANUAL'; 
let lastControlTime = 0;
// --- KHAI BÁO BIẾN DỮ LIỆU ---
let tempChart;
const maxDataPoints = 20; // Số điểm lịch sử giữ lại

// Mảng lưu trữ lịch sử thực tế (để không bị mất khi vẽ lại đuôi)
let historyLabels = [];
let historyData = [];
let latestAiPred = null;

document.addEventListener("DOMContentLoaded", function () {
    initChart();
    socket.emit('request_current_mode');
    setupControlButtons();
});

// --- 1. CẤU HÌNH BIỂU ĐỒ (STYLE GIỐNG HỆT ẢNH) ---
function initChart() {
    const ctx = document.getElementById('temperatureChart').getContext('2d');
    tempChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [], 
            datasets: [
                {
                    // ĐƯỜNG 1: THỰC TẾ (MÀU CAM)
                    label: 'Nhiệt Độ Tấm Pin (°C)',
                    data: [],
                    borderColor: '#e67e22',       // Cam đậm
                    backgroundColor: 'rgba(230, 126, 34, 0.2)', // Nền cam nhạt
                    borderWidth: 2,
                    tension: 0.3,                 
                    fill: true,                   // Bật tô nền
                    pointBackgroundColor: '#e67e22',
                    pointRadius: 4
                },
                {
                    // ĐƯỜNG 2: DỰ BÁO (XANH CYAN NÉT ĐỨT)
                    label: 'Dự Báo AI (5 phút tới)',
                    data: [],
                    borderColor: '#00d2d3',       // Xanh cyan
                    backgroundColor: 'transparent', 
                    borderWidth: 2,
                    borderDash: [5, 5],           // Nét đứt cầu nối
                    tension: 0,                   // Đường thẳng nối 2 điểm
                    fill: false,
                    pointBackgroundColor: '#00d2d3',
                    pointRadius: 5,               // Điểm tròn dự báo to hơn chút
                    pointStyle: 'rectRot'         // Hình thoi cho khác biệt
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            // Format lại tooltip cho dễ đọc
                            return context.dataset.label + ': ' + context.parsed.y + ' °C';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    title: { display: false }
                },
                x: {
                    display: true,
                    ticks: { autoSkip: true, maxTicksLimit: 6 }
                }
            },
            animation: { duration: 0 } 
        }
    });
}

// --- HÀM VẼ BIỂU ĐỒ NÂNG CAO ---
function updateChartData(currentTemp) {
    if (!tempChart) return;

    const now = new Date();
    const timeNowStr = now.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit', second:'2-digit'});
    
    // 1. Cập nhật mảng Lịch Sử (History Arrays)
    historyLabels.push(timeNowStr);
    historyData.push(currentTemp);

    // Giới hạn độ dài lịch sử
    if (historyLabels.length > maxDataPoints) {
        historyLabels.shift();
        historyData.shift();
    }

    // 2. Tạo điểm Dự Báo Tương Lai (Future Point)
    // Tính thời gian 5 phút sau
    const futureTime = new Date(now.getTime() + 5 * 60000); 
    const futureTimeStr = futureTime.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit'});

    // Lấy giá trị AI (Nếu chưa có thì lấy bằng hiện tại để không bị lỗi)
    const futureVal = latestAiPred !== null ? latestAiPred : currentTemp;

    // 3. Tái cấu trúc dữ liệu để hiển thị lên Chart
    // Mẹo: Dataset "Thực tế" sẽ có thêm 1 điểm null ở cuối để nhường chỗ cho tương lai
    // Dataset "Dự báo" sẽ toàn null, chỉ có 2 điểm cuối cùng nối với nhau.

    // A. Label: Lịch sử + 1 nhãn tương lai
    tempChart.data.labels = [...historyLabels, futureTimeStr];

    // B. Dataset Thực tế: Lịch sử + null
    tempChart.data.datasets[0].data = [...historyData, null];

    // C. Dataset Dự báo: Một mảng toàn null + Điểm hiện tại + Điểm tương lai
    // Mục đích: Để vẽ một đường nối từ điểm thực tế cuối cùng đến điểm dự báo
    const emptyPadding = Array(historyData.length - 1).fill(null);
    tempChart.data.datasets[1].data = [...emptyPadding, currentTemp, futureVal];

    // 4. Cập nhật giao diện
    tempChart.update();
}

// --- 2. XỬ LÝ SOCKET (GIỮ NGUYÊN LOGIC CŨ) ---

socket.on('sensor_data', (data) => {
    updateText('current-temp', data.temp_env + ' °C');
    updateText('humidity', data.humidity + ' %');
    updateText('light-intensity', data.lux + ' Lux');
    updateText('solar-temp', data.temp_panel+ ' °C');
    if(data.health_score !== undefined) updateText('efficiency', data.health_score + '%');
    updatePumpStatusUI(data.pump_status, 'cool');
    // Chỉ cập nhật trạng thái bơm nếu KHÔNG CÓ lệnh điều khiển nào trong 3 giây qua

    // GỌI HÀM VẼ BIỂU ĐỒ
    updateChartData(data.temp_panel);
});

socket.on('ai_data', (data) => {
    if (data.ai && data.ai.pred_temp_5min) {
        latestAiPred = data.ai.pred_temp_5min;
        
        // Hiển thị tốc độ tăng
        let currentT = historyData.length > 0 ? historyData[historyData.length - 1] : 0;
        if (currentT > 0) {
            let rate = (latestAiPred - currentT).toFixed(2);
            let sign = rate > 0 ? '+' : '';
            updateText('temp-rate', `${sign}${rate} °C/5p`);
        }
    }
});

socket.on('economic_data', (data) => {
    if(data.profit) document.getElementById('eco-profit').innerText = Math.round(data.profit) + " đ";
    if(data.delta_e) document.getElementById('eco-energy').innerText = data.delta_e.toFixed(2) + " Wh";
});

socket.on('mode_update', (data) => {
    currentMode = data.mode;
    if (currentMode === 'AUTO') {
        document.getElementById('mode_auto').checked = true;
        document.getElementById("mode-desc").innerText = "Hệ thống tự động theo ngưỡng nhiệt độ.";
        document.getElementById("economic-stats").style.display = "none";
    } else if (currentMode === 'SMART_ECO') {
        document.getElementById('mode_smart').checked = true;
        document.getElementById("mode-desc").innerText = "AI tự động tính toán Lãi/Lỗ.";
        document.getElementById("economic-stats").style.display = "block";
    } else {
        document.getElementById('mode_manual').checked = true;
        document.getElementById("mode-desc").innerText = "Bạn toàn quyền kiểm soát.";
        document.getElementById("economic-stats").style.display = "none";
    }
    
    const btns = [
        document.getElementById('btn-cool-on'), document.getElementById('stop-cool-btn'),
        document.getElementById('btn-clean-on'), document.getElementById('stop-clean-btn')
    ];
    btns.forEach(btn => {
        if(btn) btn.disabled = (currentMode !== 'MANUAL');
    });
});

document.querySelectorAll('input[name="sys_mode"]').forEach((elem) => {
    elem.addEventListener("change", function(event) {
        let mode = "MANUAL";
        if (event.target.id === "mode_auto") mode = "AUTO";
        else if (event.target.id === "mode_smart") mode = "SMART_ECO";
        socket.emit('switch_mode', { mode: mode });
    });
});

// --- 4. HÀM ĐIỀU KHIỂN & UI (ĐÃ NÂNG CẤP CHỐNG SPAM NÚT) ---
function setupControlButtons() {
    const btnCoolOn = document.getElementById('btn-cool-on');
    const btnCoolOff = document.getElementById('stop-cool-btn');
    
    if(btnCoolOn) btnCoolOn.addEventListener('click', () => sendCommand('1', 'COOL'));
    if(btnCoolOff) btnCoolOff.addEventListener('click', () => sendCommand('0', 'COOL'));
    
    // Nếu có nút Clean (Rửa pin)
    const btnCleanOn = document.getElementById('btn-clean-on');
    const btnCleanOff = document.getElementById('stop-clean-btn');
    if(btnCleanOn) btnCleanOn.addEventListener('click', () => sendCommand('2', 'CLEAN'));
    if(btnCleanOff) btnCleanOff.addEventListener('click', () => sendCommand('0', 'CLEAN'));
}

function sendCommand(cmd, type) {
    if (currentMode !== 'MANUAL') {
        alert("⚠️ Vui lòng chuyển sang chế độ THỦ CÔNG để điều khiển!");
        return;
    }

    // 1. Gửi lệnh đi
    socket.emit('send_control', { command: cmd, type: type, user_id: 'WEB' });
    // B. [QUAN TRỌNG] Cập nhật giao diện NGAY LẬP TỨC (Không chờ Server)
    // Nếu cmd = '2' (Bật) -> Trạng thái giả lập là 1
    // Nếu cmd = '0' (Tắt) -> Trạng thái giả lập là 0
    let tempStatus = (cmd === '2') ? 1 : 0;
    
    updatePumpStatusUI(tempStatus, type.toLowerCase());
    lastControlTime = Date.now();   
}

// --- 2. SỬA HÀM CẬP NHẬT GIAO DIỆN (Logic khóa nút) ---
function updatePumpStatusUI(status, type) {
    const statusText = document.getElementById(`${type}-status`);
    const btnOn = document.getElementById(`btn-${type}-on`);
    const btnOff = document.getElementById(`stop-${type}-btn`);
    
    if (!statusText || !btnOn || !btnOff) return;

    // 1. CẬP NHẬT GIAO DIỆN CHỮ (Áp dụng cho mọi chế độ)
    if (status == 1) {
        statusText.innerHTML = `Trạng thái: <strong style="color:green">ĐANG CHẠY...</strong> <i class="fas fa-spinner fa-spin"></i>`;
        statusText.style.color = "green";
    } else {
        statusText.innerHTML = `Trạng thái: <strong>Đang Tắt</strong>`;
        statusText.style.color = "#7f8c8d";
    }

    // 2. XỬ LÝ KHÓA/MỞ NÚT (Chỉ áp dụng cho chế độ MANUAL)
    if (currentMode === 'MANUAL') {
        if (status == 1) {
            // Đang Bật -> Khóa nút Bật, Mở nút Tắt
            btnOn.disabled = true;
            btnOn.style.opacity = "0.5";
            btnOn.style.cursor = "not-allowed";

            btnOff.disabled = false;
            btnOff.style.opacity = "1";
            btnOff.style.cursor = "pointer";
        } else {
            // Đang Tắt -> Mở nút Bật, Khóa nút Tắt
            btnOn.disabled = false;
            btnOn.style.opacity = "1";
            btnOn.style.cursor = "pointer";

            btnOff.disabled = true;
            btnOff.style.opacity = "0.5";
            btnOff.style.cursor = "not-allowed";
        }
    } 
}
function updateText(id, text) {
    const el = document.getElementById(id);
    if (el) {
        el.innerText = text;
    }
}
// 1. Lắng nghe sự kiện từ Server
socket.on('system_alert', (data) => {
    showSystemAlert(data.level, data.message);
});

// 2. Hàm hiển thị thông báo lên màn hình
function showSystemAlert(level, message) {
    // Tìm thẻ div cảnh báo
    let alertBox = document.getElementById('system-alert-box');
    
    // Nếu chưa có thẻ div này trong HTML thì tạo mới (Phòng trường hợp quên viết trong HTML)
    if (!alertBox) {
        alertBox = document.createElement('div');
        alertBox.id = 'system-alert-box';
        document.body.appendChild(alertBox);
    }

    // Xác định màu sắc dựa trên level (success, warning, danger)
    let colorClass = 'alert-info'; // Mặc định màu xanh dương
    let icon = '<i class="fas fa-info-circle"></i>';

    if (level === 'success') {
        colorClass = 'alert-success'; // Xanh lá
        icon = '<i class="fas fa-check-circle"></i>';
    } else if (level === 'warning') {
        colorClass = 'alert-warning'; // Vàng
        icon = '<i class="fas fa-exclamation-triangle"></i>';
    } else if (level === 'danger') {
        colorClass = 'alert-danger'; // Đỏ
        icon = '<i class="fas fa-fire"></i>';
    }

    // Nội dung HTML của hộp thoại
    alertBox.className = `alert ${colorClass} shadow-lg`; // Bootstrap classes
    alertBox.style.zIndex = "9999"; // Đảm bảo nổi lên trên cùng
    
    alertBox.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <strong style="font-size: 1.2em; margin-right: 10px;">${icon} THÔNG BÁO HỆ THỐNG:</strong>
                <br>
                <span style="font-size: 1.1em;">${message}</span>
            </div>
            <button type="button" class="btn-close" onclick="document.getElementById('system-alert-box').style.display='none'"></button>
        </div>
    `;

    // Hiện hộp thoại
    alertBox.style.display = 'block';

    // Tự động tắt sau 5 giây
    if (window.alertTimeout) clearTimeout(window.alertTimeout);
    window.alertTimeout = setTimeout(() => {
        alertBox.style.display = 'none';
    }, 7000); // 7 giây cho người dùng kịp đọc
}
// ==========================================================
// [MỚI] CẬP NHẬT DỮ LIỆU HIỆU QUẢ (EFFICIENCY)
// ==========================================================
socket.on('efficiency_data', (data) => {
    // 1. Cập nhật số kWh tăng thêm
    const kwhElem = document.getElementById('eff-gain-kwh');
    if (kwhElem) {
        let sign = data.x_today_kwh >= 0 ? '+' : '';
        kwhElem.innerHTML = `${sign}${data.x_today_kwh} <span style="font-size:0.6em">kWh</span>`;
    }

    // 2. Cập nhật tiền tiết kiệm
    const vndElem = document.getElementById('eff-save-vnd');
    if (vndElem) {
        // Format số tiền (ví dụ: 1,200 đ)
        let money = new Intl.NumberFormat('vi-VN').format(data.y_today_vnd);
        vndElem.innerText = `${money} đ`;
    }

    // 3. Cập nhật % tăng trưởng tháng
    const percentElem = document.getElementById('eff-percent-month');
    const progressElem = document.getElementById('eff-progress-bar');
    
    if (percentElem && progressElem) {
        let p = data.z_month_percent;
        percentElem.innerText = `+${p}%`;
        
        // Giới hạn thanh progress max 100% để không bị vỡ giao diện
        let width = p * 5; // Nhân 5 để dễ nhìn (ví dụ tăng 5% thì thanh dài 25%)
        if (width > 100) width = 100;
        progressElem.style.width = `${width}%`;
    }
});

// Khi load trang, lấy giá điện hiện tại để hiển thị
fetch('/api/get_params')
    .then(r => r.json())
    .then(data => {
        // Cập nhật giá điện vào phần chú thích (tính toán dựa trên alpha_p và bảng giá trong backend)
        // Vì API get_params hiện tại chưa trả về giá tiền cụ thể (chỉ trả kWh), 
        // bạn có thể cập nhật API hoặc tạm để trống. 
        // Tuy nhiên, logic backend đã dùng đúng giá điện để tính ra VND rồi.
    });