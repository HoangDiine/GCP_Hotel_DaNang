# preprocess.py
import os
import re
import sys
import unicodedata
import pandas as pd
import numpy as np
from google.cloud import storage

# Force UTF-8 for stdout on Windows
sys.stdout.reconfigure(encoding='utf-8')

base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()

def download_from_gcs(bucket_name, source_blob_name, destination_file_path):
    """Tải file từ Google Cloud Storage bucket về thư mục cục bộ"""
    try:
        # Client tự động dùng quyền IAM của Service Account khi chạy trên Cloud Run Job
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)
        
        print(f"Đang tải gs://{bucket_name}/{source_blob_name} xuống {destination_file_path}...")
        blob.download_to_filename(destination_file_path)
        print("Tải file từ GCS thành công!")
        return True
    except Exception as e:
        print(f"Không thể tải file từ GCS: {e}")
        return False

# Cấu hình tải dữ liệu thô từ GCS
bucket_name = os.environ.get("GCS_BUCKET_NAME", "capstone-project-2-group-4-data")
source_blob_name = "raw_hotels_full.csv"
raw_path = os.path.join(base_dir, "raw_hotels_full.csv")

# Thử tải từ GCS
gcs_success = download_from_gcs(bucket_name, source_blob_name, raw_path)

if not gcs_success:
    print("Sử dụng cơ chế fallback: Tìm file dữ liệu thô cục bộ...")
    raw_path = os.path.join(os.path.dirname(base_dir), "data", "raw_hotels_full.csv")
    if not os.path.exists(raw_path):
        raw_path = os.path.join(base_dir, "raw_hotels_full.csv")
    if not os.path.exists(raw_path):
        raw_path = "raw_hotels_full.csv"

output_dir = os.path.join(base_dir, "cleaned_tables")
os.makedirs(output_dir, exist_ok=True)

print(f"Đang đọc file dữ liệu CSV thô từ đường dẫn: {raw_path}")
df_raw = pd.read_csv(raw_path)
print(f"Tổng số dòng đọc được từ raw_hotels_full.csv: {len(df_raw)}")

def normalize_text(text):
    if pd.isna(text) or text is None:
        return ""
    return unicodedata.normalize('NFC', str(text)).strip()

def clean_id(text):
    text = normalize_text(text).lower()
    replacements = {
        'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
        'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
        'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
        'đ': 'd',
        'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
        'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
        'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
        'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
        'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
        'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
        'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
        'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
        'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y'
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r'[^a-z0-9]', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')

# Parse stars rating
def parse_stars(stars_rating_value, stars_rating):
    if not pd.isna(stars_rating_value):
        try:
            return int(float(stars_rating_value))
        except ValueError:
            pass
            
    stars_str = normalize_text(stars_rating)
    if not stars_str:
        return 0
    match = re.search(r'(\d+)\s+trên\s+5\s+sao', stars_str)
    return int(match.group(1)) if match else 0

# Parse address
def parse_address(addr_raw):
    if not addr_raw or pd.isna(addr_raw):
        return "", "", "", ""
    addr_str = normalize_text(addr_raw)
    match = re.search(r'^(.*?Việt\s+Nam|.*?Việt\s+Nam)', addr_str, re.IGNORECASE)
    if match:
        clean_addr = match.group(1).strip()
    else:
        clean_addr = addr_str
    clean_addr = re.sub(r'\b\d{5,6}\b\s*,?\s*', '', clean_addr)
    clean_addr = re.sub(r'\s*,\s*', ', ', clean_addr)
    clean_addr = re.sub(r',\s*,', ',', clean_addr).strip(', ')
    
    parts = [p.strip() for p in clean_addr.split(',')]
    country = "Việt Nam"
    city = "Đà Nẵng"
    street_address = clean_addr
    
    if len(parts) >= 2:
        if parts[-1].lower() == "việt nam":
            country = parts[-1]
            city = parts[-2]
            street_address = ", ".join(parts[:-2])
        else:
            city = parts[-1]
            street_address = ", ".join(parts[:-1])
    return street_address, city, country, clean_addr

# Parse checkin/checkout policies
def extract_policy_times(policy_str):
    checkin_start, checkin_end = "14:00", "00:00"
    checkout_start, checkout_end = "00:00", "12:00"
    if not policy_str or pd.isna(policy_str):
        return checkin_start, checkin_end, checkout_start, checkout_end
    policy_str = normalize_text(policy_str)
    in_match = re.search(r'Nhận\s+phòng[^\n]*\nTừ\s*(\d{2}:\d{2})(?:\s*-\s*(\d{2}:\d{2}))?', policy_str, re.IGNORECASE)
    if in_match:
        checkin_start = in_match.group(1)
        if in_match.group(2):
            checkin_end = in_match.group(2)
    out_match = re.search(r'Trả\s+phòng[^\n]*\nTừ\s*(\d{2}:\d{2})(?:\s*-\s*(\d{2}:\d{2}))?', policy_str, re.IGNORECASE)
    if out_match:
        checkout_start = out_match.group(1)
        if out_match.group(2):
            checkout_end = out_match.group(2)
    return checkin_start, checkin_end, checkout_start, checkout_end

# Parse facilities
def parse_facilities(hotel_id, facilities_str):
    records = []
    if not facilities_str or pd.isna(facilities_str):
        return records
    facilities_str = normalize_text(facilities_str)
    items = [item.strip() for item in facilities_str.split(',') if item.strip()]
    seen = set()
    for item in items:
        item_cap = item.capitalize()
        if item_cap not in seen:
            seen.add(item_cap)
            records.append({
                "hotel_id": hotel_id,
                "facility_name": item_cap
            })
    return records

# Parse nearby places
def parse_nearby_places(hotel_id, text, place_type):
    records = []
    if not text or pd.isna(text) or str(text).strip() == "":
        return records
    parts = normalize_text(text).split(';')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.search(r'^(.*?)\s+([\d,.]+)\s*(km|m)\s*$', part, re.IGNORECASE)
        if match:
            place_name = match.group(1).strip()
            dist_val_str = match.group(2).replace(',', '.')
            dist_unit = match.group(3).lower()
            try:
                dist_val = float(dist_val_str)
                meters = int(dist_val * 1000) if dist_unit == 'km' else int(dist_val)
                records.append({
                    "hotel_id": hotel_id,
                    "place_name": place_name,
                    "place_type": place_type,
                    "distance_value": dist_val,
                    "distance_unit": dist_unit,
                    "distance_in_meters": meters
                })
            except ValueError:
                continue
    return records

# Process hotels, locations, facilities, nearby, reviews, room types, room prices
hotels_list = []
locations_list = []
facilities_list = []
nearby_list = []
reviews_list = []
rooms_list = []
bookings_list = []

print("Bắt đầu xử lý từng dòng dữ liệu từ CSV...")
for index, row in df_raw.iterrows():
    hid = str(row['hotel_id'])
    
    # 1. Hotels
    stars = parse_stars(row.get('stars_rating_value'), row.get('stars_rating'))
    checkin_start, checkin_end, checkout_start, checkout_end = extract_policy_times(row.get('hotel_policies'))
    
    hotels_list.append({
        'hotel_id': hid,
        'hotel_name': normalize_text(row.get('hotel_name')),
        'description': normalize_text(row.get('description')),
        'stars_rating': stars,
        'review_count': int(row['review_count']) if not pd.isna(row.get('review_count')) else 0,
        'popular_facilities': normalize_text(row.get('popular_facilities')),
        'property_type': 'Khách sạn',
        'checkin_time_start': checkin_start,
        'checkin_time_end': checkin_end,
        'checkout_time_start': checkout_start,
        'checkout_time_end': checkout_end
    })
    
    # 2. Locations
    street_addr, city, country, full_addr = parse_address(row.get('address'))
    lat = float(row['latitude']) if not pd.isna(row.get('latitude')) else None
    lon = float(row['longitude']) if not pd.isna(row.get('longitude')) else None
    locations_list.append({
        'hotel_id': hid,
        'street_address': street_addr,
        'city': city,
        'country': country,
        'full_address': full_addr,
        'latitude': lat,
        'longitude': lon
    })
    
    # 3. Facilities
    facilities_list.extend(parse_facilities(hid, row.get('popular_facilities')))
    
    # 4. Nearby places
    nearby_list.extend(parse_nearby_places(hid, row.get('top_attractions'), 'attraction'))
    nearby_list.extend(parse_nearby_places(hid, row.get('natural_beauty'), 'nature'))
    nearby_list.extend(parse_nearby_places(hid, row.get('nearest_airports'), 'airport'))
    nearby_list.extend(parse_nearby_places(hid, row.get('restaurants_cafes'), 'restaurant'))
    nearby_list.extend(parse_nearby_places(hid, row.get('beaches_in_area'), 'beach'))
    nearby_list.extend(parse_nearby_places(hid, row.get('public_transport'), 'transport'))
    nearby_list.extend(parse_nearby_places(hid, row.get('whats_nearby'), 'nearby'))
    
    # 5. Reviews
    reviews_list.append({
        'review_id': f"{hid}_rev",
        'hotel_id': hid,
        'staff_score': float(row['staff_score']) if not pd.isna(row.get('staff_score')) else 0.0,
        'facilities_score': float(row['facilities_score']) if not pd.isna(row.get('facilities_score')) else 0.0,
        'cleanliness_score': float(row['cleanliness_score']) if not pd.isna(row.get('cleanliness_score')) else 0.0,
        'comfort_score': float(row['comfort_score']) if not pd.isna(row.get('comfort_score')) else 0.0,
        'value_for_money_score': float(row['value_for_money_score']) if not pd.isna(row.get('value_for_money_score')) else 0.0,
        'location_score': float(row['location_score']) if not pd.isna(row.get('location_score')) else 0.0,
        'free_wifi_score': float(row['free_wifi_score']) if not pd.isna(row.get('free_wifi_score')) else 0.0,
        'average_score': float(row['review_score']) if not pd.isna(row.get('review_score')) else 0.0
    })
    
    # 6 & 7. Room Types and Room Prices
    checkin_date = str(row['ngay_checkin']) if not pd.isna(row.get('ngay_checkin')) else "2026-07-06"
    checkout_date = str(row['ngay_checkout']) if not pd.isna(row.get('ngay_checkout')) else "2026-07-07"
    
    rooms_str = row.get('danh_sach_phong_va_gia')
    if rooms_str and not pd.isna(rooms_str):
        room_items = str(rooms_str).split(';')
        for idx, item in enumerate(room_items, 1):
            item = item.strip()
            if not item:
                continue
            match = re.search(r"^(.*?)\s*\(\s*([\d,.]+)\s*VND\s*\)\s*$", item, re.IGNORECASE)
            if match:
                room_name = match.group(1).strip()
                price_str = match.group(2).replace(',', '')
                try:
                    price_val = float(price_str)
                except ValueError:
                    price_val = 0.0
                
                room_type_id = f"{hid}_{clean_id(room_name)}_{idx}"
                rooms_list.append({
                    'room_type_id': room_type_id,
                    'hotel_id': hid,
                    'room_type_name': room_name,
                    'bed_types': 'Không xác định',
                    'max_guests': 2
                })
                
                bookings_list.append({
                    'booking_id': f"{room_type_id}_{checkin_date}",
                    'hotel_id': hid,
                    'room_type_id': room_type_id,
                    'original_price': price_val,
                    'current_price': price_val,
                    'discount': 0.0,
                    'taxes_included': 1,
                    'extracted_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date
                })

def save_csv(data_list, filename):
    if not data_list:
        print(f"Không có dữ liệu cho file: {filename}")
        return
    df = pd.DataFrame(data_list)
    df.drop_duplicates(inplace=True)
    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath, index=False, encoding='utf-8')
    print(f"Đã xuất file: {filename} ({len(df)} bản ghi)")

save_csv(hotels_list, "Dim_Hotel.csv")
save_csv(locations_list, "Dim_Location.csv")

if facilities_list:
    df_fac = pd.DataFrame(facilities_list).drop_duplicates()
    df_fac.to_csv(os.path.join(output_dir, "Dim_Facility.csv"), index=False, encoding='utf-8')
    print(f"Đã xuất file: Dim_Facility.csv ({len(df_fac)} bản ghi)")

if nearby_list:
    df_nearby = pd.DataFrame(nearby_list).drop_duplicates()
    df_nearby['distance_rank'] = df_nearby.groupby(['hotel_id', 'place_type'])['distance_in_meters'].rank(method='first', ascending=True).astype(int)
    df_nearby.to_csv(os.path.join(output_dir, "Dim_NearbyPlaces.csv"), index=False, encoding='utf-8')
    print(f"Đã xuất file: Dim_NearbyPlaces.csv ({len(df_nearby)} bản ghi)")

save_csv(reviews_list, "Dim_Review.csv")
save_csv(rooms_list, "Dim_RoomType.csv")
save_csv(bookings_list, "Fact_Booking.csv")

print("ETL hoàn tất! Các file CSV sạch đã được lưu tại:", output_dir)
