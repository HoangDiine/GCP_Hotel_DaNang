import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv
from firecrawl import FirecrawlApp
from bs4 import BeautifulSoup

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
app = FirecrawlApp(api_key=API_KEY)

def fetch_search_page_with_dates():
    # Sử dụng đúng ngày người dùng cung cấp
    checkin = "2026-07-26"
    checkout = "2026-07-27"
    url = f"https://www.booking.com/searchresults.vi.html?dest_id=-3712125&dest_type=city&offset=0&checkin={checkin}&checkout={checkout}&selected_currency=VND&currency=VND"
    
    print(f"Đang cào trang tìm kiếm có ngày: {url} ...")
    try:
        response = app.scrape(url, formats=["html"])
        html = response.html if response else ""
    except Exception as e:
        print(f"Lỗi khi cào trang tìm kiếm: {e}")
        html = ""
    
    if html:
        output_dir = os.path.join(PROJECT_ROOT, "raw_html", "search_pages")
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, "search_offset_0_with_dates.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Đã lưu thành công tại: {file_path}")
        
        # Đọc lại và phân tích nhanh
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all(attrs={"data-testid": "property-card"})
        print(f"Tìm thấy {len(cards)} cards khách sạn trên trang.")
        
        if cards:
            # Xem 3 card đầu tiên để kiểm tra giá và đánh giá
            for idx, card in enumerate(cards[:3]):
                print(f"\n--- Khách sạn {idx+1} ---")
                title_tag = card.find(attrs={"data-testid": "title"})
                title = title_tag.get_text(strip=True) if title_tag else "N/A"
                
                price_tag = card.find(attrs={"data-testid": "price-and-discounted-price"})
                price_text = price_tag.get_text(strip=True) if price_tag else "N/A"
                
                score_tag = card.find(attrs={"data-testid": "review-score"})
                score_text = score_tag.get_text(" | ", strip=True) if score_tag else "N/A"
                
                print(f"  Tên: {title}")
                print(f"  Giá: {price_text}")
                print(f"  Đánh giá: {score_text}")
    else:
        print("Lỗi: Không tải được HTML trang tìm kiếm.")

if __name__ == "__main__":
    fetch_search_page_with_dates()
