import os
import sys
import sqlite3
import glob

# Dynamic path resolution to make it runnable from any directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

from src import db_setup
from src import parser
from src import pipeline
from src import export_to_csv

DB_PATH = os.path.join(PROJECT_ROOT, "hotel_warehouse.db")
HOTEL_DIR = os.path.join(PROJECT_ROOT, "raw_html", "hotels")

# Đảm bảo hiển thị tốt tiếng Việt trên terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def reparse_all_cached_hotels():
    print("=" * 60)
    print("BẮT ĐẦU RE-PARSE TOÀN BỘ CÁC FILE HTML OFFLINE")
    print("=" * 60)

    # 1. Reset Database bằng cách xóa file DB cũ nếu tồn tại
    if os.path.exists(DB_PATH):
        print(f"Xóa database cũ tại: {DB_PATH}")
        try:
            # Đóng tất cả kết nối trước khi xóa (nếu có)
            os.remove(DB_PATH)
            print("Đã xóa database cũ thành công.")
        except Exception as e:
            print(f"Lỗi khi xóa database cũ: {e}")
            print("Đang tiến hành làm trống các bảng thay thế...")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF;")
            for table in ["Fact_Booking", "Dim_RoomType", "Dim_Review", "Dim_Location", "Dim_Hotel"]:
                cursor.execute(f"DROP TABLE IF EXISTS {table};")
            conn.commit()
            conn.close()

    # 2. Khởi tạo lại cấu trúc database sạch
    db_setup.init_db()

    # 3. Lấy danh sách toàn bộ các file html của khách sạn
    html_files = glob.glob(os.path.join(HOTEL_DIR, "*.html"))
    if not html_files:
        print(f"Không tìm thấy file HTML nào trong thư mục {HOTEL_DIR}")
        return

    print(f"\nTìm thấy {len(html_files)} file HTML offline để phân tích.")

    # 4. Phân tích từng file và chèn vào Database
    success_count = 0
    for idx, file_path in enumerate(html_files):
        # Lấy hotel_id từ tên file (ví dụ: paracel-danang.html -> paracel-danang)
        hotel_id = os.path.basename(file_path).replace(".html", "")
        print(f"\n[{idx + 1}/{len(html_files)}] Đang phân tích file: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        try:
            # Gọi hàm parse
            extracted_data = parser.parse_hotel_details(html_content, hotel_id)
            
            # Kiểm tra xem có trích xuất được vị trí (top_attractions) không
            loc_data = extracted_data.get("dim_location", {})
            print(f"   -> Địa chỉ: {loc_data.get('address')[:50]}...")
            print(f"   -> Vị trí trích xuất được: {loc_data.get('top_attractions')[:100]}...")

            # Ghi vào DB
            pipeline.insert_hotel_data(extracted_data)
            success_count += 1
        except Exception as e:
            print(f"Lỗi khi phân tích {hotel_id}: {e}")

    print("\n" + "=" * 60)
    print(f"QUÁ TRÌNH PHÂN TÍCH LẠI HOÀN TẤT!")
    print(f"- Thành công xử lý: {success_count}/{len(html_files)} khách sạn")
    print("=" * 60)

    # 5. Xuất lại file CSV mới nhất
    print("\nĐang xuất dữ liệu ra các file CSV mới...")
    export_to_csv.export_tables_to_csv()

if __name__ == "__main__":
    reparse_all_cached_hotels()
