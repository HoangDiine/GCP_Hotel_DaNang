"""FastAPI RAG service cho chatbot Đà Nẵng."""
import os
import sys

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

import db
import rag_chain

app = FastAPI(title="Đà Nẵng RAG Service", version="1.0")


# --- Models ---
class ChatRequest(BaseModel):
    question: str
    top_k: int = 5


class IngestTextRequest(BaseModel):
    text: str
    source: str
    metadata: dict | None = None


# --- Startup ---
@app.on_event("startup")
def startup():
    """Đảm bảo bảng rag_documents tồn tại khi service khởi động."""
    try:
        db.ensure_table()
        print("Bảng rag_documents đã sẵn sàng.")
    except Exception as e:
        print(f"Cảnh báo: Không thể tạo bảng rag_documents: {e}", file=sys.stderr)


# --- Endpoints ---
@app.get("/health")
def health():
    """Kiểm tra trạng thái service."""
    return {"status": "ok", "service": "danang-rag-service"}


@app.post("/chat")
def chat(req: ChatRequest):
    """Trả lời câu hỏi dựa trên tài liệu đã nạp."""
    try:
        result = rag_chain.query(req.question, top_k=req.top_k)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/text")
def ingest_text(req: IngestTextRequest):
    """Nạp đoạn text vào vector store."""
    try:
        count = rag_chain.ingest_text(req.text, source=req.source, metadata=req.metadata)
        return {"status": "ok", "chunks_ingested": count, "source": req.source}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    """Nạp file (txt, md, pdf) vào vector store."""
    filename = file.filename or "unknown"
    content_bytes = await file.read()

    if filename.lower().endswith(".pdf"):
        # ponytail: dùng pypdf trực tiếp, không cần langchain document loader
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content_bytes))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            raise HTTPException(status_code=500, detail="pypdf chưa được cài. Cần: pip install pypdf")
    else:
        text = content_bytes.decode("utf-8", errors="replace")

    if not text.strip():
        raise HTTPException(status_code=400, detail="File rỗng hoặc không đọc được nội dung.")

    count = rag_chain.ingest_text(text, source=filename)
    return {"status": "ok", "chunks_ingested": count, "source": filename}


@app.get("/admin")
def admin():
    """Thống kê tài liệu đã nạp."""
    try:
        stats = db.count_documents()
        sources = db.list_sources()
        return {"stats": stats, "sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
