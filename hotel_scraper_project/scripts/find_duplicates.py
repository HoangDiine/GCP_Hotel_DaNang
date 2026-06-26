import os
import sys
import glob
from bs4 import BeautifulSoup

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HOTEL_DIR = os.path.join(PROJECT_ROOT, "raw_html", "hotels")

# Đảm bảo hiển thị tốt tiếng Việt trên terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def find_and_delete_duplicates():
    html_files = glob.glob(os.path.join(HOTEL_DIR, "*.html"))
    print(f"Tổng số file HTML tìm thấy: {len(html_files)}")
    
    canonical_map = {}
    duplicates = []
    
    for file_path in html_files:
        filename = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html = f.read()
            
            soup = BeautifulSoup(html, "html.parser")
            canonical_el = soup.find("link", rel="canonical")
            
            if canonical_el and canonical_el.get("href"):
                canonical_url = canonical_el["href"].split("?")[0]  # Bỏ query params
            else:
                # Nếu không có canonical, lấy tên khách sạn làm key
                hotel_name_el = soup.select_one("h2.pp-header__title") or soup.select_one("#hp_hotel_name")
                canonical_url = hotel_name_el.get_text(strip=True) if hotel_name_el else None
                
            if not canonical_url:
                print(f"Cảnh báo: Không tìm thấy canonical/tên trong {filename}")
                continue
                
            if canonical_url in canonical_map:
                canonical_map[canonical_url].append(file_path)
                duplicates.append(file_path)
            else:
                canonical_map[canonical_url] = [file_path]
        except Exception as e:
            print(f"Lỗi đọc file {filename}: {e}")
            
    print(f"Tìm thấy {len(duplicates)} file trùng lặp.")
    
    # In thông tin các file trùng lặp
    for canonical_url, paths in canonical_map.items():
        if len(paths) > 1:
            print(f"\nTrùng lặp cho: {canonical_url}")
            # Giữ lại file có dung lượng lớn nhất (thường là bản cào đầy đủ hơn)
            paths_with_sizes = [(p, os.path.getsize(p)) for p in paths]
            paths_with_sizes.sort(key=lambda x: x[1], reverse=True)
            
            keep_path, keep_size = paths_with_sizes[0]
            print(f"  -> GIỮ: {os.path.basename(keep_path)} ({keep_size} bytes)")
            
            for delete_path, delete_size in paths_with_sizes[1:]:
                print(f"  -> XOÁ: {os.path.basename(delete_path)} ({delete_size} bytes)")
                try:
                    os.remove(delete_path)
                    print(f"     Đã xoá {os.path.basename(delete_path)} thành công.")
                except Exception as e:
                    print(f"     Lỗi khi xoá: {e}")
                    
    print("\nHoàn tất xử lý tệp trùng lặp.")

if __name__ == "__main__":
    find_and_delete_duplicates()
