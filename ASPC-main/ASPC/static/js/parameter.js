/**
 * File: parameter.js
 * Nhiệm vụ:
 * 1. Tải thông số từ Server (Python) qua API /api/get_params
 * 2. Gửi thông số về Server qua API /api/save_params để lưu vào calibration.json
 * 3. Validate dữ liệu trước khi gửi để tránh làm lỗi Health Engine.
 */

document.addEventListener('DOMContentLoaded', function() {
    // 1. Tải thông số ngay khi vào trang
    loadSettingsFromAPI();

    // 2. Lắng nghe sự kiện bấm nút Lưu
    const paramForm = document.getElementById('paramForm');
    if (paramForm) {
        paramForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Chặn load lại trang
            saveSettingsToAPI();
        });
    }
});

/**
 * Hàm tải thông số từ Server
 * Endpoint: GET /api/get_params
 */
function loadSettingsFromAPI() {
    // Hiển thị trạng thái đang tải (Optional UI polish)
    console.log("Đang tải cấu hình từ Server...");

    fetch('/api/get_params')
        .then(response => {
            if (!response.ok) throw new Error("Server phản hồi lỗi!");
            return response.json();
        })
        .then(data => {
            // Điền dữ liệu vào form (ID khớp với parameter.html)
            const pMaxInput = document.getElementById('p_max');
            const areaInput = document.getElementById('area');

            if (pMaxInput) pMaxInput.value = data.p_max;
            if (areaInput) areaInput.value = data.area;
            
            console.log("✅ Đã tải thông số:", data);
        })
        .catch(err => {
            console.error("Lỗi tải thông số:", err);
            // Không alert lỗi khi mới vào trang để tránh phiền, chỉ log console
        });
}

/**
 * Hàm lưu thông số về Server
 * Endpoint: POST /api/save_params
 */
function saveSettingsToAPI() {
    // Lấy giá trị từ form
    const pMaxInput = document.getElementById('p_max');
    const areaInput = document.getElementById('area');
    
    const pMaxVal = parseFloat(pMaxInput.value);
    const areaVal = parseFloat(areaInput.value);
    // Lấy thêm thông số kinh tế
    const pPumpVal = parseFloat(document.getElementById('p_pump').value);
    const monthlyKwhVal = parseFloat(document.getElementById('monthly_kwh').value);
    const alphaVal = parseFloat(document.getElementById('alpha_p').value);
    // --- VALIDATION (QUAN TRỌNG) ---
    // Kiểm tra kỹ trước khi gửi để tránh làm hỏng file JSON trên server
    if (isNaN(pMaxVal) || pMaxVal <= 0) {
        alert("⚠️ Lỗi: Công suất Pmax phải là số lớn hơn 0!");
        pMaxInput.focus();
        return;
    }
    if (isNaN(areaVal) || areaVal <= 0) {
        alert("⚠️ Lỗi: Diện tích phải là số lớn hơn 0!");
        areaInput.focus();
        return;
    }
    if (isNaN(monthlyKwhVal) || monthlyKwhVal < 0) {
        alert("Vui lòng nhập mức tiêu thụ điện hợp lệ!");
        return;
    }
    // Hiệu ứng nút bấm (để người dùng biết đang xử lý)
    const btnSave = document.querySelector('.btn-save');
    const originalText = btnSave.innerHTML;
    btnSave.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Đang lưu...';
    btnSave.disabled = true;

    // Gửi về Server
    fetch('/api/save_params', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            p_max: pMaxVal, 
            area: areaVal,
            
            // Dữ liệu mới
            p_pump: pPumpVal,
            monthly_kwh: monthlyKwhVal,
            alpha_p: alphaVal
        })
    })
    .then(response => response.json())
    .then(data => {
        if(data.status === 'success') {
            alert('✅ Đã lưu cấu hình thành công! Hệ thống Health Engine đã cập nhật.');
        } else {
            alert('❌ Lỗi từ Server: ' + data.message);
        }
    })
    .catch(err => {
        console.error("Lỗi lưu thông số:", err);
        alert('❌ Lỗi kết nối Server! Vui lòng kiểm tra server python.');
    })
    .finally(() => {
        // Khôi phục nút bấm dù thành công hay thất bại
        btnSave.innerHTML = originalText;
        btnSave.disabled = false;
    });
}