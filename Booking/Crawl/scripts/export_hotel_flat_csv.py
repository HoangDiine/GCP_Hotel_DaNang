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
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "raw_hotels_flat.csv")

def export_hotels_flat():
    if not os.path.exists(DB_PATH):
        print(f"Không tìm thấy file database tại {DB_PATH}")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("="*60)
    print("XUẤT DỮ LIỆU KHÁCH SẠN DẸT (MỖI DÒNG LÀ 1 KHÁCH SẠN)")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Lấy toàn bộ danh sách khách sạn kèm location và review (1 dòng/khách sạn)
    hotels_query = """
        SELECT 
            h.hotel_id, 
            h.hotel_name, 
            h.property_type,
            h.stars_rating, 
            h.review_count, 
            h.popular_facilities, 
            h.description, 
            h.hotel_policies,
            l.address, 
            l.whats_nearby,
            l.top_attractions, 
            l.natural_beauty, 
            l.nearest_airports, 
            l.restaurants_cafes, 
            l.beaches_in_area, 
            l.public_transport, 
            r.average_score,
            r.staff_score, 
            r.facilities_score, 
            r.cleanliness_score, 
            r.comfort_score, 
            r.value_for_money_score, 
            r.location_score, 
            r.free_wifi_score
        FROM Dim_Hotel h
        LEFT JOIN Dim_Location l ON h.hotel_id = l.hotel_id
        LEFT JOIN Dim_Review r ON h.hotel_id = r.hotel_id
    """

    cursor.execute(hotels_query)
    hotels = cursor.fetchall()
    hotel_cols = [desc[0] for desc in cursor.description]

    # 2. Với mỗi khách sạn, lấy danh sách phòng và giá tương ứng để gộp lại
    flat_data = []
    
    for hotel in hotels:
        hotel_dict = dict(zip(hotel_cols, hotel))
        hotel_id = hotel_dict["hotel_id"]
        
        # Truy vấn thông tin phòng và giá của khách sạn này
        rooms_query = """
            SELECT 
                rt.room_type_name, 
                fb.current_price
            FROM Fact_Booking fb
            JOIN Dim_RoomType rt ON fb.room_type_id = rt.room_type_id
            WHERE fb.hotel_id = ?
        """
        cursor.execute(rooms_query, (hotel_id,))
        room_prices = cursor.fetchall()
        
        # Truy vấn thông tin ngày checkin/checkout của khách sạn này
        dates_query = """
            SELECT DISTINCT checkin_date, checkout_date
            FROM Fact_Booking
            WHERE hotel_id = ? AND checkin_date IS NOT NULL
        """
        cursor.execute(dates_query, (hotel_id,))
        booking_dates = cursor.fetchall()
        
        if booking_dates:
            checkin_str = ", ".join(sorted(list(set([d[0] for d in booking_dates if d[0]]))))
            checkout_str = ", ".join(sorted(list(set([d[1] for d in booking_dates if d[1]]))))
        else:
            checkin_str = ""
            checkout_str = ""
        
        if room_prices:
            # Tính giá thấp nhất, cao nhất
            prices = [rp[1] for rp in room_prices if rp[1] > 0]
            min_price = min(prices) if prices else 0.0
            max_price = max(prices) if prices else 0.0
            
            # Gộp danh sách phòng thành 1 chuỗi văn bản duy nhất
            # Ví dụ: "Phòng Standard (900k); Phòng Deluxe (1.2M)"
            room_list_str = "; ".join([f"{rp[0]} ({int(rp[1]):,} VND)" for rp in room_prices])
        else:
            min_price = 0.0
            max_price = 0.0
            room_list_str = ""

        # Bổ sung các cột tổng hợp vào dict của khách sạn
        hotel_dict["ngay_checkin"] = checkin_str
        hotel_dict["ngay_checkout"] = checkout_str
        hotel_dict["gia_thap_nhat"] = min_price
        hotel_dict["gia_cao_nhat"] = max_price
        hotel_dict["danh_sach_phong_va_gia"] = room_list_str
        
        flat_data.append(hotel_dict)

    # 3. Định nghĩa tiêu đề cột mới cho file CSV
    new_column_names = hotel_cols + ["ngay_checkin", "ngay_checkout", "gia_thap_nhat", "gia_cao_nhat", "danh_sach_phong_va_gia"]
    
    # 4. Ghi ra file CSV dẹt dạng 1 dòng/khách sạn
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8-sig') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(new_column_names)
        
        for item in flat_data:
            row_data = [item[col] for col in new_column_names]
            writer.writerow(row_data)

    print(f"Đã xuất thành công file dẹt (1 khách sạn/dòng) tại: {OUTPUT_FILE}")
    print(f"Tổng số khách sạn: {len(flat_data)} dòng.")
    print("="*60)

    conn.close()

if __name__ == "__main__":
    export_hotels_flat()
