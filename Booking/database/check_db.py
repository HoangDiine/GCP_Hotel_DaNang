# check_db.py
import psycopg2
import os
import sys

# Force UTF-8 encoding for stdout on Windows
sys.stdout.reconfigure(encoding='utf-8')

db_host = os.environ.get("DB_HOST", "136.110.50.188")
db_port = os.environ.get("DB_PORT", "5432")
db_name = os.environ.get("DB_NAME", "postgres")
db_user = os.environ.get("DB_USER", "postgres")
db_password = os.environ.get("DB_PASSWORD", "Capstone2_2026")

try:
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )
    cursor = conn.cursor()
    
    tables = ["hotels", "hotel_locations", "hotel_facilities", "hotel_nearby_places", "hotel_reviews", "room_types", "room_prices"]
    print("Thống kê số lượng dòng trong các bảng:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]
        print(f"- Bảng {table}: {count} dòng")
        
    cursor.close()
    conn.close()
except Exception as e:
    print("Lỗi kết nối:", e)
