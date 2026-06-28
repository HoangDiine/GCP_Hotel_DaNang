"""Script CLI để ingest tài liệu trong Booking/docs/ vào RAG service."""
import os
import sys
import requests

RAG_SERVICE_URL = os.environ.get("RAG_SERVICE_URL", "http://localhost:8080")
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")

# Danh sách file cần ingest theo kế hoạch
TARGET_FILES = [
    "NHÓM 4 - BÁO CÁO TIẾN ĐỘ 2.pdf",
    "Walkthrough.md",
    "Ke_hoach_trien_khai_chatbot_GCP.md",
]


def ingest_file(filepath: str):
    """Upload file lên RAG service endpoint /ingest/file."""
    filename = os.path.basename(filepath)
    print(f"Đang ingest: {filename} ...")

    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{RAG_SERVICE_URL}/ingest/file",
            files={"file": (filename, f)},
            timeout=120,
        )

    if resp.status_code == 200:
        data = resp.json()
        print(f"  ✓ {data.get('chunks_ingested', '?')} chunks đã nạp từ {filename}")
    else:
        print(f"  ✗ Lỗi {resp.status_code}: {resp.text}", file=sys.stderr)


def main():
    # Kiểm tra health
    try:
        r = requests.get(f"{RAG_SERVICE_URL}/health", timeout=5)
        r.raise_for_status()
        print(f"RAG service OK tại {RAG_SERVICE_URL}\n")
    except Exception as e:
        print(f"Không thể kết nối RAG service tại {RAG_SERVICE_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    for fname in TARGET_FILES:
        path = os.path.join(DOCS_DIR, fname)
        if os.path.exists(path):
            ingest_file(path)
        else:
            print(f"  ⚠ Không tìm thấy: {path}")

    # Kiểm tra kết quả
    print("\n--- Thống kê sau ingest ---")
    resp = requests.get(f"{RAG_SERVICE_URL}/admin", timeout=10)
    if resp.ok:
        data = resp.json()
        print(f"Tổng chunks: {data['stats']['total_chunks']}")
        print(f"Nguồn tài liệu: {data['stats']['unique_sources']}")
        for s in data.get("sources", []):
            print(f"  - {s}")


if __name__ == "__main__":
    main()
