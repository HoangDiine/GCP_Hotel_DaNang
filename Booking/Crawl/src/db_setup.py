import sqlite3
import os
import sys

# Đảm bảo in ký tự Unicode tiếng Việt không bị lỗi trên Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "hotel_warehouse.db"

def init_db():
    print(f"Khởi tạo cơ sở dữ liệu SQLite tại: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Kích hoạt hỗ trợ Foreign Key trong SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Bảng Dim_Hotel
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Dim_Hotel (
        hotel_id TEXT PRIMARY KEY,
        hotel_name TEXT NOT NULL,
        description TEXT,
        stars_rating TEXT,
        review_count INTEGER,
        popular_facilities TEXT,
        property_type TEXT,
        hotel_policies TEXT
    );
    """)

    # 2. Bảng Dim_Location
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Dim_Location (
        hotel_id TEXT PRIMARY KEY,
        address TEXT,
        top_attractions TEXT,
        natural_beauty TEXT,
        nearest_airports TEXT,
        restaurants_cafes TEXT,
        beaches_in_area TEXT,
        public_transport TEXT,
        whats_nearby TEXT,
        FOREIGN KEY (hotel_id) REFERENCES Dim_Hotel(hotel_id) ON DELETE CASCADE
    );
    """)

    # Migration tự động cho database cũ đã tồn tại
    try:
        cursor.execute("ALTER TABLE Dim_Hotel ADD COLUMN hotel_policies TEXT;")
    except sqlite3.OperationalError:
        pass # Đã tồn tại
    try:
        cursor.execute("ALTER TABLE Dim_Location ADD COLUMN whats_nearby TEXT;")
    except sqlite3.OperationalError:
        pass # Đã tồn tại
    try:
        cursor.execute("ALTER TABLE Fact_Booking ADD COLUMN checkin_date TEXT;")
    except sqlite3.OperationalError:
        pass # Đã tồn tại
    try:
        cursor.execute("ALTER TABLE Fact_Booking ADD COLUMN checkout_date TEXT;")
    except sqlite3.OperationalError:
        pass # Đã tồn tại

    # 3. Bảng Dim_Review
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Dim_Review (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        hotel_id TEXT NOT NULL,
        staff_score REAL,
        facilities_score REAL,
        cleanliness_score REAL,
        comfort_score REAL,
        value_for_money_score REAL,
        location_score REAL,
        free_wifi_score REAL,
        average_score REAL,
        FOREIGN KEY (hotel_id) REFERENCES Dim_Hotel(hotel_id) ON DELETE CASCADE
    );
    """)

    # 4. Bảng Dim_RoomType
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Dim_RoomType (
        room_type_id TEXT PRIMARY KEY,
        hotel_id TEXT NOT NULL,
        room_type_name TEXT NOT NULL,
        bed_types TEXT,
        max_guests INTEGER,
        FOREIGN KEY (hotel_id) REFERENCES Dim_Hotel(hotel_id) ON DELETE CASCADE
    );
    """)

    # 5. Bảng Fact_Booking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Fact_Booking (
        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
        hotel_id TEXT NOT NULL,
        room_type_id TEXT NOT NULL,
        original_price REAL,
        current_price REAL,
        discount REAL,
        taxes_included INTEGER, -- 0 hoặc 1
        extracted_at TEXT NOT NULL,
        checkin_date TEXT,
        checkout_date TEXT,
        FOREIGN KEY (hotel_id) REFERENCES Dim_Hotel(hotel_id) ON DELETE CASCADE,
        FOREIGN KEY (room_type_id) REFERENCES Dim_RoomType(room_type_id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
    print("Khởi tạo cấu trúc bảng SQLite thành công.")

if __name__ == "__main__":
    init_db()
