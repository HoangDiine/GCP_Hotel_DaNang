import os
import sys
from bs4 import BeautifulSoup

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def find_prices_in_all_cards():
    file_path = os.path.join(PROJECT_ROOT, "raw_html", "search_pages", "search_offset_0_with_dates.html")
    if not os.path.exists(file_path):
        # Fallback to direct relative path if not found
        file_path = "raw_html/search_pages/search_offset_0_with_dates.html"
        if not os.path.exists(file_path):
            print(f"Không tìm thấy file: {file_path}")
            return
        
    print(f"Đọc file: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
        
    soup = BeautifulSoup(html, "html.parser")
    for idx, card in enumerate(soup.find_all(attrs={"data-testid": "property-card"})):
        title_el = card.find(attrs={"data-testid": "title"})
        title = title_el.get_text(strip=True) if title_el else "N/A"
        # Tìm tất cả văn bản có chứa VND hoặc đ
        vnd_texts = []
        for tag in card.find_all(True):
            if tag.name in ["script", "style"]:
                continue
            text = tag.get_text(strip=True)
            if "VND" in text and len(text) < 100:
                vnd_texts.append(text)
        print(f"\n[{idx+1}] Khách sạn: {title}")
        print(f"  Các chuỗi VND tìm thấy: {list(set(vnd_texts))}")

if __name__ == "__main__":
    find_prices_in_all_cards()
