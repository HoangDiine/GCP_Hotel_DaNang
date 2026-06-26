# run_etl.py
import subprocess
import sys

print("=== BẮT ĐẦU CHẠY ETL HỆ THỐNG ===")
print("1. Đang chạy tiền xử lý dữ liệu (preprocess.py)...")
res = subprocess.run([sys.executable, "preprocess.py"], capture_output=True, text=True)
print(res.stdout)
if res.returncode != 0:
    print("Lỗi chạy tiền xử lý:", res.stderr)
    sys.exit(res.returncode)

print("2. Đang nạp dữ liệu sạch vào database (load_to_cloud_sql.py)...")
res_db = subprocess.run([sys.executable, "load_to_cloud_sql.py"], capture_output=True, text=True)
print(res_db.stdout)
if res_db.returncode != 0:
    print("Lỗi nạp dữ liệu vào database:", res_db.stderr)
    sys.exit(res_db.returncode)

print("=== QUÁ TRÌNH ETL HOÀN TẤT THÀNH CÔNG ===")
