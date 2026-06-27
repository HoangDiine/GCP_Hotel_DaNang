import sqlite3
import sys

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "hotel_warehouse.db"

def verify():
    print("="*60)
    print("KIỂM TRA DỮ LIỆU TRONG DATABASE SQLite")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = ["Dim_Hotel", "Dim_Location", "Dim_Review", "Dim_RoomType", "Fact_Booking"]
    
    for t in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            print(f"- Bảng {t:<15}: có {count} dòng.")
            
            if count > 0:
                cursor.execute(f"SELECT * FROM {t} LIMIT 1")
                row = cursor.fetchone()
                # Lấy tên các cột
                cursor.execute(f"PRAGMA table_info({t})")
                cols = [c[1] for c in cursor.fetchall()]
                
                print(f"  Ví dụ dòng đầu tiên:")
                for col, val in zip(cols, row):
                    print(f"    * {col:<22}: {val}")
                print("-" * 40)
        except Exception as e:
            print(f"Lỗi khi truy vấn bảng {t}: {e}")
            
    conn.close()
    print("="*60)

if __name__ == "__main__":
    verify()
