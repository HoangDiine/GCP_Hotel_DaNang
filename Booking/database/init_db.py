# init_db.py
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

def init_db():
    print(f"Kết nối tới {db_host}:{db_port}/{db_name} để khởi tạo schema...")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )
    cursor = conn.cursor()
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    
    print("Đang thực thi các câu lệnh SQL trong schema.sql...")
    cursor.execute(sql)
    conn.commit()
    cursor.close()
    conn.close()
    print("Khởi tạo schema cơ sở dữ liệu thành công!")

if __name__ == "__main__":
    init_db()
