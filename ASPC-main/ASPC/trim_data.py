import pandas as pd

# Đường dẫn đến file của bạn
file_path = 'data_usa.csv'

# Đọc dữ liệu
df = pd.read_csv(file_path)

# Tính toán số lượng hàng muốn giữ (50%)
half_count = len(df) // 2

# Lấy một nửa đầu tiên
df_half = df.iloc[:half_count]

# Ghi đè lại vào file cũ (hoặc lưu file mới để kiểm tra trước)
df_half.to_csv(file_path, index=False)

print(f"drop tu {len(df)} row xuong con {len(df_half)} row.")