import os
from bs4 import BeautifulSoup

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
html_path = os.path.join(PROJECT_ROOT, "raw_html", "hotels", "truong-tai.html")

if not os.path.exists(html_path):
    html_path = "raw_html/hotels/truong-tai.html"

try:
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")

    container = soup.select_one("[data-testid=review-subscores-desktop]")
    if container:
        print("Found review subscores container!")
        # In ra tất cả các thẻ con có chứa text
        for el in container.find_all(True):
            if el.name in ["span", "div", "p"] and el.string:
                text = el.string.strip()
                if text:
                    print(f"  Tag: {el.name}, Text: {text}")
    else:
        print("Not found review subscores container")
except Exception as e:
    print(f"Lỗi: Không thể đọc file HTML ({html_path}): {e}")
