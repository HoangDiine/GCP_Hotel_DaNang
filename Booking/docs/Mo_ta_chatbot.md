# Chatbot AI Du Lịch Đà Nẵng — Mô tả hoạt động

## Tổng quan

Chatbot là trợ lý du lịch AI hỗ trợ tra cứu khách sạn tại Đà Nẵng bằng tiếng Việt. Hệ thống gồm **3 agent chuyên trách** được điều phối bởi **1 root agent**, kết hợp truy vấn SQL thời gian thực và tìm kiếm tài liệu bằng RAG.

---

## Kiến trúc Agent

```
Người dùng
    │
    ▼
┌──────────────────────────┐
│   Root Agent (Điều phối) │  ← gemini-2.5-flash
│   danang_hotel_agent     │
└────┬─────────┬───────────┘
     │         │         │
     ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────────┐
│ Search  │ │ Details │ │ RAG         │
│ Agent   │ │ Agent   │ │ Agent       │
└────┬────┘ └────┬────┘ └──────┬──────┘
     │           │             │
     ▼           ▼             ▼
  MCP Toolbox  MCP Toolbox   RAG Service
  (Cloud Run)  (Cloud Run)   (Cloud Run)
     │           │             │
     ▼           ▼             ▼
  Cloud SQL   Cloud SQL    pgvector + Gemini
  PostgreSQL  PostgreSQL
```

---

## Các Agent

### 1. Root Agent (`danang_hotel_agent`)
- **Vai trò**: Tiếp nhận câu hỏi từ người dùng, phân tích ý định, chuyển tiếp đến agent phù hợp.
- **Quy tắc**:
  - Tìm khách sạn theo giá/vị trí → `hotel_search_agent`
  - Hỏi chi tiết/tiện ích/đánh giá → `hotel_details_agent`
  - Hỏi về tài liệu/báo cáo/quy trình → `rag_document_agent`
  - Câu hỏi ngoài phạm vi → lịch sự từ chối

### 2. Hotel Search Agent (`hotel_search_agent`)
- **Vai trò**: Tìm kiếm và lọc danh sách khách sạn.
- **Tools**:
  - `find-hotels-by-price` — tìm theo giá tối đa + ngày nhận phòng
  - `find-hotels-near-attraction` — tìm theo khoảng cách đến địa danh
- **Dữ liệu**: truy vấn bảng `room_prices`, `hotels`, `hotel_nearby_places`, `hotel_locations`

### 3. Hotel Details Agent (`hotel_details_agent`)
- **Vai trò**: Cung cấp thông tin chi tiết về khách sạn cụ thể.
- **Tools**:
  - `get-hotel-details` — mô tả, hạng sao, giờ check-in/out
  - `get-hotel-facilities` — danh sách tiện ích
  - `get-hotel-reviews` — điểm đánh giá theo tiêu chí
- **Dữ liệu**: truy vấn bảng `hotels`, `hotel_facilities`, `hotel_reviews`

### 4. RAG Document Agent (`rag_document_agent`)
- **Vai trò**: Trả lời câu hỏi dựa trên tài liệu đã nạp (PDF, Markdown).
- **Cách hoạt động**:
  1. Gọi RAG service qua HTTP (`/chat`)
  2. RAG service embed câu hỏi bằng Vertex AI
  3. Tìm top-k đoạn văn liên quan trong pgvector
  4. Gemini tổng hợp câu trả lời kèm nguồn tài liệu

---

## Luồng xử lý

### Ví dụ 1: Tìm khách sạn theo giá
```
Người dùng: "Tìm khách sạn dưới 1 triệu ngày 2026-07-10"
    → Root Agent nhận diện: tìm theo giá
    → Chuyển cho Search Agent
    → Gọi tool find-hotels-by-price(max_price=1000000, checkin_date="2026-07-10")
    → MCP Toolbox truy vấn Cloud SQL
    → Trả về danh sách: tên, loại phòng, giá, ngày
```

### Ví dụ 2: Hỏi tiện ích khách sạn
```
Người dùng: "Khách sạn Muong Thanh có hồ bơi không?"
    → Root Agent nhận diện: hỏi chi tiết
    → Chuyển cho Details Agent
    → Gọi tool get-hotel-facilities(hotel_name_query="Muong Thanh")
    → Trả về danh sách tiện ích, nêu rõ có/không có hồ bơi
```

### Ví dụ 3: Hỏi tài liệu
```
Người dùng: "Kiến trúc GCP gồm những thành phần nào?"
    → Root Agent nhận diện: câu hỏi tài liệu
    → Chuyển cho RAG Agent
    → Gọi RAG service /chat
    → Tìm đoạn văn liên quan trong tài liệu đã nạp
    → Trả lời kèm tên nguồn tài liệu
```

---

## Hạ tầng GCP

| Thành phần | Dịch vụ GCP | Ghi chú |
|---|---|---|
| Agent chatbot | Cloud Run (`danang-agent-service`) | ADK api_server, auto-scale |
| MCP Toolbox | Cloud Run (`mcp-toolbox`) | Cầu nối agent ↔ Cloud SQL |
| RAG service | Cloud Run (`danang-rag-service`) | FastAPI + pgvector |
| Database | Cloud SQL PostgreSQL | 542 khách sạn, 7 bảng |
| AI Model | Vertex AI Gemini 2.5 Flash | Hiểu ngôn ngữ + sinh câu trả lời |
| Embedding | Vertex AI text-multilingual-embedding-002 | Cho RAG module |
| Cấu hình | Secret Manager | Lưu tools.yaml, DB credentials |

---

## Quy tắc chung của chatbot

- Luôn trả lời bằng **tiếng Việt** tự nhiên
- **Không bịa** thông tin ngoài dữ liệu
- **Hỏi lại** nếu thiếu thông tin (ngày, giá, tên khách sạn)
- Trình bày kết quả dạng **danh sách có cấu trúc**
- Từ chối lịch sự nếu câu hỏi ngoài phạm vi
