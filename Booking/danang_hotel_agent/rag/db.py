"""Kết nối Cloud SQL PostgreSQL và quản lý bảng rag_documents."""
import os
import psycopg2
from psycopg2.extras import execute_values

# ponytail: Cloud Run kết nối Cloud SQL qua Unix socket, không qua TCP public IP.
# Khi CLOUD_SQL_CONNECTION_NAME được set → dùng Unix socket.
# Khi không set (local dev) → dùng TCP trực tiếp.
CLOUD_SQL_CONNECTION_NAME = os.environ.get("CLOUD_SQL_CONNECTION_NAME", "")
DB_HOST = os.environ.get("DB_HOST", "136.110.50.188")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

VECTOR_TABLE = os.environ.get("VECTOR_TABLE", "rag_documents")

INIT_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS {VECTOR_TABLE} (
    id TEXT PRIMARY KEY,
    source TEXT,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    if CLOUD_SQL_CONNECTION_NAME:
        # Cloud Run: kết nối qua Unix socket mount bởi --add-cloudsql-instances
        socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
        return psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            host=f"{socket_dir}/{CLOUD_SQL_CONNECTION_NAME}",
        )
    else:
        # Local dev: kết nối TCP trực tiếp
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME,
            user=DB_USER, password=DB_PASSWORD,
        )


def ensure_table():
    """Tạo extension pgvector và bảng rag_documents nếu chưa tồn tại."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(INIT_SQL)
        conn.commit()
    finally:
        conn.close()


def insert_chunks(rows: list[tuple]):
    """Insert danh sách (id, source, content, embedding_list, metadata_json).

    embedding_list là list[float] 768 chiều, sẽ được cast sang VECTOR.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""INSERT INTO {VECTOR_TABLE} (id, source, content, embedding, metadata)
                    VALUES %s ON CONFLICT (id) DO UPDATE
                    SET content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata""",
                rows,
                template="(%s, %s, %s, %s::vector, %s::jsonb)",
                page_size=100,
            )
        conn.commit()
    finally:
        conn.close()


def search_similar(embedding: list[float], top_k: int = 5) -> list[dict]:
    """Tìm top-k chunks gần nhất với embedding query."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT id, source, content, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                    FROM {VECTOR_TABLE}
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s""",
                [str(embedding), str(embedding), top_k],
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def count_documents() -> dict:
    """Đếm số documents và sources."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT source) FROM {VECTOR_TABLE}")
            total, sources = cur.fetchone()
            return {"total_chunks": total, "unique_sources": sources}
    finally:
        conn.close()


def list_sources() -> list[str]:
    """Liệt kê tất cả sources đã ingest."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT DISTINCT source FROM {VECTOR_TABLE} ORDER BY source")
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
