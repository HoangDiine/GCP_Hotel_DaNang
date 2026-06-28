import sys
import psycopg2
from psycopg2.extensions import register_adapter, AsIs
from psycopg2.extras import execute_values
import pandas as pd
import numpy as np
import os
from google.cloud import bigquery

# Force UTF-8 for stdout on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Register adapters for numpy types so psycopg2 knows how to handle them
register_adapter(np.int64, AsIs)
register_adapter(np.float64, AsIs)

# Cấu hình Database từ biến môi trường (hoặc fallback mặc định)
db_host = os.environ.get("DB_HOST", "136.110.50.188")
db_port = os.environ.get("DB_PORT", "5432")
db_name = os.environ.get("DB_NAME", "postgres")
db_user = os.environ.get("DB_USER", "postgres")
db_password = os.environ.get("DB_PASSWORD", "Capstone2_2026")

cleaned_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleaned_tables")

def get_connection():
    print(f"Đang kết nối tới PostgreSQL tại {db_host}:{db_port}/{db_name} với user: {db_user}...")
    return psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )

def load_csv_to_table(cursor, conn, file_name, table_name):
    path = os.path.join(cleaned_dir, file_name)
    if not os.path.exists(path):
        print(f"Không tìm thấy file: {file_name}")
        return
        
    print(f"Đang import dữ liệu từ {file_name} vào bảng {table_name}...")
    df = pd.read_csv(path)
    
    # Thay thế giá trị NaN bằng None để chèn đúng định dạng NULL trong PostgreSQL
    df = df.where(pd.notnull(df), None)
    
    # Xây dựng câu lệnh INSERT động với ON CONFLICT DO NOTHING để tránh lỗi trùng lặp khi chạy lại
    columns = list(df.columns)
    col_str = ", ".join(columns)
    insert_query = f"INSERT INTO {table_name} ({col_str}) VALUES %s ON CONFLICT DO NOTHING"
    
    # Thực hiện chèn theo lô (batch insert) sau khi chuyển đổi numpy types sang python native types
    list_records = []
    for row in df.itertuples(index=False, name=None):
        clean_row = []
        for val in row:
            if pd.isna(val):
                clean_row.append(None)
            elif isinstance(val, (np.integer, int)):
                clean_row.append(int(val))
            elif isinstance(val, (np.floating, float)):
                clean_row.append(float(val))
            else:
                clean_row.append(val)
        list_records.append(tuple(clean_row))
    
    execute_values(cursor, insert_query, list_records, page_size=1000)
    conn.commit()
    print(f"Hoàn thành import {len(df)} dòng vào bảng {table_name}.")

def load_csv_to_bigquery(file_name, table_name):
    path = os.path.join(cleaned_dir, file_name)
    if not os.path.exists(path):
        print(f"[BigQuery] Không tìm thấy file: {file_name}")
        return

    dataset_id = os.environ.get("BQ_DATASET", "danang_hotels_analytics")
    write_disposition = "WRITE_TRUNCATE"
    if table_name == "room_prices":
        write_disposition = "WRITE_APPEND"

    # Cách 1: Thử nạp bằng Python SDK (tối ưu cho môi trường Production / Cloud Run)
    try:
        bq_client = bigquery.Client()
        table_ref = f"{bq_client.project}.{dataset_id}.{table_name}"
        print(f"[BigQuery SDK] Đang nạp {file_name} vào {table_ref}...")
        df = pd.read_csv(path)
        job_config = bigquery.LoadJobConfig(
            write_disposition=write_disposition,
            autodetect=True,
        )
        job = bq_client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        job.result()
        print(f"[BigQuery SDK] Nạp thành công {len(df)} dòng vào {table_ref}.")
        return
    except Exception as sdk_err:
        print(f"[BigQuery SDK] Không thể nạp bằng Python SDK: {sdk_err}")
        print("[BigQuery CLI] Đang kích hoạt chế độ dự phòng bằng công cụ bq CLI...")

    # Cách 2: Chế độ dự phòng bằng cách gọi trực tiếp bq CLI (Dành cho chạy Local)
    try:
        import subprocess
        # Thiết lập cờ replace/append cho bq CLI
        replace_flag = "--replace" if write_disposition == "WRITE_TRUNCATE" else ""
        
        cmd = [
            "bq.cmd" if os.name == "nt" else "bq",
            "load",
            "--source_format=CSV",
            "--autodetect",
            "--allow_quoted_newlines",
        ]
        if replace_flag:
            cmd.append(replace_flag)
            
        cmd.extend([
            f"{dataset_id}.{table_name}",
            path
        ])
        
        print(f"[BigQuery CLI] Đang thực thi: {' '.join(cmd)}")
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[BigQuery CLI] Nạp thành công {file_name} vào {dataset_id}.{table_name}!")
    except Exception as cli_err:
        print(f"[BigQuery CLI] Gặp lỗi ở chế độ dự phòng bq CLI: {cli_err}")
        if hasattr(cli_err, 'stderr') and cli_err.stderr:
            print(f"[BigQuery CLI] Chi tiết lỗi: {cli_err.stderr}")

try:
    conn = get_connection()
    cursor = conn.cursor()
    
    # Thực hiện import dữ liệu theo đúng trình tự khóa ngoại (foreign key dependencies)
    load_csv_to_table(cursor, conn, "Dim_Hotel.csv", "hotels")
    load_csv_to_table(cursor, conn, "Dim_Location.csv", "hotel_locations")
    load_csv_to_table(cursor, conn, "Dim_Facility.csv", "hotel_facilities")
    load_csv_to_table(cursor, conn, "Dim_NearbyPlaces.csv", "hotel_nearby_places")
    load_csv_to_table(cursor, conn, "Dim_Review.csv", "hotel_reviews")
    load_csv_to_table(cursor, conn, "Dim_RoomType.csv", "room_types")
    load_csv_to_table(cursor, conn, "Fact_Booking.csv", "room_prices")
    
    cursor.close()
    conn.close()
    print("Quá trình đẩy dữ liệu lên cơ sở dữ liệu PostgreSQL hoàn tất thành công!")
    
    # Thực hiện nạp song song lên BigQuery Data Warehouse (OLAP)
    print("\n=== ĐANG TIẾN HÀNH NẠP DỮ LIỆU LÊN BIGQUERY WAREHOUSE ===")
    load_csv_to_bigquery("Dim_Hotel.csv", "hotels")
    load_csv_to_bigquery("Dim_Location.csv", "hotel_locations")
    load_csv_to_bigquery("Dim_Facility.csv", "hotel_facilities")
    load_csv_to_bigquery("Dim_NearbyPlaces.csv", "hotel_nearby_places")
    load_csv_to_bigquery("Dim_Review.csv", "hotel_reviews")
    load_csv_to_bigquery("Dim_RoomType.csv", "room_types")
    load_csv_to_bigquery("Fact_Booking.csv", "room_prices")
    print("=== HOÀN TẤT LUỒNG NẠP DỮ LIỆU ===")

except Exception as e:
    print("Lỗi xảy ra trong quá trình nạp dữ liệu:", e)
