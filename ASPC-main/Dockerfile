# Sử dụng môi trường Python gọn nhẹ
FROM python:3.11-slim

# Tạo thư mục làm việc ảo bên trong Docker
WORKDIR /app

# Copy file requirements vào trước để cài thư viện
COPY requirements.txt .

# Cài đặt thư viện
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn của dự án (hotspot_engine.py, thư mục templates, static...) vào Docker
COPY . .

# Mở cổng 5000 (cổng mặc định nếu dùng Flask)
EXPOSE 5000

# Lệnh khởi chạy ứng dụng
CMD ["python", "ASPC/app.py"]