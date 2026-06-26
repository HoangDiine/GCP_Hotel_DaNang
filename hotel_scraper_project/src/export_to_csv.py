import sqlite3
import csv
import os
import sys

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamic path resolution to make it runnable from any directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(PROJECT_ROOT, "hotel_warehouse.db")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "csv_exports", "dim_fact")

def export_tables_to_csv():
    if not os.path.exists(DB_PATH):
        print(f"Không tìm thấy file database tại {DB_PATH}")
        return

    # Tạo thư mục đầu ra nếu chưa có
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Lấy danh sách các bảng trong database (trừ các bảng hệ thống sqlite)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        print("Không có bảng nào trong database để xuất.")
        conn.close()
        return

    print(f"Tìm thấy các bảng: {', '.join(tables)}")
    
    for table in tables:
        print(f"Đang xuất bảng '{table}'...")
        
        # Lấy dữ liệu
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        
        # Lấy tên cột (headers)
        column_names = [description[0] for description in cursor.description]
        
        output_file = os.path.join(OUTPUT_DIR, f"{table}.csv")
        
        # Sử dụng encoding utf-8-sig để Excel mở không bị lỗi font tiếng Việt
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csv_file:
            writer = csv.writer(csv_file)
            # Ghi tiêu đề cột
            writer.writerow(column_names)
            # Ghi dữ liệu dòng
            writer.writerows(rows)
            
        print(f"-> Đã xuất thành công: {output_file} ({len(rows)} dòng)")

    conn.close()
    print("\nHoàn thành xuất toàn bộ bảng ra file CSV!")

if __name__ == "__main__":
    export_tables_to_csv()
