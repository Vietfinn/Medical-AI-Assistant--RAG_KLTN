# 🚀 Quick Start Guide

Hướng dẫn khởi động nhanh Hệ thống Trợ lý Y tế AI trong 10 phút.

## Yêu cầu Hệ thống

- **Python**: 3.9 hoặc cao hơn
- **Node.js**: 16 hoặc cao hơn
- **Docker**: Để chạy Qdrant (hoặc cài Qdrant trực tiếp)
- **API Key**: Google Gemini API Key (miễn phí tại https://ai.google.dev)

## Bước 1: Cài đặt Qdrant Vector Database

### Sử dụng Docker (Khuyến nghị)

```bash
docker run -d -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage:z \
    qdrant/qdrant
```

### Hoặc cài đặt trực tiếp

Xem hướng dẫn tại: https://qdrant.tech/documentation/quick-start/

## Bước 2: Cài đặt Backend

```bash
cd backend

# Tạo virtual environment
python -m venv venv

# Kích hoạt virtual environment
# Trên Linux/Mac:
source venv/bin/activate
# Trên Windows:
venv\Scripts\activate

# Cài đặt dependencies
pip install -r requirements.txt
```

## Bước 3: Cấu hình API Key

```bash
# Tạo file .env trong thư mục backend
cp .env.example .env

# Chỉnh sửa .env và thêm Gemini API Key
nano .env
```

Nội dung file `.env`:
```env
GEMINI_API_KEY=your_api_key_here
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

## Bước 4: Chuẩn bị Dữ liệu

### Nếu có file ViHealthQA:
```bash
# Đặt file vnhealthqa.json vào thư mục data/
cp path/to/vnhealthqa.json ../data/
```

### Nếu chưa có dữ liệu:
Script sẽ tự động tạo file mẫu để demo

## Bước 5: Index Dữ liệu vào Qdrant

```bash
cd backend
python scripts/index_data.py
```

Quá trình này mất khoảng 5-10 phút tùy vào kích thước dữ liệu.

## Bước 6: Khởi động Backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend sẽ chạy tại: http://localhost:8000

## Bước 7: Cài đặt Frontend

Mở terminal mới:

```bash
cd frontend

# Cài đặt dependencies
npm install
```

## Bước 8: Khởi động Frontend

```bash
npm start
```

Frontend sẽ tự động mở tại: http://localhost:3000

## ✅ Kiểm tra

1. Truy cập http://localhost:3000
2. Nhập hồ sơ sức khỏe (tùy chọn)
3. Thử đặt câu hỏi: "Làm sao chữa đau đầu?"
4. Xem kết quả với citations và warnings!

## 🐛 Troubleshooting

### Backend không kết nối được Qdrant
```bash
# Kiểm tra Qdrant đang chạy
docker ps | grep qdrant

# Hoặc kiểm tra Qdrant Web UI
# Mở http://localhost:6333/dashboard
```

### Lỗi import model
```bash
# Cài lại sentence-transformers
pip install --upgrade sentence-transformers torch
```

### Frontend không kết nối Backend
```bash
# Kiểm tra Backend đang chạy
curl http://localhost:8000/health

# Kết quả mong đợi: {"status":"healthy",...}
```

### Lỗi CORS
- Kiểm tra file `backend/config.py`
- Đảm bảo frontend URL có trong `CORS_ORIGINS`

## 📚 Tài liệu Chi tiết

- [README.md](README.md) - Tổng quan hệ thống
- [docs/API.md](docs/API.md) - API Documentation
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Production Deployment

## 💡 Mẹo

1. **Tăng tốc độ index**: Giảm batch_size trong `index_data.py`
2. **GPU**: Nếu có GPU, PyTorch sẽ tự động sử dụng
3. **Memory**: Nếu thiếu RAM, giảm TOP_K_RETRIEVAL trong `config.py`
4. **Gemini API**: Free tier có giới hạn 60 requests/minute

## 🎉 Hoàn thành!

Bạn đã khởi động thành công Hệ thống Trợ lý Y tế AI. Bắt đầu hỏi các câu hỏi y tế và trải nghiệm sức mạnh của RAG + Context-Aware AI!
