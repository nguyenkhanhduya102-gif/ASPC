function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = text; 
}

// Hàm format giờ từ chuỗi API (VD: "2024-05-20 15:00:00" -> "15:00, 20/05")
function formatTime(dt_txt) {
    if(!dt_txt) return '--';
    const parts = dt_txt.split(' ');
    const time = parts[1].substring(0, 5); // Lấy HH:MM
    const dateParts = parts[0].split('-');
    return `<span class="text-primary fw-bold">${time}</span><br><small class="text-muted">${dateParts[2]}/${dateParts[1]}</small>`;
}

async function loadWeather() {
  try {
    const resp = await fetch('/api/weather', { cache: 'no-store' });
    const payload = await resp.json().catch(() => ({}));

    if (!resp.ok || payload.status !== 'success') {
      throw new Error(payload?.message || 'Không lấy được dữ liệu thời tiết.');
    }

    const data = payload.data || {};
    const forecast = data.forecast || [];

    // Lấy mốc thời tiết gần nhất
    const first = forecast[0] || {};
    
    // Tìm Min/Max
    let minT = 999, maxT = -999;
    forecast.forEach(item => {
      if(item.temp < minT) minT = item.temp;
      if(item.temp > maxT) maxT = item.temp;
    });
    if(minT === 999) minT = '--';
    if(maxT === -999) maxT = '--';

    // Cập nhật CỤM BÊN TRÁI
    setText('w-city', `<i class="fas fa-map-marker-alt me-2"></i> ${data.location || 'Trạm Quan Trắc'}`);
    setText('w-desc', (first.weather || 'Không xác định').toUpperCase());
    setText('w-temp', (first.temp !== undefined) ? `${Math.round(first.temp)}°` : '--°');
    setText('w-min', minT !== '--' ? Math.round(minT) : '--');
    setText('w-max', maxT !== '--' ? Math.round(maxT) : '--');

    // Cập nhật 4 THẺ BÊN PHẢI
    setText('w-humidity', (first.humidity !== undefined) ? `${first.humidity} %` : '-- %');
    setText('w-wind', (first.wind_speed !== undefined) ? `${first.wind_speed} m/s` : '-- m/s');
    setText('w-clouds', (first.clouds !== undefined) ? `${first.clouds} %` : '-- %');
    
    const pop = (first.pop !== undefined) ? Math.round(first.pop) : 0;
    setText('w-pressure', `${pop} %`); 

    // --- VẼ BẢNG DỰ BÁO CÁC GIỜ TỚI ---
    const tbody = document.getElementById('weather-rows');
    if (tbody) {
        if (forecast.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-muted">Không có dữ liệu dự báo.</td></tr>`;
        } else {
            let html = '';
            // Bỏ qua mốc đầu tiên (vì đang hiển thị ở thẻ to rồi), lặp từ mốc thứ 1 trở đi (tối đa lấy 5 mốc)
            for(let i = 1; i < Math.min(forecast.length, 6); i++) {
                const item = forecast[i];
                
                // Xác định Icon Thời tiết cơ bản dựa vào description
                let icon = '<i class="fas fa-cloud text-secondary fs-4"></i>';
                let descLower = (item.weather || '').toLowerCase();
                let statusBadge = '<span class="badge bg-success-subtle text-success">Làm mát bình thường</span>';
                
                if(descLower.includes('rain') || descLower.includes('mưa')) {
                    icon = '<i class="fas fa-cloud-showers-heavy text-primary fs-4"></i>';
                    statusBadge = '<span class="badge bg-warning-subtle text-warning">Tạm dừng bơm (Có mưa)</span>';
                } else if(descLower.includes('sun') || descLower.includes('clear')) {
                    icon = '<i class="fas fa-sun text-warning fs-4"></i>';
                }

                html += `
                <tr class="border-bottom">
                    <td class="text-start ps-4">${formatTime(item.time)}</td>
                    <td>
                        <div class="d-flex flex-column align-items-center justify-content-center">
                            ${icon}
                            <span class="small text-muted text-capitalize mt-1">${item.weather}</span>
                        </div>
                    </td>
                    <td><h5 class="m-0 fw-bold">${Math.round(item.temp)}°C</h5></td>
                    <td class="text-info fw-bold">${item.humidity}% <i class="fas fa-tint fs-6 ms-1"></i></td>
                    <td>
                        <span class="d-block text-secondary small"><i class="fas fa-cloud me-1"></i> ${item.clouds}%</span>
                        <span class="d-block text-secondary small"><i class="fas fa-wind me-1"></i> ${item.wind_speed} m/s</span>
                    </td>
                    <td class="pe-4">${statusBadge}</td>
                </tr>
                `;
            }
            tbody.innerHTML = html;
        }
    }

  } catch (err) {
    console.error("Weather load error:", err);
    setText('w-city', '<i class="fas fa-exclamation-triangle me-2 text-warning"></i> Lỗi API');
    setText('w-desc', 'Vui lòng kiểm tra lại Key OpenWeather');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadWeather();
  setInterval(loadWeather, 10 * 60 * 1000);
});

