import os
import sys
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from firecrawl import FirecrawlApp

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Load variables from .env file
load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
API_URL = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev")

if not API_KEY:
    print("CẢNH BÁO: Không tìm thấy FIRECRAWL_API_KEY trong .env. Vui lòng thiết lập biến môi trường.")

# Initialize Firecrawl Client
try:
    if API_URL and API_URL != "https://api.firecrawl.dev":
        app = FirecrawlApp(api_key=API_KEY, api_url=API_URL)
    else:
        app = FirecrawlApp(api_key=API_KEY)
except Exception as e:
    print(f"Lỗi khi khởi tạo Firecrawl Client: {e}")
    app = None

SEARCH_DIR = "raw_html/search_pages"
HOTEL_DIR = "raw_html/hotels"

os.makedirs(SEARCH_DIR, exist_ok=True)
os.makedirs(HOTEL_DIR, exist_ok=True)

def fetch_and_save_search_page(page_index: int, checkin: str = "", checkout: str = "", order: str = "", nflt: str = "") -> str:
    """
    Tải trang tìm kiếm Booking.com Đà Nẵng với offset phân trang và lưu file HTML thô.
    Hỗ trợ truyền ngày check-in/check-out, thứ tự sắp xếp (order) và bộ lọc (nflt) để lấy nhiều khách sạn độc nhất.
    """
    if not app:
        print("Lỗi: Firecrawl Client chưa được khởi tạo.")
        return ""
        
    offset = page_index * 25
    order_suffix = f"_{order}" if order else ""
    nflt_suffix = f"_nflt_{nflt.replace('%3D', '_').replace('%3B', '_')}" if nflt else ""
    
    if checkin and checkout:
        file_path = os.path.join(SEARCH_DIR, f"search_offset_{offset}_with_dates{order_suffix}{nflt_suffix}.html")
    else:
        file_path = os.path.join(SEARCH_DIR, f"search_offset_{offset}{order_suffix}{nflt_suffix}.html")
    
    # Kiểm tra xem file đã tồn tại hay chưa để tránh gọi API lãng phí
    if os.path.exists(file_path):
        print(f"Trang danh sách offset {offset}{order_suffix}{nflt_suffix} đã tồn tại offline tại: {file_path}. Bỏ qua.")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    if checkin and checkout:
        url = f"https://www.booking.com/searchresults.vi.html?dest_id=-3712125&dest_type=city&offset={offset}&checkin={checkin}&checkout={checkout}&selected_currency=VND&currency=VND"
    else:
        url = f"https://www.booking.com/searchresults.vi.html?dest_id=-3712125&dest_type=city&offset={offset}"
        
    if order:
        url += f"&order={order}"
    if nflt:
        url += f"&nflt={nflt}"
        
    print(f"Đang tải trang danh sách {page_index + 1} qua Firecrawl (offset={offset}, order={order}, nflt={nflt})...")
    
    try:
        response = app.scrape(url, formats=["html"])
        html_content = response.html if response else ""
        
        if html_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Đã tải thành công và lưu HTML tại: {file_path}")
            # Nghỉ ngắn giữa các lần gọi API để tránh rate limit
            time.sleep(2)
            return html_content
        else:
            print("Lỗi: Firecrawl trả về trang trống.")
            return ""
    except Exception as e:
        print(f"Lỗi khi cào trang danh sách: {e}")
        return ""

def download_hotel_raw_html(hotel_url: str) -> bool:
    """
    Tải trang chi tiết của từng khách sạn dựa trên URL sạch và lưu file HTML thô.
    Tự động chèn ngày check-in/check-out để Booking.com hiển thị bảng giá phòng (#hprt-table).
    """
    if not app:
        print("Lỗi: Firecrawl Client chưa được khởi tạo.")
        return False

    # Lấy slug của khách sạn để làm tên file
    try:
        hotel_slug = hotel_url.split("/hotel/vn/")[-1].replace(".vi.html", "").split("?")[0]
    except Exception:
        hotel_slug = hotel_url.replace("https://", "").replace("/", "_").replace("?", "_")

    file_path = os.path.join(HOTEL_DIR, f"{hotel_slug}.html")
    
    # Tránh tải lại nếu file đã tồn tại offline
    if os.path.exists(file_path):
        print(f"Khách sạn '{hotel_slug}' đã có dữ liệu offline. Bỏ qua.")
        return True
        
    # Tạo URL có ngày nhận/trả phòng (mặc định là 14 ngày sau để có nhiều phòng trống)
    clean_url = hotel_url.split("?")[0]
    checkin_date = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    checkout_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
    url_with_dates = f"{clean_url}?checkin={checkin_date}&checkout={checkout_date}&selected_currency=VND&currency=VND"
    
    print(f"Đang tải trang chi tiết khách sạn '{hotel_slug}' với ngày {checkin_date} -> {checkout_date} từ Firecrawl...")
    try:
        response = app.scrape(
            url_with_dates,
            formats=["html"],
            actions=[
                {"type": "scroll", "direction": "down"},
                {"type": "wait", "milliseconds": 1500},
                {"type": "scroll", "direction": "down"},
                {"type": "wait", "milliseconds": 1500}
            ]
        )
        html_content = response.html if response else ""
        
        if html_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"Đã lưu HTML chi tiết khách sạn tại: {file_path}")
            # Nghỉ ngắn tránh rate limit
            time.sleep(2)
            return True
        else:
            print(f"Lỗi: Firecrawl trả về HTML trống cho khách sạn {hotel_slug}")
            return False
    except Exception as e:
        print(f"Lỗi khi tải trang chi tiết khách sạn {hotel_slug}: {e}")
        return False
