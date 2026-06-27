import os
import sys
import sqlite3
import time
import socket
from datetime import datetime

# Thiết lập timeout cho các kết nối mạng (tránh bị treo vĩnh viễn)
socket.setdefaulttimeout(60)

from src import scraper
from src import parser
from src import pipeline
from src import export_to_csv
from src import db_setup

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "hotel_warehouse.db"
HOTEL_DIR = "raw_html/hotels"

def run_detail_crawler():
    print("="*60)
    print("KHỞI CHẠY TIẾN TRÌNH CÀO CHI TIẾT KHÁCH SẠN (XUNG QUANH & CHÍNH SÁCH)")
    print("="*60)
    
    # 1. Chạy di trú DB trước tiên
    db_setup.init_db()
    
    # 2. Truy vấn danh sách khách sạn cần bổ sung chi tiết
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Lấy các hotel_id chưa có thông tin whats_nearby
    cursor.execute("""
        SELECT h.hotel_id, h.hotel_name 
        FROM Dim_Hotel h
        LEFT JOIN Dim_Location l ON h.hotel_id = l.hotel_id
        WHERE l.whats_nearby IS NULL OR l.whats_nearby = '' OR h.hotel_policies IS NULL OR h.hotel_policies = ''
    """)
    hotels_to_crawl = cursor.fetchall()
    conn.close()
    
    total_to_crawl = len(hotels_to_crawl)
    print(f"Tổng cộng có {total_to_crawl} khách sạn cần bổ sung thông tin chi tiết.")
    print("="*60)
    
    if total_to_crawl == 0:
        print("Tất cả khách sạn đã có đầy đủ thông tin chi tiết. Quy trình kết thúc sớm!")
        return

    processed = 0
    success = 0
    
    for hotel_id, hotel_name in hotels_to_crawl:
        processed += 1
        print(f"\n[{processed}/{total_to_crawl}] Đang xử lý: {hotel_name} ({hotel_id})")
        
        # Tạo URL chi tiết sạch
        url = f"https://www.booking.com/hotel/vn/{hotel_id}.vi.html"
        
        # Download raw HTML (đã được cấu hình scroll tự động trong scraper.py)
        # Để đảm bảo lấy lại dữ liệu đầy đủ nếu trước đó file cache bị thiếu (không được scroll),
        # ta kiểm tra nếu file cache đã có nhưng trong DB trống, ta sẽ xóa file cache cũ và tải lại.
        file_path = os.path.join(HOTEL_DIR, f"{hotel_id}.html")
        if os.path.exists(file_path):
            # Xóa file cache cũ không có scroll để tải lại bản đầy đủ
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Không thể xóa file cache cũ: {e}")
                
        download_ok = scraper.download_hotel_raw_html(url)
        if not download_ok:
            print(f"Không thể tải trang chi tiết cho {hotel_id}. Bỏ qua.")
            continue
            
        # Đọc HTML và bóc tách
        if not os.path.exists(file_path):
            print(f"Lỗi: Không thấy file HTML offline {file_path}")
            continue
            
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        try:
            extracted_data = parser.parse_hotel_details(html_content, hotel_id)
            # Ghi đè tên từ danh sách gốc nếu parser không lấy được
            if not extracted_data["dim_hotel"]["hotel_name"] or extracted_data["dim_hotel"]["hotel_name"] == "Không xác định":
                extracted_data["dim_hotel"]["hotel_name"] = hotel_name
                
            # Lưu trữ dữ liệu
            pipeline.insert_hotel_data(extracted_data)
            success += 1
        except Exception as e:
            print(f"Lỗi khi bóc tách / lưu trữ cho {hotel_id}: {e}")
            
        # Thỉnh thoảng xuất CSV để đảm bảo dữ liệu được cập nhật liên tục (mỗi 10 khách sạn)
        if success % 10 == 0:
            print(f"\nTự động cập nhật file CSV (Đã cào thành công {success} khách sạn)...")
            try:
                export_to_csv.export_tables_to_csv()
            except Exception as e:
                print(f"Lỗi xuất CSV: {e}")
                
        # Nghỉ ngắn giữa các khách sạn
        time.sleep(2)

    print("\n" + "="*60)
    print("TIẾN TRÌNH CÀO CHI TIẾT HOÀN TẤT!")
    print(f"- Đã xử lý: {processed}/{total_to_crawl}")
    print(f"- Thành công cập nhật DB: {success}")
    print("="*60)
    
    # Xuất CSV lần cuối
    print("\nXuất dữ liệu hoàn chỉnh ra file CSV...")
    try:
        export_to_csv.export_tables_to_csv()
    except Exception as e:
        print(f"Lỗi xuất CSV cuối cùng: {e}")

if __name__ == "__main__":
    run_detail_crawler()
