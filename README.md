# Medical AI Assistant (RAG) - Qdrant Cloud

Hệ thống trợ lý y tế dựa trên RAG (Retrieval-Augmented Generation) với dữ liệu ViHealthQA. README này tập trung vào cấu hình và chạy hệ thống với Qdrant Cloud.

## Tính năng chính
- Tra cứu y khoa bằng Hybrid Search (Vector + BM25)
- Reranking tài liệu để tăng độ chính xác
- Safety check dựa trên hồ sơ sức khỏe
- Trích dẫn nguồn tài liệu trong câu trả lời

## Yêu cầu hệ thống
- Python 3.9+
- Node.js 16+
- Google Gemini API Key
- Tài khoản Qdrant Cloud + API Key

## Quick Start (Qdrant Cloud)

### 1) Cài đặt Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Cấu hình biến môi trường
Tạo file `backend/.env` với nội dung:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
QDRANT_MODE=cloud
QDRANT_CLOUD_URL=https://<cluster-id>.<region>.aws.cloud.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key_here
QDRANT_COLLECTION=vnhealthqa
```

### 3) Kiểm tra kết nối Qdrant Cloud (khuyến nghị)
```bash
python backend/scripts/test_connection.py
```

### 4) Chuẩn bị dữ liệu
- Đặt file dữ liệu tại `data/train_clean.csv`
- File CSV/JSON cần có tối thiểu cột `question` và `answer`
- Có thể thêm cột `context` và `id` (không bắt buộc)

### 5) Index dữ liệu lên Qdrant Cloud
```bash
python backend/scripts/index_data.py
```

### 6) Chạy Backend
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend chạy tại `http://localhost:8000`

### 7) Chạy Frontend
```bash
cd frontend
npm install
npm start
```

Frontend chạy tại `http://localhost:3000`  
Nếu backend không chạy ở `localhost:8000`, hãy set `REACT_APP_API_URL` trước khi chạy.

## Luồng xử lý hiện tại
1. Gemini thực hiện bước gate nhanh để xác định câu hỏi có liên quan y tế hay không.
2. Nếu KHÔNG y tế: trả về câu trả lời ngắn (chào hỏi hoặc từ chối lịch sự) và dừng luồng.
3. Nếu y tế: chạy Hybrid Search trên Qdrant (Vector + BM25).
4. Reranker chọn ra Top-K tài liệu liên quan nhất.
5. Gemini tạo câu trả lời chi tiết có trích dẫn.
6. Safety check theo hồ sơ sức khỏe (nếu có).
7. Trả response về frontend.

## Sơ đồ luồng xử lý end-to-end
```
User (ReactJS)
   |
   | 1) POST /api/chat
   v
FastAPI Backend
   |
   | 2) Gate: Gemini kiểm tra y tế?
   |    |-- KHÔNG y tế -> trả câu trả lời ngắn -> Frontend
   |    |
   |    |-- Y tế -> tiếp tục
   v
Hybrid Search
   |
   | 3) Qdrant Vector Search + (BM25 nếu đã init)
   v
Reranker
   |
   | 4) Chọn Top-K tài liệu
   v
Gemini Generation
   |
   | 5) Tạo câu trả lời có trích dẫn
   v
Safety Check (nếu có hồ sơ)
   |
   | 6) Thêm cảnh báo nếu cần
   v
Response -> Frontend (ReactJS)
```

## Biến môi trường quan trọng
- `GEMINI_API_KEY`: API key cho Gemini
- `GEMINI_MODEL`: Model Gemini sử dụng
- `QDRANT_MODE`: `cloud` hoặc `local`
- `QDRANT_CLOUD_URL`: URL cluster Qdrant Cloud
- `QDRANT_API_KEY`: API key của Qdrant Cloud
- `QDRANT_COLLECTION`: Tên collection

## Troubleshooting nhanh
- Lỗi 401/403 từ Qdrant Cloud: kiểm tra `QDRANT_API_KEY` và `QDRANT_CLOUD_URL`
- `BM25 not initialized`: chạy `python backend/scripts/index_data.py`
- Frontend timeout: tăng `timeout` trong `frontend/src/services/api.js`

## Local Qdrant (tuỳ chọn)
Nếu muốn chạy local thay vì cloud:
1. Set `QDRANT_MODE=local`, `QDRANT_HOST=localhost`, `QDRANT_PORT=6333` trong `.env`
2. Chạy Qdrant bằng Docker:
```bash
docker run -d -p 6333:6333 qdrant/qdrant
```

## License
MIT
