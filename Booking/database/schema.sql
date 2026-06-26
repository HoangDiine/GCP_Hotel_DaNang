-- 1. Bảng hotels (Thông tin khách sạn)
CREATE TABLE IF NOT EXISTS hotels (
    hotel_id VARCHAR(100) PRIMARY KEY,
    hotel_name VARCHAR(255) NOT NULL,
    description TEXT,
    stars_rating INTEGER,
    review_count INTEGER,
    popular_facilities TEXT,
    property_type VARCHAR(100),
    checkin_time_start VARCHAR(50),
    checkin_time_end VARCHAR(50),
    checkout_time_start VARCHAR(50),
    checkout_time_end VARCHAR(50)
);

-- 2. Bảng hotel_locations (Địa chỉ khách sạn đã làm sạch và phân tách chi tiết)
CREATE TABLE IF NOT EXISTS hotel_locations (
    hotel_id VARCHAR(100) PRIMARY KEY REFERENCES hotels(hotel_id) ON DELETE CASCADE,
    street_address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    full_address TEXT NOT NULL,
    latitude NUMERIC(10, 8),
    longitude NUMERIC(11, 8)
);

-- 3. Bảng hotel_facilities (Bảng tiện ích chi tiết - Liên kết nhiều nhiều)
CREATE TABLE IF NOT EXISTS hotel_facilities (
    hotel_id VARCHAR(100) REFERENCES hotels(hotel_id) ON DELETE CASCADE,
    facility_name VARCHAR(150) NOT NULL,
    PRIMARY KEY (hotel_id, facility_name)
);

-- 4. Bảng hotel_nearby_places (Lưu các địa điểm lân cận cùng thứ tự khoảng cách)
CREATE TABLE IF NOT EXISTS hotel_nearby_places (
    id SERIAL PRIMARY KEY,
    hotel_id VARCHAR(100) REFERENCES hotels(hotel_id) ON DELETE CASCADE,
    place_name VARCHAR(255) NOT NULL,
    place_type VARCHAR(50), -- 'attraction', 'nature', 'airport', 'restaurant', 'beach', 'transport'
    distance_value NUMERIC(6, 2),
    distance_unit VARCHAR(10),
    distance_in_meters INTEGER,
    distance_rank INTEGER
);

-- 5. Bảng hotel_reviews (Chi tiết đánh giá của khách)
CREATE TABLE IF NOT EXISTS hotel_reviews (
    review_id VARCHAR(100) PRIMARY KEY,
    hotel_id VARCHAR(100) REFERENCES hotels(hotel_id) ON DELETE CASCADE,
    staff_score NUMERIC(3, 1),
    facilities_score NUMERIC(3, 1),
    cleanliness_score NUMERIC(3, 1),
    comfort_score NUMERIC(3, 1),
    value_for_money_score NUMERIC(3, 1),
    location_score NUMERIC(3, 1),
    free_wifi_score NUMERIC(3, 1),
    average_score NUMERIC(3, 1)
);

-- 6. Bảng room_types (Các loại phòng của khách sạn)
CREATE TABLE IF NOT EXISTS room_types (
    room_type_id VARCHAR(150) PRIMARY KEY,
    hotel_id VARCHAR(100) REFERENCES hotels(hotel_id) ON DELETE CASCADE,
    room_type_name VARCHAR(255) NOT NULL,
    bed_types VARCHAR(255),
    max_guests INTEGER
);

-- 7. Bảng room_prices (Bảng Fact lưu mức giá theo ngày)
CREATE TABLE IF NOT EXISTS room_prices (
    booking_id VARCHAR(255) PRIMARY KEY,
    hotel_id VARCHAR(100) REFERENCES hotels(hotel_id) ON DELETE CASCADE,
    room_type_id VARCHAR(150) REFERENCES room_types(room_type_id) ON DELETE CASCADE,
    original_price NUMERIC(15, 2),
    current_price NUMERIC(15, 2),
    discount NUMERIC(15, 2),
    taxes_included INTEGER,
    extracted_at TIMESTAMP,
    checkin_date DATE,
    checkout_date DATE
);

-- Đánh chỉ mục (Indexing) để tối ưu hiệu năng tìm kiếm cho AI
CREATE INDEX IF NOT EXISTS idx_prices_current ON room_prices(current_price);
CREATE INDEX IF NOT EXISTS idx_prices_dates ON room_prices(checkin_date, checkout_date);
CREATE INDEX IF NOT EXISTS idx_places_name ON hotel_nearby_places(place_name);
CREATE INDEX IF NOT EXISTS idx_places_meters ON hotel_nearby_places(distance_in_meters);
CREATE INDEX IF NOT EXISTS idx_facilities_name ON hotel_facilities(facility_name);
