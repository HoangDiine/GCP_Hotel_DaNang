import os
import sys
import json
import csv
from datetime import datetime

# Ensure Vietnamese Unicode characters are printed properly on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
JSON_FILE = os.path.join(PROJECT_ROOT, "csv_exports", "raw_hotels_data.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "csv_exports", "raw_hotels_full.csv")

def export_full_csv():
    if not os.path.exists(JSON_FILE):
        print(f"Không tìm thấy file dữ liệu JSON tại: {JSON_FILE}")
        return

    print("="*60)
    print("XUẤT DỮ LIỆU KHÁCH SẠN ĐẦY ĐỦ CHI TIẾT (FULL FLAT CSV)")
    print("="*60)
    
    print(f"Đang đọc dữ liệu thô từ: {JSON_FILE} ...")
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        hotels_data = json.load(f)
        
    print(f"Tìm thấy {len(hotels_data)} khách sạn.")
    
    flat_data = []
    
    for item in hotels_data:
        # Extract subscores
        subscores = item.get("subscores", {})
        
        # Process room prices and lists
        bookings = item.get("bookings", [])
        room_types = item.get("room_types", [])
        
        # Aggregate checkin/checkout dates
        checkin_dates = sorted(list(set([b.get("checkin_date") for b in bookings if b.get("checkin_date")])))
        checkout_dates = sorted(list(set([b.get("checkout_date") for b in bookings if b.get("checkout_date")])))
        checkin_str = ", ".join(checkin_dates)
        checkout_str = ", ".join(checkout_dates)
        
        # Calculate price ranges and lists
        prices = [b.get("current_price") for b in bookings if b.get("current_price") is not None and b.get("current_price") > 0]
        min_price = min(prices) if prices else 0.0
        max_price = max(prices) if prices else 0.0
        
        # Create a dict mapping room_type_id to room_type_name
        room_names = {r.get("room_type_id"): r.get("room_type_name") for r in room_types if r.get("room_type_id")}
        
        room_price_list = []
        for b in bookings:
            r_id = b.get("room_type_id")
            r_name = room_names.get(r_id, r_id or "Phòng không xác định")
            price_val = b.get("current_price")
            if price_val:
                room_price_list.append(f"{r_name} ({int(price_val):,} VND)")
            else:
                room_price_list.append(r_name)
                
        room_list_str = "; ".join(room_price_list)
        
        # Handle list of image URLs
        images_str = "; ".join(item.get("hotel_images", []))
        
        # Compile all fields
        record = {
            "hotel_id": item.get("hotel_id"),
            "hotel_name": item.get("hotel_name"),
            "canonical_url": item.get("canonical_url"),
            "stars_rating": item.get("stars_rating"),
            "stars_rating_value": item.get("stars_rating_value"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "review_score": item.get("review_score"),
            "review_count": item.get("review_count"),
            "review_score_word": item.get("review_score_word"),
            "popular_facilities": item.get("popular_facilities"),
            "description": item.get("description"),
            "hotel_policies": item.get("hotel_policies"),
            "hotel_images": images_str,
            "address": item.get("address"),
            "whats_nearby": item.get("whats_nearby"),
            "top_attractions": item.get("top_attractions"),
            "natural_beauty": item.get("natural_beauty"),
            "nearest_airports": item.get("nearest_airports"),
            "restaurants_cafes": item.get("restaurants_cafes"),
            "beaches_in_area": item.get("beaches_in_area"),
            "public_transport": item.get("public_transport"),
            # Reviews subscores
            "staff_score": subscores.get("staff", 0.0),
            "facilities_score": subscores.get("facilities", 0.0),
            "cleanliness_score": subscores.get("cleanliness", 0.0),
            "comfort_score": subscores.get("comfort", 0.0),
            "value_for_money_score": subscores.get("value_for_money", 0.0),
            "location_score": subscores.get("location", 0.0),
            "free_wifi_score": subscores.get("free_wifi", 0.0),
            # Bookings aggregations
            "ngay_checkin": checkin_str,
            "ngay_checkout": checkout_str,
            "gia_thap_nhat": min_price,
            "gia_cao_nhat": max_price,
            "danh_sach_phong_va_gia": room_list_str
        }
        flat_data.append(record)

    headers = [
        "hotel_id", "hotel_name", "canonical_url", "stars_rating", "stars_rating_value",
        "latitude", "longitude", "review_score", "review_count", "review_score_word",
        "gia_thap_nhat", "gia_cao_nhat", "address", "ngay_checkin", "ngay_checkout",
        "popular_facilities", "description", "hotel_policies", "whats_nearby", "top_attractions",
        "natural_beauty", "nearest_airports", "restaurants_cafes", "beaches_in_area", "public_transport",
        "staff_score", "facilities_score", "cleanliness_score", "comfort_score", "value_for_money_score",
        "location_score", "free_wifi_score", "hotel_images", "danh_sach_phong_va_gia"
    ]

    print(f"Đang ghi dữ liệu vào tệp CSV dẹt: {OUTPUT_FILE} ...")
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(flat_data)
        
    print(f"-> Xuất tệp CSV thành công tại: {OUTPUT_FILE} ({len(flat_data)} dòng)")
    print("="*60)

if __name__ == "__main__":
    export_full_csv()
