FROM python:3.10-slim
WORKDIR /app

# Sao chép các tệp yêu cầu thư viện từ thư mục etl/
COPY etl/requirements_etl.txt .
RUN pip install --no-cache-dir -r requirements_etl.txt

# Sao chép mã nguồn ETL từ thư mục etl/
COPY etl/preprocess.py .
COPY etl/load_to_cloud_sql.py .
COPY etl/run_etl.py .

# Sao chép tệp dữ liệu CSV từ thư mục data/
COPY data/raw_hotels_full.csv .

CMD ["python", "run_etl.py"]

