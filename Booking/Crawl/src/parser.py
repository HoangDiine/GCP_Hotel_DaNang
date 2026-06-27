import os
import re
import sys
import unicodedata
from datetime import datetime
from bs4 import BeautifulSoup

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def clean_price(price_str: str) -> float:
    """
    Hàm làm sạch chuỗi giá cực kỳ mạnh mẽ, hỗ trợ cả VND (chỉ có phần nghìn) và USD (có phần thập phân).
    Ví dụ: 'VND 1.878.300', '1,878,300 đ', 'US$ 86.58', '86,58'
    """
    if not price_str:
        return 0.0
        
    # Loại bỏ ký hiệu tiền tệ và khoảng trắng
    price_str = re.sub(r'[VNDđ$US\u200b\s]', '', price_str, flags=re.IGNORECASE)
    
    # Xử lý dấu phân tách hàng nghìn và thập phân
    if ',' in price_str and '.' in price_str:
        if price_str.find(',') < price_str.find('.'):
            price_str = price_str.replace(',', '')
        else:
            price_str = price_str.replace('.', '').replace(',', '.')
    elif ',' in price_str:
        parts = price_str.split(',')
        if len(parts[-1]) == 2:  # Ví dụ 86,58 -> thập phân
            price_str = "".join(parts[:-1]) + "." + parts[-1]
        else:  # Ví dụ 1,800,000 -> hàng nghìn
            price_str = "".join(parts)
    elif '.' in price_str:
        parts = price_str.split('.')
        if len(parts[-1]) == 2:  # Ví dụ 86.58 -> thập phân
            price_str = "".join(parts[:-1]) + "." + parts[-1]
        else:  # Ví dụ 1.800.000 -> hàng nghìn
            price_str = "".join(parts)
            
    cleaned = re.sub(r'[^\d.]', '', price_str)
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def extract_hotel_urls_from_html(html_content: str) -> list:
    """
    Quét tất cả thẻ <a> trong trang danh sách tìm kiếm có chứa '/hotel/vn/'
    """
    soup = BeautifulSoup(html_content, "html.parser")
    hotel_urls = set()
    
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/hotel/vn/" in href:
            # Làm sạch URL: bỏ query parameters
            clean_url = href.split("?")[0]
            if not clean_url.startswith("http"):
                clean_url = "https://www.booking.com" + clean_url
            hotel_urls.add(clean_url)
            
    return list(hotel_urls)

def parse_hotel_details(html_content: str, hotel_id: str, checkin: str = "", checkout: str = "") -> dict:
    """
    Phân tích trang HTML chi tiết khách sạn và trả về các cấu trúc dữ liệu tương ứng 5 bảng.
    Sử dụng thuật toán bóc tách độc lập class (Class-Independent) cực kỳ bền vững.
    """
    if not checkin:
        checkin_match = re.search(r'checkin=(\d{4}-\d{2}-\d{2})', html_content)
        if checkin_match:
            checkin = checkin_match.group(1)
    if not checkout:
        checkout_match = re.search(r'checkout=(\d{4}-\d{2}-\d{2})', html_content)
        if checkout_match:
            checkout = checkout_match.group(1)

    soup = BeautifulSoup(html_content, "html.parser")
    
    # ------------------ 1. Dim_Hotel ------------------
    # Tên khách sạn
    hotel_name_el = soup.select_one("h2.pp-header__title")
    if not hotel_name_el:
        hotel_name_el = soup.select_one("#hp_hotel_name")
    hotel_name = hotel_name_el.get_text(strip=True) if hotel_name_el else "Không xác định"
    # Chuẩn hóa tên
    if hotel_name.startswith("Khách sạn"):
        hotel_name = hotel_name.replace("Khách sạn", "", 1).strip()
    elif hotel_name.startswith("Căn hộ"):
        hotel_name = hotel_name.replace("Căn hộ", "", 1).strip()

    # Mô tả khách sạn
    desc_el = soup.select_one('p[data-testid="property-description"]')
    if not desc_el:
        desc_el = soup.select_one("#property_description_content")
    description = desc_el.get_text(strip=True) if desc_el else ""

    # Xếp hạng sao (Stars rating)
    stars_rating = "0 trên 5 sao"
    stars_el = soup.select_one('button[data-testid="quality-rating"] span[data-testid="rating-stars"]')
    if stars_el and stars_el.get("aria-label"):
        stars_rating = stars_el["aria-label"]
    else:
        stars_container = soup.select_one('span[data-testid="rating-stars"]')
        if stars_container and stars_container.get("aria-label"):
            stars_rating = stars_container["aria-label"]

    # Số lượng đánh giá (Review count)
    review_count = 0
    review_count_el = soup.select_one('div[data-testid="review-score-right-component"]')
    if review_count_el:
        text = review_count_el.get_text(" ", strip=True)
        match = re.search(r'(\d+[\d\s,.]*)\s*(đánh giá|nhận xét|review)', text, re.IGNORECASE)
        if match:
            review_count = int(re.sub(r'[^\d]', '', match.group(1)))
            
    if review_count == 0:
        # Fallback tìm trong toàn bộ văn bản có pattern score-bar hoặc review count
        text_all = soup.get_text(" ", strip=True)
        match = re.search(r'(\d+[\d\s,.]*)\s*(đánh giá|nhận xét|review của khách)', text_all, re.IGNORECASE)
        if match:
            review_count = int(re.sub(r'[^\d]', '', match.group(1)))

    # Tiện nghi nổi bật (Popular facilities)
    popular_facilities_list = []
    
    # Cách 1: Tìm H2/H3/H4/Div chứa tiêu đề "Các tiện nghi được ưa chuộng nhất"
    fac_header = None
    for tag in soup.find_all(["h2", "h3", "h4", "div"]):
        text_val = unicodedata.normalize("NFC", tag.get_text(strip=True))
        if "tiện nghi được ưa chuộng nhất" in text_val.lower() and len(text_val) < 50:
            fac_header = tag
            break
            
    if fac_header:
        parent = fac_header.parent
        ul = fac_header.find_next_sibling("ul")
        if not ul and parent:
            ul = parent.find_next_sibling("ul")
        if not ul and parent:
            ul = parent.find("ul")
            
        if ul:
            lis = ul.find_all("li")
            popular_facilities_list = [li.get_text(strip=True) for li in lis if li.get_text(strip=True)]
            
    # Cách 2: Fallback dùng selector cũ
    if not popular_facilities_list:
        fac_container = soup.select_one('div[data-testid="property-most-popular-facilities"]')
        if fac_container:
            popular_facilities_list = [item.get_text(strip=True) for item in fac_container.find_all("div") if item.get_text(strip=True)]
            
    # Cách 3: Fallback dùng class cũ
    if not popular_facilities_list:
        fac_items_alt = soup.select(".pp-facilities-popular li span")
        popular_facilities_list = [item.get_text(strip=True) for item in fac_items_alt if item.get_text(strip=True)]
        
    # Làm sạch danh sách: loại bỏ khoảng trắng dư thừa, ký tự lặp
    popular_facilities_list = [re.sub(r'\s+', ' ', f).strip() for f in popular_facilities_list]
    popular_facilities = ", ".join(list(set(popular_facilities_list))) if popular_facilities_list else ""

    # Loại hình lưu trú (Property type)
    property_type = "Khách sạn"
    breadcrumb_list = soup.select('ol[data-testid="breadcrumb-list"] li span')
    if breadcrumb_list:
        property_type = breadcrumb_list[-1].get_text(strip=True)
    else:
        breadcrumb_list_alt = soup.select(".breadcrumb_list_item span")
        if breadcrumb_list_alt:
            property_type = breadcrumb_list_alt[-1].get_text(strip=True)

    # Chính sách khách sạn (General policies)
    hotel_policies = ""
    for sec in soup.find_all("section"):
        text_val = unicodedata.normalize("NFC", sec.get_text())
        if "quy tắc chung" in text_val.lower() or "chính sách chung" in text_val.lower():
            raw_text = sec.get_text("\n", strip=True)
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
            filtered_lines = []
            for line in lines:
                if "xem phòng trống" in line.lower() or "nhận yêu cầu đặc biệt" in line.lower():
                    continue
                filtered_lines.append(line)
            hotel_policies = "\n".join(filtered_lines)
            break

    dim_hotel = {
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "description": description,
        "stars_rating": stars_rating,
        "review_count": review_count,
        "popular_facilities": popular_facilities,
        "property_type": property_type,
        "hotel_policies": hotel_policies
    }

    # ------------------ 2. Dim_Location ------------------
    # Địa chỉ
    address = ""
    address_el = soup.select_one('div[data-testid="PropertyHeaderAddressDesktop-wrapper"]')
    if address_el:
        # Lấy text của địa chỉ, cắt bỏ phần khuyến mại/bản đồ nếu có
        address = address_el.get_text(" ", strip=True)
        if "Hiển thị bản đồ" in address:
            address = address.split("Hiển thị bản đồ")[0].strip()
    if not address:
        address_el_alt = soup.select_one("span.hp_address_subtitle")
        if address_el_alt:
            address = address_el_alt.get_text(strip=True)

    # Thuật toán tìm thông tin xung quanh độc lập class (Class-Independent)
    def get_surroundings_items(header_text):
        for tag in soup.find_all(["div", "span", "h2", "h3", "h4"]):
            text_val = tag.get_text(strip=True)
            # So khớp nếu danh mục nằm trong tiêu đề và độ dài văn bản tiêu đề ngắn
            if header_text.lower() in text_val.lower() and len(text_val) < 50:
                # Tránh trùng với các tiện ích khác (ví dụ "Xe đưa đón sân bay")
                if "xe đưa đón" in text_val.lower() or "bếp" in text_val.lower() or "phòng" in text_val.lower():
                    continue
                
                # 1. Thử sibling tiếp theo
                sib = tag.find_next_sibling()
                while sib:
                    if sib.name in ["ul", "ol"]:
                        lis = sib.find_all("li")
                        if lis:
                            return "; ".join([li.get_text(" ", strip=True) for li in lis if li.get_text(strip=True)])
                    if sib.name in ["h2", "h3", "h4", "div"] and len(sib.get_text(strip=True)) < 50:
                        break
                    sib = sib.find_next_sibling()
                
                # 2. Thử tìm trong parent's sibling
                parent = tag.find_parent()
                if parent:
                    sib = parent.find_next_sibling()
                    while sib:
                        if sib.name in ["ul", "ol"]:
                            lis = sib.find_all("li")
                            if lis:
                                return "; ".join([li.get_text(" ", strip=True) for li in lis if li.get_text(strip=True)])
                        if sib.name in ["h2", "h3", "h4", "div"] and len(sib.get_text(strip=True)) < 50:
                            break
                        sib = sib.find_next_sibling()
        return ""

    # Trích xuất địa điểm từ mô tả nếu khối Xung quanh bị trống (do lazy load của Booking)
    def extract_location_info_from_description(desc_text):
        if not desc_text:
            return ""
        desc_text = unicodedata.normalize("NFC", desc_text)
        sentences = re.split(r'(?<=[.!?])\s+', desc_text)
        matched_sentences = []
        keywords = ["cách", "bán kính", "đi bộ", "km", " m ", " m,", " m.", "sân bay", "di chuyển", "gần", "tọa lạc", "nằm ở", "nhìn ra", "giáp biển"]
        for s in sentences:
            s_lower = s.lower()
            if any(kw in s_lower for kw in keywords):
                if len(s) < 220:
                    matched_sentences.append(s.strip())
        return "; ".join(matched_sentences)

    desc_location = extract_location_info_from_description(description)
    top_attractions = get_surroundings_items("Địa điểm tham quan hàng đầu") or get_surroundings_items("Những điểm hấp dẫn nhất")
    
    # Sử dụng thông tin trích xuất được từ mô tả làm fallback
    if not top_attractions and desc_location:
        top_attractions = desc_location

    dim_location = {
        "hotel_id": hotel_id,
        "address": address,
        "top_attractions": top_attractions,
        "natural_beauty": get_surroundings_items("Cảnh đẹp thiên nhiên"),
        "nearest_airports": get_surroundings_items("Sân bay") or get_surroundings_items("Các sân bay gần nhất"),
        "restaurants_cafes": get_surroundings_items("Nhà hàng & quán cà phê") or get_surroundings_items("Nhà hàng"),
        "beaches_in_area": get_surroundings_items("Các bãi biển trong khu vực") or get_surroundings_items("Bãi biển"),
        "public_transport": get_surroundings_items("Phương tiện công cộng"),
        "whats_nearby": get_surroundings_items("Xung quanh có gì") or get_surroundings_items("Xung quanh có gì?") or get_surroundings_items("Xung quanh")
    }

    # ------------------ 3. Dim_Review ------------------
    # Điểm đánh giá chi tiết
    subscores = {
        "staff_score": 0.0,
        "facilities_score": 0.0,
        "cleanliness_score": 0.0,
        "comfort_score": 0.0,
        "value_for_money_score": 0.0,
        "location_score": 0.0,
        "free_wifi_score": 0.0
    }
    
    # Lấy toàn bộ text của trang và chuẩn hóa NFC tiếng Việt
    norm_text = unicodedata.normalize("NFC", soup.get_text(" ", strip=True))
    norm_text = re.sub(r'\s+', ' ', norm_text)
    
    patterns = {
        "staff_score": r'Nhân viên\s*(?:phục vụ)?\s*(\d+[\.,]\d+|\d+)',
        "facilities_score": r'Tiện nghi\s*(\d+[\.,]\d+|\d+)',
        "cleanliness_score": r'Sạch sẽ\s*(\d+[\.,]\d+|\d+)',
        "comfort_score": r'Thoải mái\s*(\d+[\.,]\d+|\d+)',
        "value_for_money_score": r'Đáng giá tiền\s*(\d+[\.,]\d+|\d+)',
        "location_score": r'Địa điểm\s*(\d+[\.,]\d+|\d+)',
        "free_wifi_score": r'WiFi miễn phí\s*(\d+[\.,]\d+|\d+)'
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, norm_text, re.IGNORECASE)
        if match:
            val_str = match.group(1).replace(",", ".")
            try:
                subscores[key] = float(val_str)
            except ValueError:
                pass

    # Điểm đánh giá trung bình (Average score)
    average_score = 0.0
    avg_el = soup.select_one('div[data-testid="review-score-component"] .dff2e52086')
    if avg_el:
        try:
            average_score = float(avg_el.get_text(strip=True).replace(",", "."))
        except ValueError:
            pass
    if average_score == 0.0:
        # Fallback: tìm điểm trung bình bằng regex trong review-score-component
        avg_el_alt = soup.select_one('[data-testid="review-score-component"]')
        if avg_el_alt:
            score_text = avg_el_alt.get_text(" ", strip=True)
            numbers = re.findall(r'\d+[\.,]\d+|\d+', score_text)
            if numbers:
                average_score = float(numbers[0].replace(",", "."))

    dim_review = {
        "hotel_id": hotel_id,
        "average_score": average_score,
        **subscores
    }

    # ------------------ 4 & 5. Dim_RoomType & Fact_Booking ------------------
    dim_room_types = []
    fact_bookings = []

    table = soup.select_one("#hprt-table")
    if table:
        tbody = table.select_one("tbody")
        rows = tbody.select("tr") if tbody else []
        
        current_room_name = ""
        current_room_id = ""
        current_bed_types = ""
        current_max_guests = 2

        for row in rows:
            # Nhận biết dòng chứa liên kết phòng mới
            room_cell = row.select_one(".hprt-roomtype-link")
            if room_cell:
                current_room_name = room_cell.get_text(strip=True)
                current_room_name = re.sub(r'\s+', ' ', current_room_name)
                
                # Tạo room_slug không dấu
                room_slug = current_room_name.lower()
                char_map = {
                    'á': 'a', 'à': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
                    'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
                    'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
                    'é': 'e', 'è': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
                    'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
                    'í': 'i', 'ì': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
                    'ó': 'o', 'ò': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
                    'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
                    'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
                    'ú': 'u', 'ù': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
                    'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
                    'ý': 'y', 'ỳ': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
                    'đ': 'd', ' ': '-'
                }
                for c, r in char_map.items():
                    room_slug = room_slug.replace(c, r)
                room_slug = re.sub(r'[^a-z0-9\-]', '', room_slug)
                room_slug = re.sub(r'\-+', '-', room_slug).strip('-')
                
                current_room_id = f"{hotel_id}_{room_slug}"

                # Loại giường
                bed_cell = row.select_one(".appartment-bed-types-wrapper .room-config li")
                if not bed_cell:
                    bed_cell = row.select_one(".rt-bed-type")
                current_bed_types = bed_cell.get_text(strip=True) if bed_cell else ""
                current_bed_types = re.sub(r'\s+', ' ', current_bed_types)

                # Số khách tối đa
                occupancy_cell = row.select_one(".hprt-table-cell-occupancy")
                if occupancy_cell:
                    adult_icons = occupancy_cell.select(".c-occupancy-icons__adults i")
                    if adult_icons:
                        current_max_guests = len(adult_icons)
                    else:
                        occupancy_text = occupancy_cell.get_text(strip=True)
                        nums = re.findall(r'\d+', occupancy_text)
                        if nums:
                            current_max_guests = int(nums[0])
                        else:
                            current_max_guests = 2
                
                dim_room_types.append({
                    "room_type_id": current_room_id,
                    "hotel_id": hotel_id,
                    "room_type_name": current_room_name,
                    "bed_types": current_bed_types,
                    "max_guests": current_max_guests
                })

            # Giá đặt phòng (Fact_Booking)
            price_cell = row.select_one(".hprt-table-cell-price")
            if price_cell and current_room_id:
                # Giá gốc
                orig_price_el = price_cell.select_one(".bui-price-display__original")
                if not orig_price_el:
                    orig_price_el = price_cell.select_one(".bui-u-line-through")
                original_price = clean_price(orig_price_el.get_text(strip=True)) if orig_price_el else 0.0

                # Giá hiện tại
                curr_price_el = price_cell.select_one(".bui-price-display__value span")
                if not curr_price_el:
                    curr_price_el = price_cell.select_one(".prco-val-bui-wrapper")
                if not curr_price_el:
                    curr_price_el = price_cell.select_one(".hprt-price-block-wrapper")
                current_price = clean_price(curr_price_el.get_text(strip=True)) if curr_price_el else 0.0

                if original_price == 0.0:
                    original_price = current_price

                discount = max(0.0, original_price - current_price)

                # Thuế phí
                taxes_included = 1
                tax_el = price_cell.select_one(".prd-taxes-and-fees-under-price")
                if tax_el:
                    tax_text = tax_el.get_text(strip=True)
                    if "chưa bao gồm" in tax_text.lower() or "không bao gồm" in tax_text.lower():
                        taxes_included = 0
                
                if current_price > 0:
                    fact_bookings.append({
                        "hotel_id": hotel_id,
                        "room_type_id": current_room_id,
                        "original_price": original_price,
                        "current_price": current_price,
                        "discount": discount,
                        "taxes_included": taxes_included,
                        "extracted_at": datetime.now().isoformat(),
                        "checkin_date": checkin if checkin else None,
                        "checkout_date": checkout if checkout else None
                    })

    # ------------------ New Raw Fields (Extracted for raw data) ------------------
    # 1. Canonical URL (standard Booking.com URL format using hotel_id)
    canonical_url = f"https://www.booking.com/hotel/vn/{hotel_id}.vi.html"

    # 2. Latitude & Longitude
    latitude = None
    longitude = None
    latlng_el = soup.find(attrs={"data-atlas-latlng": True})
    if latlng_el:
        latlng_val = latlng_el["data-atlas-latlng"]
        try:
            lat_str, lng_str = latlng_val.split(",")
            latitude = float(lat_str.strip())
            longitude = float(lng_str.strip())
        except Exception:
            pass

    # 3. Review score word/descriptor
    review_score_word = ""
    review_score_el = soup.select_one('[data-testid="review-score-component"]')
    if review_score_el:
        text = unicodedata.normalize("NFC", review_score_el.get_text(" ", strip=True))
        for word in ["Tuyệt hảo", "Xuất sắc", "Rất tốt", "Tốt", "Tiêu chuẩn", "Tuyệt vời"]:
            if word in text:
                review_score_word = word
                break
        if not review_score_word:
            for span in review_score_el.find_all("span"):
                span_text = span.get_text(strip=True)
                if span_text and not any(c.isdigit() for c in span_text) and "đánh giá" not in span_text.lower():
                    review_score_word = span_text
                    break

    # 4. Numeric star rating value
    stars_rating_value = 0
    stars_match = re.search(r'(\d+)', stars_rating)
    if stars_match:
        try:
            stars_rating_value = int(stars_match.group(1))
        except ValueError:
            pass

    # 5. List of image URLs
    hotel_images = []
    gallery_wrapper = soup.select_one('[data-testid="GalleryUnifiedDesktop-wrapper"]') or soup.select_one('#photo_wrapper')
    if gallery_wrapper:
        for img in gallery_wrapper.find_all("img", src=True):
            src = img["src"]
            if src.startswith("http") and ".jpg" in src:
                hotel_images.append(src)
    # Deduplicate preserving order
    seen_imgs = set()
    hotel_images = [x for x in hotel_images if not (x in seen_imgs or seen_imgs.add(x))]

    # Cập nhật các sub-dictionaries để lưu trữ vào DB nếu cần hoặc phục vụ phân tích
    dim_hotel["canonical_url"] = canonical_url
    dim_hotel["stars_rating_value"] = stars_rating_value
    dim_location["latitude"] = latitude
    dim_location["longitude"] = longitude
    dim_review["review_score_word"] = review_score_word

    return {
        "dim_hotel": dim_hotel,
        "dim_location": dim_location,
        "dim_review": dim_review,
        "dim_room_types": dim_room_types,
        "fact_bookings": fact_bookings,
        "canonical_url": canonical_url,
        "latitude": latitude,
        "longitude": longitude,
        "review_score_word": review_score_word,
        "stars_rating_value": stars_rating_value,
        "hotel_images": hotel_images
    }

def parse_search_results_page(html_content: str, checkin: str = "", checkout: str = "") -> list:
    """
    Phân tích trang HTML danh sách tìm kiếm Booking.com Đà Nẵng và trích xuất
    toàn bộ thông tin các khách sạn trên trang (thông thường là 25 card/trang).
    Trả về danh sách các dictionary tương thích với cấu trúc của parse_hotel_details.
    """
    if not checkin:
        checkin_match = re.search(r'checkin=(\d{4}-\d{2}-\d{2})', html_content)
        if checkin_match:
            checkin = checkin_match.group(1)
    if not checkout:
        checkout_match = re.search(r'checkout=(\d{4}-\d{2}-\d{2})', html_content)
        if checkout_match:
            checkout = checkout_match.group(1)

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all(attrs={"data-testid": "property-card"})
    
    parsed_results = []
    for idx, card in enumerate(cards):
        # 1. Tên khách sạn
        title_tag = card.find(attrs={"data-testid": "title"})
        hotel_name = title_tag.get_text(strip=True) if title_tag else "Không xác định"
        
        # 2. URL và ID khách sạn
        link_tag = card.find(attrs={"data-testid": "title-link"})
        hotel_url = link_tag["href"] if link_tag and link_tag.has_attr("href") else ""
        if hotel_url:
            try:
                hotel_id = hotel_url.split("/hotel/vn/")[-1].replace(".vi.html", "").split("?")[0]
            except Exception:
                hotel_id = hotel_url.replace("https://", "").replace("/", "_").replace("?", "_")
        else:
            hotel_id = f"unknown_{idx}_{int(datetime.now().timestamp())}"
            
        # 3. Địa chỉ
        address_tag = card.find(attrs={"data-testid": "address"})
        if not address_tag:
            address_tag = card.find(attrs={"data-testid": "address-link"})
        address = address_tag.get_text(strip=True) if address_tag else "Đà Nẵng"
        
        # 4. Khoảng cách
        distance_tag = card.find(attrs={"data-testid": "distance"})
        distance = distance_tag.get_text(strip=True) if distance_tag else ""
        
        # 5. Xếp hạng sao
        stars_rating = "0 trên 5 sao"
        stars_div = card.find(attrs={"data-testid": "rating-stars"})
        if stars_div:
            parent_label = stars_div.parent.get("aria-label") if stars_div.parent else None
            if parent_label:
                match = re.search(r'(\d+)', parent_label)
                if match:
                    stars_rating = f"{match.group(1)} trên 5 sao"
            else:
                self_label = stars_div.get("aria-label")
                if self_label:
                    match = re.search(r'(\d+)', self_label)
                    if match:
                        stars_rating = f"{match.group(1)} trên 5 sao"
        
        # 6. Đánh giá (Điểm trung bình và số lượng đánh giá)
        review_tag = card.find(attrs={"data-testid": "review-score"})
        average_score = 0.0
        review_count = 0
        if review_tag:
            review_text = unicodedata.normalize("NFC", review_tag.get_text(" | ", strip=True))
            score_match = re.search(r'(?:Đạt điểm|Điểm số)\s*(\d+[\.,]\d+|\d+)', review_text, re.IGNORECASE)
            if score_match:
                average_score = float(score_match.group(1).replace(",", "."))
            else:
                num_match = re.search(r'(\d+[\.,]\d+|\d+)', review_text)
                if num_match:
                    average_score = float(num_match.group(1).replace(",", "."))
            
            count_match = re.search(r'(\d+[\d\s,.]*)\s*(đánh giá|nhận xét|review)', review_text, re.IGNORECASE)
            if count_match:
                review_count = int(re.sub(r'[^\d]', '', count_match.group(1)))
                
        # 7. Điểm vị trí (bóc tách từ secondary review score nếu có)
        location_score = average_score
        loc_score_tag = card.find(attrs={"data-testid": "secondary-review-score-link"})
        if loc_score_tag:
            loc_text = unicodedata.normalize("NFC", loc_score_tag.get_text(strip=True))
            loc_match = re.search(r'(\d+[\.,]\d+|\d+)', loc_text)
            if loc_match:
                try:
                    location_score = float(loc_match.group(1).replace(",", "."))
                except ValueError:
                    pass

        # 8. Loại hình lưu trú (Property type)
        property_type = "Khách sạn"
        name_lower = hotel_name.lower()
        if "resort" in name_lower:
            property_type = "Resort"
        elif "căn hộ" in name_lower or "apartment" in name_lower:
            property_type = "Căn hộ"
        elif "villa" in name_lower or "biệt thự" in name_lower:
            property_type = "Biệt thự"
        elif "homestay" in name_lower:
            property_type = "Homestay"

        # 9. Tên phòng gợi ý
        room_type_name = "Phòng Tiêu Chuẩn"
        recommended_div = card.find(attrs={"data-testid": "recommended-units"})
        if recommended_div:
            room_name_el = recommended_div.find("h4")
            if room_name_el:
                room_type_name = room_name_el.get_text(strip=True)
            else:
                room_name_el = recommended_div.find(["a", "span", "div"])
                if room_name_el:
                    room_type_name = room_name_el.get_text(strip=True)
        else:
            availability_single = card.find(attrs={"data-testid": "availability-single"})
            if availability_single:
                h4 = availability_single.find("h4")
                if h4:
                    room_type_name = h4.get_text(strip=True)
                else:
                    first_div = availability_single.find("div")
                    if first_div:
                        room_type_name = first_div.get_text(strip=True)
                        
        room_type_name = re.sub(r'\s+', ' ', room_type_name).strip()
        
        # 10. Thông tin giường
        bed_types = "1 giường đôi"
        for text_el in card.find_all(string=True):
            normalized_text = unicodedata.normalize("NFC", text_el)
            if "giường" in normalized_text.lower() or "bed" in normalized_text.lower():
                bed_types = normalized_text.strip()
                break
        bed_types = re.sub(r'\s+', ' ', bed_types).strip()
                
        # 11. Số khách tối đa
        max_guests = 2
        nights_guests_div = card.find(attrs={"data-testid": "price-for-x-nights"})
        if nights_guests_div:
            guests_text = nights_guests_div.get_text(strip=True)
            guest_match = re.search(r'(\d+)\s*(người|adult|guest)', guests_text, re.IGNORECASE)
            if guest_match:
                max_guests = int(guest_match.group(1))

        # 12. Giá gốc và giá hiện tại
        price_wrapper = card.find(attrs={"data-testid": "availability-rate-information"})
        if not price_wrapper:
            price_wrapper = card.find(attrs={"data-testid": "availability-rate-wrapper"})
        if not price_wrapper:
            price_wrapper = card
            
        prices_found = []
        for text_el in price_wrapper.find_all(string=True):
            clean_t = text_el.strip()
            if "VND" in clean_t:
                val = clean_price(clean_t)
                if val > 0:
                    prices_found.append(val)
                    
        # Loại bỏ giá trùng lặp
        unique_prices = []
        for p in prices_found:
            if p not in unique_prices:
                unique_prices.append(p)
                
        if len(unique_prices) >= 2:
            current_price = min(unique_prices)
            original_price = max(unique_prices)
        elif len(unique_prices) == 1:
            current_price = unique_prices[0]
            original_price = unique_prices[0]
        else:
            price_tag = card.find(attrs={"data-testid": "price-and-discounted-price"})
            val = clean_price(price_tag.get_text(strip=True)) if price_tag else 0.0
            current_price = val
            original_price = val
            
        discount = max(0.0, original_price - current_price)
        
        # 13. Thuế phí
        taxes_included = 1
        for text_el in card.find_all(string=True):
            norm_t = unicodedata.normalize("NFC", text_el).lower()
            if "chưa bao gồm" in norm_t or "không bao gồm" in norm_t:
                taxes_included = 0
                break
                
        # 14. Tạo cấu trúc tương ứng với Schema
        dim_hotel = {
            "hotel_id": hotel_id,
            "hotel_name": hotel_name,
            "description": f"Khách sạn {hotel_name} tọa lạc tại Đà Nẵng, {distance}." if distance else f"Khách sạn {hotel_name} tọa lạc tại Đà Nẵng.",
            "stars_rating": stars_rating,
            "review_count": review_count,
            "popular_facilities": "WiFi miễn phí, Lễ tân 24 giờ", # Mặc định cho trang danh sách
            "property_type": property_type,
            "hotel_policies": ""
        }

        dim_location = {
            "hotel_id": hotel_id,
            "address": address,
            "top_attractions": f"Cách trung tâm Đà Nẵng khoảng {distance}." if distance else "",
            "natural_beauty": "",
            "nearest_airports": "",
            "restaurants_cafes": "",
            "beaches_in_area": "",
            "public_transport": "",
            "whats_nearby": ""
        }

        dim_review = {
            "hotel_id": hotel_id,
            "average_score": average_score,
            "staff_score": average_score,
            "facilities_score": average_score,
            "cleanliness_score": average_score,
            "comfort_score": average_score,
            "value_for_money_score": average_score,
            "location_score": location_score,
            "free_wifi_score": average_score
        }

        room_slug = room_type_name.lower()
        # Chuyển đổi ký tự tiếng Việt không dấu
        char_map = {
            'á': 'a', 'à': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
            'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
            'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
            'é': 'e', 'è': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
            'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
            'í': 'i', 'ì': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
            'ó': 'o', 'ò': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
            'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
            'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
            'ú': 'u', 'ù': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
            'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
            'ý': 'y', 'ỳ': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
            'đ': 'd', ' ': '-'
        }
        for c, r in char_map.items():
            room_slug = room_slug.replace(c, r)
        room_slug = re.sub(r'[^a-z0-9\-]', '', room_slug)
        room_slug = re.sub(r'\-+', '-', room_slug).strip('-')
        
        room_type_id = f"{hotel_id}_{room_slug}" if room_slug else f"{hotel_id}_standard-room"

        dim_room_types = [{
            "room_type_id": room_type_id,
            "hotel_id": hotel_id,
            "room_type_name": room_type_name,
            "bed_types": bed_types,
            "max_guests": max_guests
        }]

        fact_bookings = []
        if current_price > 0:
            fact_bookings.append({
                "hotel_id": hotel_id,
                "room_type_id": room_type_id,
                "original_price": original_price,
                "current_price": current_price,
                "discount": discount,
                "taxes_included": taxes_included,
                "extracted_at": datetime.now().isoformat(),
                "checkin_date": checkin if checkin else None,
                "checkout_date": checkout if checkout else None
            })

        parsed_results.append({
            "dim_hotel": dim_hotel,
            "dim_location": dim_location,
            "dim_review": dim_review,
            "dim_room_types": dim_room_types,
            "fact_bookings": fact_bookings
        })
        
    return parsed_results
