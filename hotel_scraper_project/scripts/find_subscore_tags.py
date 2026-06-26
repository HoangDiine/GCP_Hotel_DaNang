import sys
import os
from bs4 import BeautifulSoup
import re

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

    print("Searching for elements containing 'Nhân' or 'phục' or 'phuc':")
    for el in soup.find_all(True):
        text = el.get_text(strip=True)
        if ("Nhân" in text or "phục" in text or "phuc" in text) and len(text) < 150:
            print(f"Tag: {el.name}, Class: {el.get('class')}, Text: {text}")
except Exception as e:
    print(f"Lỗi: Không thể đọc file HTML ({html_path}): {e}")
