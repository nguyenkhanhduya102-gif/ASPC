/**
 * File: index.js
 */
const socket = io();
const currentDeviceMac = localStorage.getItem('device_id') || 'ESP32_DEFAULT';
let currentMode = 'MANUAL'; 

let tempChart;
const maxDataPoints = 20; 
let historyLabels = [];
let historyData = [];
let latestAiPred = null;

document.addEventListener("DOMContentLoaded", function () {
    initChart();
    socket.emit('request_current_mode', { mac_address: currentDeviceMac });
    setupControlButtons();
});

function initChart() {
    const ctx = document.getElementById('temperatureChart').getContext('2d');
    tempChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [], 
            datasets: [
                { label: 'Nhiệt Độ Tấm Pin (°C)', data: [], borderColor: '#e67e22', backgroundColor: 'rgba(230, 126, 34, 0.2)', borderWidth: 2, tension: 0.3, fill: true, pointBackgroundColor: '#e67e22', pointRadius: 4 },
                { label: 'Dự Báo AI (15 phút tới)', data: [], borderColor: '#00d2d3', backgroundColor: 'transparent', borderWidth: 2, borderDash: [5, 5], tension: 0, fill: false, pointBackgroundColor: '#00d2d3', pointRadius: 5, pointStyle: 'rectRot' }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: { y: { beginAtZero: false, title: { display: false } }, x: { display: true, ticks: { autoSkip: true, maxTicksLimit: 6 } } },
            animation: { duration: 0 } 
        }
    });
}

function updateChartData(currentTemp) {
    if (!tempChart) return;
    const now = new Date();
    const timeNowStr = now.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit', second:'2-digit'});
    
    historyLabels.push(timeNowStr);
    historyData.push(currentTemp);
    if (historyLabels.length > maxDataPoints) { historyLabels.shift(); historyData.shift(); }

    const futureTime = new Date(now.getTime() + 15 * 60000); 
    const futureTimeStr = futureTime.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit'});
    const futureVal = latestAiPred !== null ? latestAiPred : currentTemp;

    tempChart.data.labels = [...historyLabels, futureTimeStr];
    tempChart.data.datasets[0].data = [...historyData, null];

    const emptyPadding = Array(historyData.length - 1).fill(null);
    tempChart.data.datasets[1].data = [...emptyPadding, currentTemp, futureVal];
    tempChart.update();
}

function updateText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
}


// 1. NHẬN DỮ LIỆU CẢM BIẾN (CHỈ DÙNG 1 HÀM NÀY)

socket.on('sensor_data', (data) => {
    updateText('current-temp', data.temp_env + ' °C');
    updateText('humidity', data.humidity + ' %');
    updateText('light-intensity', data.lux + ' Lux');
    updateText('solar-temp', data.temp_panel + ' °C');
    
    if(data.health_score !== undefined) updateText('efficiency', Math.round(data.health_score) + '%');
    
    const dustEl = document.getElementById('dust-level');
    if (dustEl && typeof data.dust_level === 'number') dustEl.textContent = `${data.dust_level.toFixed(1)} %`;

    updateChartData(data.temp_panel);

    // Xử lý 2 ô Làm mát / Làm sạch
    const boxCooling = document.getElementById('status-cooling');
    const boxCleaning = document.getElementById('status-cleaning');
    const iconCooling = document.getElementById('icon-cooling');
    const iconCleaning = document.getElementById('icon-cleaning');
    const reasonText = document.getElementById('pump-reason-text');

    if (boxCooling && boxCleaning && data.pump_mode) {
        boxCooling.className = "p-2 border rounded text-center bg-light text-muted";
        boxCleaning.className = "p-2 border rounded text-center bg-light text-muted";
        iconCooling.className = "fas fa-snowflake fs-4 mb-1";
        iconCleaning.className = "fas fa-shower fs-4 mb-1";
        boxCooling.style.backgroundColor = ""; boxCleaning.style.backgroundColor = "";

        if (data.pump_status === 1 || data.pump_status === true || data.pump_status === "1") {
            if (data.pump_mode === 'COOLING') {
                boxCooling.className = "p-2 border border-primary rounded text-center text-white shadow-sm";
                boxCooling.style.backgroundColor = "#0d6efd";
                iconCooling.className = "fas fa-snowflake fs-4 mb-1 fa-spin";
            } else if (data.pump_mode === 'CLEANING') {
                boxCleaning.className = "p-2 border border-info rounded text-center text-white shadow-sm";
                boxCleaning.style.backgroundColor = "#0dcaf0";
                iconCleaning.className = "fas fa-shower fs-4 mb-1 fa-bounce";
            } else if (data.pump_mode === 'MANUAL') {
                boxCooling.className = "p-2 border border-warning rounded text-center text-dark shadow-sm bg-warning";
                boxCleaning.className = "p-2 border border-warning rounded text-center text-dark shadow-sm bg-warning";
                iconCooling.className = "fas fa-cog fs-4 mb-1 fa-spin";
                iconCleaning.className = "fas fa-cog fs-4 mb-1 fa-spin";
            }
        }
        if (data.pump_reason) reasonText.innerHTML = `<i class="fas fa-robot me-1 text-primary"></i> <b>AI:</b> ${data.pump_reason}`;
    }

    // Logic nút Bật Tắt:
    // Nếu web báo MANUAL nhưng giả lập backend (của bạn) lại tự bật bơm -> nó sẽ đổi nút loạn lên.
    // Ở đây ta ép giao diện hiển thị đúng với trạng thái thực tế từ backend gửi về.
        // Dựa vào pump_mode để web biết đang bật LÀM MÁT (cool) hay LÀM SẠCH (clean)
        
    if (data.pump_status == 0) {
        // Nếu bơm đang tắt -> Ép tắt CẢ 2 NÚT trên UI để không bao giờ bị kẹt
        updatePumpStatusUI(0, 'cool');
        updatePumpStatusUI(0, 'clean');
    } else {
        // Nếu bơm đang bật -> Thằng nào được bật thì sáng nút thằng đó
        const uiType = (data.pump_mode === 'CLEANING') ? 'clean' : 'cool';
        updatePumpStatusUI(1, uiType);
    }
});


// 2. NHẬN DỮ LIỆU HIỆU QUẢ KINH TẾ

socket.on('efficiency_data', (data) => {
    const profitEl = document.getElementById('eco-profit');
    const energyEl = document.getElementById('eco-energy');
    
    if(profitEl && data.y_today_vnd !== undefined) {
        profitEl.innerText = new Intl.NumberFormat('vi-VN').format(Math.round(data.y_today_vnd)) + " đ";
    }
    
    // Bắt đúng biến x_today_kwh từ Backend
    if(energyEl && data.x_today_kwh !== undefined) {
        energyEl.innerText = data.x_today_kwh.toFixed(3) + " kWh";
    }
});

socket.on('ai_data', (data) => {
    if (data.ai && data.ai.pred_temp_15min) {
        latestAiPred = data.ai.pred_temp_15min;
        let currentT = historyData.length > 0 ? historyData[historyData.length - 1] : 0;
        if (currentT > 0) {
            let rate = (latestAiPred - currentT).toFixed(2);
            let sign = rate > 0 ? '+' : '';
            updateText('temp-rate', `${sign}${rate} °C/15p`);
        }
    }
});



// 3. XỬ LÝ CHUYỂN CHẾ ĐỘ & ĐIỀU KHIỂN NÚT

socket.on('mode_update', (data) => {
    currentMode = data.mode;
    if (currentMode === 'AUTO') {
        document.getElementById('mode_auto').checked = true;
        document.getElementById("mode-desc").innerText = "Hệ thống tự động theo ngưỡng nhiệt độ.";
    } else if (currentMode === 'SMART_ECO') {
        document.getElementById('mode_smart').checked = true;
        document.getElementById("mode-desc").innerText = "AI tự động tính toán Lãi/Lỗ.";
    } else {
        document.getElementById('mode_manual').checked = true;
        document.getElementById("mode-desc").innerText = "Bạn toàn quyền kiểm soát.";
    }
    
    // Khóa/Mở tất cả 4 nút
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
        socket.emit('switch_mode', {mac_address: currentDeviceMac, mode: mode });
    });
});

function setupControlButtons() {
    // Nút LÀM MÁT -> Gửi chữ COOL
    const btnCoolOn = document.getElementById('btn-cool-on');
    const btnCoolOff = document.getElementById('stop-cool-btn');
    if(btnCoolOn) btnCoolOn.addEventListener('click', () => sendCommand('2', 'COOL'));
    if(btnCoolOff) btnCoolOff.addEventListener('click', () => sendCommand('0', 'COOL'));

    // Nút LÀM SẠCH -> Gửi chữ CLEAN
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
    // Gửi lệnh lên Server
    socket.emit('send_control', {mac_address: currentDeviceMac, command: cmd, type: type, user_id: 'WEB' });
    
    // Ép UI nhảy ngay lập tức cho mượt
    let tempStatus = (cmd === '2') ? 1 : 0;
    updatePumpStatusUI(tempStatus, type.toLowerCase()); 
}

// Cập nhật trạng thái từng nút bấm độc lập
function updatePumpStatusUI(status, type) {
    const statusText = document.getElementById(`${type}-status`);
    const btnOn = document.getElementById(`btn-${type}-on`);
    const btnOff = document.getElementById(`stop-${type}-btn`);
    
    if (!statusText || !btnOn || !btnOff) return;

    if (status == 1) {
        statusText.innerHTML = `Trạng thái: <strong style="color:green">ĐANG CHẠY...</strong>`;
        statusText.style.color = "green";
    } else {
        statusText.innerHTML = `Trạng thái: <strong>Đang Tắt</strong>`;
        statusText.style.color = "#7f8c8d";
    }

    if (currentMode === 'MANUAL') {
        if (status == 1) {
            btnOn.disabled = true; btnOn.style.opacity = "0.5"; btnOn.style.cursor = "not-allowed";
            btnOff.disabled = false; btnOff.style.opacity = "1"; btnOff.style.cursor = "pointer";
        } else {
            btnOn.disabled = false; btnOn.style.opacity = "1"; btnOn.style.cursor = "pointer";
            btnOff.disabled = true; btnOff.style.opacity = "0.5"; btnOff.style.cursor = "not-allowed";
        }
    } 
}