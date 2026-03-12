document.addEventListener('DOMContentLoaded', loadHistory);

function loadHistory() {
    const tableBody = document.getElementById('history-table-body');
    if (!tableBody) return;

    // Hiện dòng đang tải...
    tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">⏳ Đang tải dữ liệu...</td></tr>';

    // Gọi API lấy dữ liệu thật từ Python
    fetch('/api/get_history')
        .then(response => response.json())
        .then(data => {
            tableBody.innerHTML = ''; // Xóa loading

            if (!data || data.length === 0) {
                tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px;">Chưa có dữ liệu lịch sử.</td></tr>';
                return;
            }

            data.forEach(row => {
                const tr = document.createElement('tr');

                // 1. Xử lý Trạng thái (BẬT/TẮT)
                let statusClass = 'status-off';
                let statusText = row.command;
                if (String(row.command) === '2' || row.command === 'BẬT') {
                    statusClass = 'status-on'; 
                    statusText = 'BẬT';
                } else if (String(row.command) === '0' || row.command === 'TẮT') {
                    statusClass = 'status-off';
                    statusText = 'TẮT';
                }

                // 2. Xử lý Nguồn lệnh (Để hiện Smart Eco)
                let sourceHTML = '';
                // [PHẦN QUAN TRỌNG]: Phân biệt các chế độ
                if (row.source === 'SMART_ECO') {
                    sourceHTML = '<span class="source-tag source-smart"><i class="fas fa-leaf"></i> Smart Eco (AI)</span>';
                } else if (row.source === 'AI_AUTO' || row.source === 'AUTO') {
                    sourceHTML = '<span class="source-tag source-auto"><i class="fas fa-robot"></i> Tự động (AI)</span>';
                } else {
                    sourceHTML = '<span class="source-tag source-manual"><i class="fas fa-hand-pointer"></i> Thủ công (Web)</span>';
                }

                // 3. Render HTML khớp với giao diện cũ
                tr.innerHTML = `
                    <td>${row.timestamp}</td>
                    <td style="font-weight:bold; color: #fff;">${row.user_id}</td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td>${row.action_type}</td>
                    <td>${sourceHTML}</td>
                `;
                tableBody.appendChild(tr);
            });
        })
        .catch(err => {
            console.error(err);
            tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: red;">Lỗi kết nối Server!</td></tr>';
        });
}