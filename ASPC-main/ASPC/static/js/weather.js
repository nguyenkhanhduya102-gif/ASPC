function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerText = text;
}

function showError(message) {
  const box = document.getElementById('weather-error');
  if (!box) return;
  box.style.display = 'block';
  box.innerText = message;
}

function hideError() {
  const box = document.getElementById('weather-error');
  if (!box) return;
  box.style.display = 'none';
  box.innerText = '';
}

function renderRows(forecast) {
  const tbody = document.getElementById('weather-rows');
  if (!tbody) return;

  if (!Array.isArray(forecast) || forecast.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-muted">Không có dữ liệu dự báo.</td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = forecast.map(item => `
    <tr>
      <td>${item.time ?? '--'}</td>
      <td class="fw-bold">${(item.temp ?? '--')}</td>
      <td>${item.humidity ?? '--'}</td>
      <td>${item.clouds ?? '--'}</td>
      <td>${item.wind_speed ?? '--'}</td>
      <td>${item.weather ?? '--'}</td>
    </tr>
  `).join('');
}

async function loadWeather() {
  hideError();
  setText('weather-updated', 'Đang tải...');

  try {
    const resp = await fetch('/api/weather', { cache: 'no-store' });
    const payload = await resp.json().catch(() => ({}));

    if (!resp.ok || payload.status !== 'success') {
      throw new Error(payload?.message || 'Không lấy được dữ liệu thời tiết.');
    }

    const data = payload.data || {};
    const forecast = data.forecast || [];

    setText('weather-location', data.location || '--');

    const first = forecast[0] || {};
    setText('weather-temp', (first.temp !== undefined && first.temp !== null) ? `${first.temp} °C` : '--');
    setText('weather-humidity', (first.humidity !== undefined && first.humidity !== null) ? `${first.humidity} %` : '--');
    setText('weather-clouds', (first.clouds !== undefined && first.clouds !== null) ? `${first.clouds} %` : '--');
    setText('weather-wind', (first.wind_speed !== undefined && first.wind_speed !== null) ? `${first.wind_speed} m/s` : '--');
    setText('weather-desc', first.weather || '--');

    renderRows(forecast);

    const now = new Date();
    setText('weather-updated', `Cập nhật: ${now.toLocaleString('vi-VN')}`);
  } catch (err) {
    showError(err?.message || 'Có lỗi khi tải dữ liệu thời tiết.');
    setText('weather-updated', 'Lỗi tải dữ liệu');
    renderRows([]);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('weather-refresh');
  if (btn) btn.addEventListener('click', loadWeather);
  loadWeather();
});

