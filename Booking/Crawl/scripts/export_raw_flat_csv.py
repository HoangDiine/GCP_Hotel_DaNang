import sqlite3
import csv
import os
import sys

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Dynamic path resolution to make it runnable from any directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

DB_PATH = os.path.join(PROJECT_ROOT, "hotel_warehouse.db")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "csv_exports")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "raw_flat_data.csv")

def export_flat_csv():
    if not os.path.exists(DB_PATH):
        print(f"Không tìm thấy file database tại {DB_PATH}")
        return

    # Tạo thư mục đầu ra nếu chưa có
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("="*60)
    print("XUẤT DỮ LIỆU TỔNG HỢP (FLAT RAW CSV) TỪ DATABASE")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Câu lệnh SQL gộp toàn bộ các bảng Dim và Fact lại với nhau
    query = """
        SELECT 
            -- Dim_Hotel
            h.hotel_id, 
            h.hotel_name, 
            h.property_type,
            h.stars_rating, 
            h.review_count, 
            h.popular_facilities, 
            h.description, 
            h.hotel_policies,
            -- Dim_Location
            l.address, 
            l.whats_nearby,
            l.top_attractions, 
            l.natural_beauty, 
            l.nearest_airports, 
            l.restaurants_cafes, 
            l.beaches_in_area, 
            l.public_transport, 
            -- Dim_Review
            r.average_score,
            r.staff_score, 
            r.facilities_score, 
            r.cleanliness_score, 
            r.comfort_score, 
            r.value_for_money_score, 
            r.location_score, 
            r.free_wifi_score, 
            -- Dim_RoomType
            rt.room_type_name, 
            rt.bed_types, 
            rt.max_guests,
            -- Fact_Booking
            fb.original_price, 
            fb.current_price, 
            fb.discount, 
            fb.taxes_included, 
            fb.extracted_at,
            fb.checkin_date,
            fb.checkout_date
        FROM Fact_Booking fb
        LEFT JOIN Dim_Hotel h ON fb.hotel_id = h.hotel_id
        LEFT JOIN Dim_Location l ON fb.hotel_id = l.hotel_id
        LEFT JOIN Dim_Review r ON fb.hotel_id = r.hotel_id
        LEFT JOIN Dim_RoomType rt ON fb.room_type_id = rt.room_type_id
    """

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Lấy tên các cột kết quả
        column_names = [description[0] for description in cursor.description]
        
        # Xuất ra file CSV với utf-8-sig
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(column_names)
            writer.writerows(rows)
            
        print(f"Đã xuất thành công file dẹt (flat/raw) tại: {OUTPUT_FILE}")
        print(f"Tổng số bản ghi: {len(rows)} dòng.")
        
    except Exception as e:
        print(f"Lỗi khi thực hiện gộp bảng: {e}")
    finally:
        conn.close()
        
    print("="*60)

if __name__ == "__main__":
    export_flat_csv()
