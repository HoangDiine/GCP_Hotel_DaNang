import os
import sys
import glob
import json
from datetime import datetime

# Dynamic path resolution to make it runnable from any directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

from src import parser

# Đảm bảo hiển thị tốt tiếng Việt trên terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HOTEL_DIR = os.path.join(PROJECT_ROOT, "raw_html", "hotels")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "csv_exports")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "raw_hotels_data.json")

def compile_all_raw_data():
    print("=" * 60)
    print("BẮT ĐẦU TỔNG HỢP DỮ LIỆU THÔ CỦA TẤT CẢ KHÁCH SẠN")
    print("=" * 60)

    # 1. Lấy danh sách toàn bộ các file HTML của khách sạn
    html_files = glob.glob(os.path.join(HOTEL_DIR, "*.html"))
    if not html_files:
        print(f"Không tìm thấy file HTML nào trong thư mục {HOTEL_DIR}")
        return

    print(f"Tìm thấy {len(html_files)} file HTML độc nhất để phân tích.")

    # Tạo thư mục đầu ra nếu chưa có
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    compiled_data = []
    success_count = 0

    # 2. Phân tích từng file và thu thập dữ liệu
    for idx, file_path in enumerate(html_files):
        hotel_id = os.path.basename(file_path).replace(".html", "")
        
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        try:
            # Gọi hàm parser để bóc tách thông tin
            data = parser.parse_hotel_details(html_content, hotel_id)
            
            # Cấu trúc hóa bản ghi thô đầy đủ
            raw_record = {
                "hotel_id": hotel_id,
                "hotel_name": data["dim_hotel"]["hotel_name"],
                "canonical_url": data["canonical_url"],
                "stars_rating": data["dim_hotel"]["stars_rating"],
                "stars_rating_value": data["stars_rating_value"],
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "review_score": data["dim_review"]["average_score"],
                "review_count": data["dim_hotel"]["review_count"],
                "review_score_word": data["review_score_word"],
                "popular_facilities": data["dim_hotel"]["popular_facilities"],
                "description": data["dim_hotel"]["description"],
                "hotel_policies": data["dim_hotel"]["hotel_policies"],
                "hotel_images": data["hotel_images"],
                "address": data["dim_location"]["address"],
                "top_attractions": data["dim_location"]["top_attractions"],
                "natural_beauty": data["dim_location"]["natural_beauty"],
                "nearest_airports": data["dim_location"]["nearest_airports"],
                "restaurants_cafes": data["dim_location"]["restaurants_cafes"],
                "beaches_in_area": data["dim_location"]["beaches_in_area"],
                "public_transport": data["dim_location"]["public_transport"],
                "whats_nearby": data["dim_location"]["whats_nearby"],
                "subscores": {
                    "staff": data["dim_review"]["staff_score"],
                    "facilities": data["dim_review"]["facilities_score"],
                    "cleanliness": data["dim_review"]["cleanliness_score"],
                    "comfort": data["dim_review"]["comfort_score"],
                    "value_for_money": data["dim_review"]["value_for_money_score"],
                    "location": data["dim_review"]["location_score"],
                    "free_wifi": data["dim_review"]["free_wifi_score"]
                },
                "room_types": data["dim_room_types"],
                "bookings": data["fact_bookings"],
                "compiled_at": datetime.now().isoformat()
            }
            
            compiled_data.append(raw_record)
            success_count += 1
            
            # Print tiến độ định kỳ
            if (idx + 1) % 50 == 0 or (idx + 1) == len(html_files):
                print(f"Đang tiến hành... Đã xử lý thành công: {idx + 1}/{len(html_files)}")
                
        except Exception as e:
            print(f"Lỗi khi bóc tách dữ liệu cho {hotel_id} ({file_path}): {e}")

    # 3. Ghi kết quả tổng hợp ra file JSON thô
    print(f"\nĐang ghi {len(compiled_data)} bản ghi vào tệp JSON thô...")
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as out_file:
            json.dump(compiled_data, out_file, indent=2, ensure_ascii=False)
        print(f"-> Ghi thành công tệp dữ liệu thô tại: {OUTPUT_FILE}")
    except Exception as e:
        print(f"Lỗi khi ghi tệp kết quả JSON: {e}")

    print("\n" + "=" * 60)
    print("TIẾN TRÌNH TỔNG HỢP HOÀN TẤT!")
    print(f"- Thành công: {success_count}/{len(html_files)} khách sạn")
    print(f"- Kết quả được lưu tại: {OUTPUT_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    compile_all_raw_data()
