import sys
import os
from bs4 import BeautifulSoup
import re
import unicodedata

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
html_path = os.path.join(PROJECT_ROOT, "raw_html", "hotels", "truong-tai.html")

if not os.path.exists(html_path):
    html_path = "raw_html/hotels/truong-tai.html"

try:
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")

    for el in soup.find_all(True):
        text = el.get_text(strip=True)
        if "Nhân viên" in text and len(text) < 50:
            print("Raw text:", text)
            print("NFC normalized:", unicodedata.normalize("NFC", text))
            print("Code points:", [hex(ord(c)) for c in text])
            parent = el.parent
            if parent:
                print("Parent text:", parent.get_text(" ", strip=True))
                numbers = re.findall(r'\d+[.,]\d+|\d+', parent.get_text(" ", strip=True))
                print("Numbers in parent:", numbers)
            break
except Exception as e:
    print(f"Lỗi: Không thể đọc file HTML ({html_path}): {e}")
