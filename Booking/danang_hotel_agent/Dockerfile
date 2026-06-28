FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

# Cloud Run needs 0.0.0.0 (not 127.0.0.1) and reads PORT env var
CMD ["sh", "-c", "adk api_server --host 0.0.0.0 --port ${PORT:-8080} --auto_create_session --with_ui ."]

