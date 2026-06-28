"""RAG chain: chunking, embedding, retrieval, answer generation."""
import hashlib
import json
import os
from typing import Optional

import vertexai
from vertexai.language_models import TextEmbeddingModel

import db

# Config
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "200"))
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-multilingual-embedding-002")
GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "gemini-2.5-flash")
TOP_K = int(os.environ.get("TOP_K", "5"))

# ponytail: init vertexai once at module load
_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "capstone-project-2-group-4")
_location = os.environ.get("GOOGLE_CLOUD_LOCATION", "asia-southeast1")
vertexai.init(project=_project, location=_location)


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Tách text thành chunks với overlap. Đơn giản, không cần langchain."""
    # ponytail: stdlib splitter thay vì kéo cả langchain chỉ để chunk text
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """Tạo embeddings cho danh sách texts bằng Vertex AI."""
    model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL)
    # ponytail: batch size nhỏ (5) vì embedding model giới hạn 20k tokens/request.
    # Với chunk_size=1000 chars, 5 chunks ≈ 5k-10k tokens, an toàn.
    all_embeddings = []
    for i in range(0, len(texts), 5):
        batch = texts[i:i + 5]
        embeddings = model.get_embeddings(batch)
        all_embeddings.extend([e.values for e in embeddings])
    return all_embeddings


def _make_chunk_id(source: str, idx: int) -> str:
    """Tạo deterministic ID cho chunk."""
    return hashlib.sha256(f"{source}::{idx}".encode()).hexdigest()[:16]


def ingest_text(text: str, source: str, metadata: Optional[dict] = None) -> int:
    """Chunk text, embed, và lưu vào pgvector. Trả về số chunks đã lưu."""
    chunks = _chunk_text(text)
    if not chunks:
        return 0

    embeddings = _embed_texts(chunks)
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    rows = [
        (
            _make_chunk_id(source, i),
            source,
            chunk,
            str(emb),  # psycopg2 cần string cho vector type
            meta_json,
        )
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]

    db.insert_chunks(rows)
    return len(rows)


def query(question: str, top_k: int = TOP_K) -> dict:
    """Truy vấn RAG: embed question → search pgvector → generate answer."""
    # Embed câu hỏi
    q_embedding = _embed_texts([question])[0]

    # Retrieve chunks
    results = db.search_similar(q_embedding, top_k=top_k)

    if not results:
        return {
            "answer": "Không tìm thấy thông tin liên quan trong tài liệu đã nạp.",
            "sources": [],
            "chunks_used": 0,
        }

    # Build context
    context_parts = []
    sources_used = set()
    for r in results:
        context_parts.append(f"[Nguồn: {r['source']}]\n{r['content']}")
        sources_used.add(r["source"])

    context = "\n\n---\n\n".join(context_parts)

    # Generate answer bằng Vertex AI Gemini
    from vertexai.generative_models import GenerativeModel

    model = GenerativeModel(GENERATION_MODEL)
    prompt = (
        "Bạn là trợ lý AI chuyên trả lời câu hỏi dựa trên tài liệu được cung cấp.\n"
        "Hãy trả lời bằng tiếng Việt, chính xác dựa trên nội dung bên dưới.\n"
        "Nếu thông tin không có trong tài liệu, nói rõ 'Không tìm thấy trong tài liệu'.\n"
        "Trích dẫn tên nguồn tài liệu khi trả lời.\n\n"
        f"TÀI LIỆU THAM KHẢO:\n{context}\n\n"
        f"CÂU HỎI: {question}\n\n"
        "TRẢ LỜI:"
    )

    response = model.generate_content(prompt)
    answer = response.text if response.text else "Không thể tạo câu trả lời."

    return {
        "answer": answer,
        "sources": sorted(sources_used),
        "chunks_used": len(results),
    }
