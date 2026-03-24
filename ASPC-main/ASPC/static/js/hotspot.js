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
    
        socket.on('system_alert', function(data) {
            const level = String(data?.level || '').toUpperCase();
    
            if (level === 'CRITICAL') {
                alert('🚨 CẢNH BÁO KHẨN CẤP: ' + data.message);
            } else if (level === 'WARNING') {
                alert('⚠️ CẢNH BÁO: ' + data.message);
            }
    
            const alertList = document.getElementById('alert-list');
            if (alertList) {
                const alertItem = document.createElement('div');
                alertItem.className = 'alert-item ' + level.toLowerCase();
                alertItem.innerHTML = `<strong>${level}:</strong> ${data.message} <small>(${new Date().toLocaleTimeString()})</small>`;
                alertList.appendChild(alertItem);
                setTimeout(() => alertItem.remove(), 30000);
            }
        });
    

    console.log("🚀 ASPC Hotspot Radar Engine đã sẵn sàng!");



});