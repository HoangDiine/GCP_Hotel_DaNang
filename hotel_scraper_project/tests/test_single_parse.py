import os
import sys
import json

# Dynamic path resolution to make it runnable from any directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

from src import parser

# Đảm bảo hiển thị tốt tiếng Việt trên terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def test_parse():
    hotel_id = "crowne-plaza-danang"
    file_path = os.path.join(PROJECT_ROOT, "raw_html", "hotels", f"{hotel_id}.html")
    
    if not os.path.exists(file_path):
        print(f"Lỗi: Không tìm thấy file HTML tại: {file_path}")
        print("Vui lòng lưu nội dung HTML của khách sạn vào đường dẫn trên trước khi chạy test.")
        return

    print(f"Đang phân tích file: {file_path} ...")
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    try:
        # Chạy hàm parse từ parser.py
        result = parser.parse_hotel_details(html_content, hotel_id)
        
        # In kết quả dạng JSON đẹp mắt
        print("\n=== KẾT QUẢ PHÂN TÍCH THỬ NGHIỆM ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Có lỗi xảy ra khi phân tích: {e}")

if __name__ == "__main__":
    test_parse()
