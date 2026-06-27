import os
import sys
import sqlite3
from dotenv import load_dotenv
from src import scraper
from src import parser
from src import db_setup

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

DB_PATH = "hotel_warehouse.db"
HOTEL_DIR = "raw_html/hotels"

def insert_hotel_data(data: dict):
    """
    Chèn hoặc cập nhật dữ liệu khách sạn vào SQLite theo thứ tự ràng buộc khóa ngoại:
    Dim_Hotel -> Dim_Location, Dim_Review, Dim_RoomType -> Fact_Booking
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Kích hoạt Foreign Keys trong SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    try:
        # 1. Chèn vào Dim_Hotel
        hotel = data["dim_hotel"]
        cursor.execute("""
            INSERT OR REPLACE INTO Dim_Hotel (
                hotel_id, hotel_name, description, stars_rating, review_count, popular_facilities, property_type, hotel_policies
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hotel["hotel_id"], hotel["hotel_name"], hotel["description"], 
            hotel["stars_rating"], hotel["review_count"], hotel["popular_facilities"], 
            hotel["property_type"], hotel.get("hotel_policies", "")
        ))

        # 2. Chèn vào Dim_Location
        loc = data["dim_location"]
        cursor.execute("""
            INSERT OR REPLACE INTO Dim_Location (
                hotel_id, address, top_attractions, natural_beauty, nearest_airports, 
                restaurants_cafes, beaches_in_area, public_transport, whats_nearby
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            loc["hotel_id"], loc["address"], loc["top_attractions"], loc["natural_beauty"],
            loc["nearest_airports"], loc["restaurants_cafes"], loc["beaches_in_area"], 
            loc["public_transport"], loc.get("whats_nearby", "")
        ))

        # 3. Chèn vào Dim_Review
        rev = data["dim_review"]
        cursor.execute("DELETE FROM Dim_Review WHERE hotel_id = ?", (rev["hotel_id"],))
        cursor.execute("""
            INSERT INTO Dim_Review (
                hotel_id, staff_score, facilities_score, cleanliness_score, comfort_score,
                value_for_money_score, location_score, free_wifi_score, average_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rev["hotel_id"], rev["staff_score"], rev["facilities_score"], rev["cleanliness_score"],
            rev["comfort_score"], rev["value_for_money_score"], rev["location_score"], rev["free_wifi_score"],
            rev["average_score"]
        ))

        # 4. Chèn vào Dim_RoomType
        for rt in data["dim_room_types"]:
            cursor.execute("""
                INSERT OR REPLACE INTO Dim_RoomType (
                    room_type_id, hotel_id, room_type_name, bed_types, max_guests
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                rt["room_type_id"], rt["hotel_id"], rt["room_type_name"], rt["bed_types"], rt["max_guests"]
            ))

        # 5. Chèn vào Fact_Booking
        for booking in data["fact_bookings"]:
            cursor.execute("""
                INSERT INTO Fact_Booking (
                    hotel_id, room_type_id, original_price, current_price, discount, taxes_included, extracted_at, checkin_date, checkout_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                booking["hotel_id"], booking["room_type_id"], booking["original_price"],
                booking["current_price"], booking["discount"], booking["taxes_included"],
                booking["extracted_at"], booking.get("checkin_date"), booking.get("checkout_date")
            ))

        conn.commit()
        print(f"-> Đã lưu trữ thành công dữ liệu khách sạn: {hotel['hotel_name']} ({hotel['hotel_id']})")
    except Exception as e:
        conn.rollback()
        print(f"Lỗi khi lưu trữ dữ liệu cho khách sạn {data.get('dim_hotel', {}).get('hotel_id')}: {e}")
    finally:
        conn.close()

def run_pipeline(num_pages: int = 1):
    """
    Hàm điều phối toàn bộ quy trình cào, parse và lưu trữ dữ liệu
    """
    print("="*60)
    print("KHỞI CHẠY PIPELINE CÀO DỮ LIỆU KHÁCH SẠN ĐÀ NẴNG (BOOKING.COM)")
    print("="*60)
    
    # Bước 1: Khởi tạo cơ sở dữ liệu
    db_setup.init_db()
    
    # Bước 2: Thu thập các URL khách sạn từ trang tìm kiếm
    all_hotel_urls = set()
    for page in range(num_pages):
        html_content = scraper.fetch_and_save_search_page(page)
        if html_content:
            urls = parser.extract_hotel_urls_from_html(html_content)
            print(f"Trang {page + 1}: Tìm thấy {len(urls)} đường link khách sạn.")
            all_hotel_urls.update(urls)
        else:
            print(f"Bỏ qua trang {page + 1} do không tải được HTML.")

    all_hotel_urls = list(all_hotel_urls)
    print(f"\nTỔNG CỘNG: Tìm thấy {len(all_hotel_urls)} đường dẫn khách sạn duy nhất để xử lý.")
    print("="*60)

    # Bước 3: Tải trang chi tiết và phân tích dữ liệu offline
    processed_count = 0
    success_count = 0
    
    for url in all_hotel_urls[:5]:  # Giới hạn 5 khách sạn để kiểm thử tránh hết credit
        processed_count += 1
        try:
            hotel_id = url.split("/hotel/vn/")[-1].replace(".vi.html", "").split("?")[0]
        except Exception:
            continue
            
        print(f"\n[{processed_count}/{len(all_hotel_urls)}] Đang xử lý khách sạn: {hotel_id}")
        
        # Tải HTML chi tiết (kiểm tra offline trước)
        download_ok = scraper.download_hotel_raw_html(url)
        if not download_ok:
            print(f"Không thể tải trang chi tiết cho {hotel_id}. Bỏ qua.")
            continue
            
        # Đọc HTML từ file offline để xử lý
        file_path = os.path.join(HOTEL_DIR, f"{hotel_id}.html")
        if not os.path.exists(file_path):
            print(f"Lỗi: Không tìm thấy file offline {file_path}")
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            html_detail = f.read()
            
        # Parse dữ liệu offline bằng BeautifulSoup
        try:
            extracted_data = parser.parse_hotel_details(html_detail, hotel_id)
            # Lưu vào Database
            insert_hotel_data(extracted_data)
            success_count += 1
        except Exception as e:
            print(f"Lỗi khi phân tích HTML cho {hotel_id}: {e}")

    print("\n" + "="*60)
    print(f"QUY TRÌNH HOÀN TẤT!")
    print(f"- Tổng số khách sạn xử lý: {processed_count}")
    print(f"- Thành công ghi vào database: {success_count}")
    print("="*60)

    # Tự động xuất CSV mới sau khi cào xong
    print("\nĐang xuất dữ liệu mới ra các file CSV...")
    try:
        from src import export_to_csv
        export_to_csv.export_tables_to_csv()
    except Exception as e:
        print(f"Lỗi khi tự động xuất CSV: {e}")

def run_search_pipeline(checkin: str = "2026-07-26", checkout: str = "2026-07-27"):
    """
    Quy trình cào nhanh: tải trực tiếp trang tìm kiếm có ngày, parse các card và ghi vào database.
    Sử dụng các bộ lọc phân hạng sao (nflt=class=X) để đảm bảo không trùng lặp và đạt tối thiểu 500 khách sạn độc nhất.
    """
    print("="*60)
    print("KHỞI CHẠY PIPELINE CÀO NHANH THEO BỘ LỌC SAO (BOOKING.COM)")
    print(f"- Ngày: {checkin} -> {checkout}")
    print("="*60)
    
    # Bước 1: Khởi tạo cơ sở dữ liệu
    db_setup.init_db()
    
    total_hotels_saved = 0
    
    # Định nghĩa các bộ lọc theo sao (5 sao, 4 sao, 3 sao, 2 sao, 1 sao, không xếp hạng)
    # nflt = class%3D5, class%3D4, class%3D3, class%3D2, class%3D1, class%3D0
    # Cấu hình số trang tối đa cho từng hạng sao (tránh cào quá nhiều nếu hết phòng/hết kết quả)
    filters = [
        ("class%3D5", 6),              # 5 sao: tối đa 6 trang (~150 khách sạn)
        ("class%3D4", 10),             # 4 sao: tối đa 10 trang (~250 khách sạn)
        ("class%3D3", 12),             # 3 sao: tối đa 12 trang (~300 khách sạn)
        ("class%3D2", 10),             # 2 sao: tối đa 10 trang (~250 khách sạn)
        ("class%3D1", 6),              # 1 sao: tối đa 6 trang (~150 khách sạn)
        ("class%3D0", 12)              # Không xếp hạng (Homestay, Apartment, Hostel): tối đa 12 trang
    ]
    
    for nflt_val, pages in filters:
        label = nflt_val.replace("class%3D", "") + "-sao"
        print(f"\n===== CÀO VỚI BỘ LỌC SAO: {label.upper()} ({pages} TRANG) =====")
        
        for page in range(pages):
            print(f"\n--- Đang xử lý bộ lọc {label} - Trang {page + 1}/{pages} ---")
            html_content = scraper.fetch_and_save_search_page(page, checkin=checkin, checkout=checkout, nflt=nflt_val)
            if html_content:
                try:
                    hotels_data = parser.parse_search_results_page(html_content, checkin=checkin, checkout=checkout)
                    print(f"Tìm thấy {len(hotels_data)} khách sạn trên trang này.")
                    
                    if len(hotels_data) == 0:
                        print(f"-> Không có khách sạn nào trên trang này. Dừng bộ lọc {label} sớm.")
                        break
                        
                    page_saved = 0
                    for hotel_data in hotels_data:
                        try:
                            insert_hotel_data(hotel_data)
                            page_saved += 1
                        except Exception as e:
                            print(f"Lỗi khi lưu khách sạn {hotel_data.get('dim_hotel', {}).get('hotel_id')}: {e}")
                    
                    total_hotels_saved += page_saved
                    print(f"-> Ghi thành công {page_saved}/{len(hotels_data)} khách sạn.")
                except Exception as e:
                    print(f"Lỗi khi bóc tách bộ lọc {label} Trang {page + 1}: {e}")
            else:
                print(f"Bỏ qua bộ lọc {label} trang {page + 1} do không tải được HTML.")

    print("\n" + "="*60)
    print(f"QUY TRÌNH CÀO NHANH HOÀN TẤT!")
    print(f"- Tổng số lượt khách sạn đã xử lý: {total_hotels_saved}")
    print("="*60)

    # Tự động xuất CSV mới sau khi cào xong
    print("\nĐang xuất dữ liệu mới ra các file CSV...")
    try:
        from src import export_to_csv
        export_to_csv.export_tables_to_csv()
    except Exception as e:
        print(f"Lỗi khi tự động xuất CSV: {e}")

if __name__ == "__main__":
    # Mặc định chạy cào nhanh để lấy ít nhất 500 khách sạn
    run_search_pipeline()
