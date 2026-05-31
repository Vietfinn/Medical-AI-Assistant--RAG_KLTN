# Hệ Thống Trợ Lý Y Khoa Thông Minh AIMCare (AIMCare Medical AI Assistant)

**AIMCare** là hệ thống Trợ lý Y khoa Thông minh và là một giải pháp y tế số toàn diện được xây dựng trên kiến trúc đa tác nhân dị biến (Heterogeneous Multi-Agent) kết hợp với công nghệ truy xuất tăng cường sinh (Retrieval-Augmented Generation - RAG). Hệ thống AIMCare được thiết kế nhằm cung cấp các phản hồi y khoa chính xác, đảm bảo mức độ an toàn lâm sàng (Clinical Safety) cao dựa trên hồ sơ sức khỏe cá nhân của bệnh nhân, đồng thời hỗ trợ giao diện quản trị an toàn thông tin y tế và giám sát rủi ro theo thời gian thực.

---

## 1. Tổng Quan Kiến Trúc Hệ Thống (System Architecture)

Hệ thống được chia thành ba tầng kiến trúc độc lập nhằm đảm bảo khả năng mở rộng, tính chịu tải cao và phản hồi nhanh:

### Tầng Giao Diện Người Dùng (Frontend Layer)
*   **React.js:** Thư viện cốt lõi để xây dựng giao diện ứng dụng đơn trang (Single Page Application).
*   **Trải nghiệm tương tác thời gian thực:** Giao diện hỗ trợ nhận diện phản hồi dạng dòng chảy (SSE Streaming) từ mô hình ngôn ngữ lớn, cuộn trang tự động và tích hợp các công cụ hỗ trợ người dùng cuối.
*   **Clerk Authentication:** Giải pháp xác thực người dùng đồng bộ (Single Sign-On qua Google, Github), hỗ trợ phân quyền vai trò người dùng (User) và quản trị viên (Admin) thông qua Clerk JWT Claims.
*   **Vanilla CSS:** Thiết kế giao diện hiện đại sử dụng Glassmorphism, hỗ trợ chế độ giao diện sáng/tối (Light/Dark Mode) và tối ưu hóa phản hồi giao diện động.

### Tầng Nghiệp Vụ & Trí Tuệ Nhân Tạo (Backend Layer)
*   **FastAPI:** Framework hiệu năng cao hỗ trợ xử lý bất đồng bộ (Asynchronous) trong Python. Sử dụng Lifespan Context Manager để quản lý vòng đời ứng dụng, khởi tạo và giải phóng tài nguyên một cách tối ưu.
*   **Multi-Agent Pipeline:** Quy trình xử lý câu hỏi y khoa chia nhỏ thành các vai trò chuyên biệt:
    *   **Triage Agent:** Phân loại ý định người dùng (Medical vs. Non-Medical) và kiểm tra tính an toàn sơ bộ.
    *   **Clinical RAG Agent (Gemini 2.5 Flash):** Tác nhân chính thực hiện truy xuất tài liệu chuyên môn và tổng hợp câu trả lời lâm sàng.
    *   **Safety Guard Agent:** Tác nhân hậu kiểm chuyên chéo hồ sơ bệnh án cá nhân (dị ứng, bệnh lý nền) với câu trả lời dự thảo để phát hiện chống chỉ định y tế.
*   **Smart Suggestion Engine:** Engine gợi ý hoạt chất dị ứng, bệnh mạn tính và thuốc thương mại chạy trực tiếp trên bộ nhớ RAM (In-Memory) để đảm bảo tốc độ phản hồi tối ưu dưới 2ms.

### Tầng Lưu Trữ & Cơ Sở Dữ Liệu (Storage Layer)
*   **Qdrant Cloud:** Vector Database lưu trữ và truy xuất các vector nhúng (Embeddings) của bộ cơ sở dữ liệu tri thức y khoa. Sử dụng phương pháp tìm kiếm hỗn hợp (Hybrid Search) kết hợp Dense Vector (`vietnamese-bi-encoder`) và Sparse Vector (`fastembed` BM25), tích hợp thuật toán xếp hạng hợp nhất Reciprocal Rank Fusion (RRF).
*   **MongoDB Atlas:** Cơ sở dữ liệu phi quan hệ (NoSQL) lưu trữ lịch sử hội thoại (Chat History), phiên làm việc (Sessions), thông tin hồ sơ sức khỏe người dùng (Health Profiles), cấu hình hệ thống động (System Settings), phản hồi chất lượng (Feedbacks) và nhật ký vi phạm an toàn thông tin (Unsafe Logs).

---

## 2. Quy Trình Xử Lý Đa Tác Nhân (Multi-Agent Processing Pipeline)

Quy trình xử lý một câu hỏi y tế được thực hiện qua bốn giai đoạn nghiêm ngặt:

```mermaid
sequenceDiagram
    participant User as Người dùng
    participant Auth as Auth Middleware
    participant Mongo as MongoDB Atlas
    participant Triage as Triage Agent (Llama 3.3)
    participant Qdrant as Qdrant Vector DB
    participant Cohere as Cohere Reranker
    participant Gemini as Clinical Agent (Gemini)
    participant Safety as Safety Agent (Llama 3.3)

    Người dùng->>Auth: Gửi câu hỏi + Token xác thực + Session ID
    Auth->>Mongo: Kiểm tra trạng thái cấm (Ban) & Tải hồ sơ bệnh án
    Auth-->>Người dùng: Trả về 403 Forbidden (Nếu người dùng bị cấm)
    
    Triage->>Triage: Quét từ khóa cấm trong cấu hình hệ thống (Blacklist)
    alt Khớp từ khóa cấm
        Triage-->>Người dùng: Phản hồi từ chối y tế mặc định (Early Exit)
    else Hợp lệ
        Triage->>Triage: Phân loại ý định (Medical vs. Non-Medical)
        alt Không liên quan y tế (Non-Medical)
            Triage-->>Người dùng: Từ chối lịch sự & Hướng dẫn sử dụng đúng mục đích
        else Liên quan y tế (Medical)
            Triage->>Qdrant: Thực hiện tìm kiếm Hybrid Search
            Qdrant-->>Triage: Trả về Top 30 tài liệu thô
            Triage->>Cohere: Tiến hành Rerank (Tái xếp hạng Cross-Encoder)
            Cohere-->>Triage: Chọn lọc Top N tài liệu liên quan nhất
            Triage->>Gemini: Đưa tài liệu, lịch sử hội thoại & hồ sơ sức khỏe vào Prompt
            Gemini-->>Triage: Trả về dự thảo câu trả lời (Draft Response) + Nguồn trích dẫn
            Triage->>Safety: Đối chiếu dự thảo câu trả lời với bệnh án dị ứng của bệnh nhân
            alt Phát hiện cảnh báo chống chỉ định
                Safety-->>Người dùng: Trả về câu trả lời kèm nhãn cảnh báo đỏ (Warnings)
            else Hoàn toàn an toàn
                Safety-->>Người dùng: Trả về câu trả lời chuẩn y khoa lâm sàng
            end
            Safety->>Mongo: Lưu toàn bộ phiên chat & thông số hiệu năng RAG vào CSDL
        end
    end
```

---

## 3. Công Cụ Gợi Ý Autocomplete & RAM Cache (Smart Suggestion Engine)

Để tối ưu hóa trải nghiệm điền thông tin bệnh án và giảm thiểu độ trễ, hệ thống ứng dụng công cụ gợi ý chạy trên bộ nhớ RAM (In-Memory Cache):

*   **Tải dữ liệu thông minh:** Khi khởi động hệ thống (`lifespan startup`), toàn bộ dữ liệu danh mục bệnh mạn tính ICD-10, danh mục hoạt chất master và danh mục thuốc thương mại được nạp thẳng từ MongoDB lên RAM.
*   **Chuẩn hóa trước (Pre-Normalization):** Các khóa tìm kiếm không dấu (ASCII) được tạo sẵn tại RAM để tránh việc chạy hàm chuẩn hóa unicode động `unidecode` O(N) trên mỗi ký tự người dùng nhập vào.
*   **Chiến lược so khớp mờ (Fuzzy Matching):**
    *   *Bệnh mạn tính:* Sử dụng chiến lược Prefix-first (ưu tiên từ bắt đầu) kết hợp Fuzzy match dự phòng bằng `RapidFuzz` để đảm bảo độ chính xác.
    *   *Dị ứng hoạt chất:* Tự động hiển thị dạng danh sách cuộn A-Z khi chưa có ký tự nhập vào, và chuyển sang so khớp mờ khi có ký tự đầu vào.
    *   *Thuốc thương mại:* Sử dụng thuật toán `fuzz.WRatio` cho phép tìm kiếm bất chấp sai sót chính tả thông thường của người dùng cuối.
*   **Tối ưu hóa nhóm thuốc:** Danh sách nhóm thuốc độc nhất được tính toán và cache tĩnh dạng `O(1)` giúp phản hồi tức thì cho giao diện bộ lọc danh mục.

---

## 4. Cơ Chế Kháng Lỗi Logic & Đồng Bộ Dữ Liệu (Safety & Consistency Implementations)

Hệ thống đã triển khai thành công các giải pháp kỹ thuật để khắc phục triệt để các lỗi bất đồng bộ nghiêm trọng giữa môi trường User và Admin:

*   **Kháng lỗi mất bệnh án (PATCH Partial Update):** API cập nhật hồ sơ sức khỏe `/api/profile` được tách riêng luồng POST (ghi đè toàn bộ) và PATCH (cập nhật vi phân). Lệnh PATCH sử dụng toán tử `$set` của MongoDB kết hợp cấu trúc Dot-notation (Ví dụ: `health_profile.weight`), ngăn ngừa việc cập nhật một trường đơn lẻ làm xóa sạch dữ liệu bệnh nền, dị ứng đã điền trước đó.
*   **Cách ly trạng thái cấm (Banned Isolation):** Giải quyết tình trạng tài khoản bị cấm (bị Ban) biến mất khỏi giao diện quản lý của Admin khi thực hiện thao tác xóa logs vi phạm an toàn. Danh sách tài khoản nguy hiểm (`/api/admin/unsafe-users`) tự động thực hiện truy vấn hợp nhất (Outer-Join) trạng thái cờ `is_banned` từ collection `users`, độc lập hoàn toàn với collection `unsafe_logs`.
*   **Đồng bộ phía Client (On-Mount Fetch):** Khi ứng dụng Frontend khởi chạy, hệ thống tự động kéo thông tin hồ sơ sức khỏe thực tế từ MongoDB xuống bộ nhớ tạm `localStorage` để đồng bộ trạng thái, ngăn chặn việc đẩy ngược đối tượng trống lên server khi mở modal trên thiết bị mới.

---

## 5. Hệ Thống Giám Sát Lỗi (Sentry) & Nhật Ký Có Cấu Trúc (Structured Logging)

Nhằm đảm bảo tính ổn định tối đa khi vận hành thực tế (Production), hệ thống tích hợp giải pháp giám sát lỗi chủ động và ghi log có cấu trúc:

*   **Sentry Error Tracking (Backend & Frontend):** 
    *   *Giám sát thời gian thực:* Phát hiện và bắt toàn bộ các ngoại lệ (Exceptions/Crashes) chưa được xử lý ở cả API Backend (FastAPI) và mã nguồn phía Client (React). Tự động gom nhóm lỗi và gửi thông báo cảnh báo tức thì tới email của Admin.
    *   *Bảo vệ dữ liệu y tế nhạy cảm (PII Redaction):* Thiết lập hook đệ quy `before_send` ở backend và `beforeSend` ở frontend để tự động lọc và thay thế toàn bộ thông tin bệnh án nhạy cảm (như nội dung chat, tên bệnh nền, thuốc dị ứng, email...) thành `[REDACTED]` trước khi gửi về Sentry, đảm bảo an toàn thông tin y khoa tuyệt đối.
    *   *Sentry ErrorBoundary:* Bọc ứng dụng React để ngăn lỗi component làm sập giao diện (trắng màn hình), hiển thị thông báo thay thế thân thiện cho người dùng.
*   **Structured JSON Logging (Production logs):**
    *   Khi chạy môi trường Production (`LOG_FORMAT=json`), hệ thống backend tự động chuyển đổi toàn bộ log thô dạng text sang dạng JSON có cấu trúc (gồm các trường: `timestamp`, `level`, `module`, `message`).
    *   Log JSON có cấu trúc giúp các hệ thống thu thập log tập trung (như Hugging Face Logs) dễ dàng lọc, truy vấn và tìm kiếm sự cố nhanh chóng.

---

## 6. Hướng Dẫn Cài Đặt & Triển Khai Hệ Thống (Installation & Deployment)

### Yêu Cầu Hệ Thống
*   Python 3.10 trở lên
*   Node.js 18 trở lên (để build Frontend)
*   Tài khoản và API keys hoạt động: Gemini, Groq, Cohere, Clerk.

### 1. Cấu hình biến môi trường (`.env` cho Backend)
Tạo file `.env` tại thư mục `backend` với cấu hình mẫu sau:

```env
# AI Models Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY1=your_groq_key_1_here
GROQ_API_KEY2=your_groq_key_2_here
GROQ_MODEL=llama-3.3-70b-versatile

# Cohere Reranker API
COHERE_API_KEY=your_cohere_key_here
RERANKER_MODEL=rerank-v4.0-pro

# Qdrant Vector Database
QDRANT_MODE=cloud
QDRANT_CLOUD_URL=https://your-qdrant-cluster-url.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION=vnhealthqa

# MongoDB Atlas Url
MONGODB_URL=mongodb+srv://admin:password@cluster.mongodb.net/?retryWrites=true&w=majority

# Authentication (Clerk JWKS)
CLERK_JWKS_URL=https://your-clerk-domain.clerk.accounts.dev/.well-known/jwks.json
CLERK_ISSUER=https://your-clerk-domain.clerk.accounts.dev

# SMTP Email Settings
GMAIL_SENDER=your-system-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/your-script-id/exec

# Sentry & Observability Configuration
SENTRY_DSN_BACKEND=https://your-sentry-dsn-for-backend@ingest.sentry.io/project-id
LOG_FORMAT=json  # "json" cho production, "text" cho dev
```

### 2. Thiết lập Môi trường Backend & Chạy cơ sở dữ liệu
```bash
# Di chuyển vào thư mục backend
cd backend

# Khởi tạo môi trường ảo Python
python -m venv venv
source venv/bin/activate  # Trên Windows dùng: venv\Scripts\activate

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt

# Tạo chỉ mục và đẩy dữ liệu Vector vào Qdrant Cloud
python scripts/index_data.py

# Seed dữ liệu gợi ý ICD-10 và Thuốc thương mại vào MongoDB Atlas
python -m scripts.seed_clinical_conditions
python -m scripts.process_medications

# Khởi chạy máy chủ phát triển
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Thiết lập Frontend
Tạo file `.env` tại thư mục `frontend` và định cấu hình API:
```env
REACT_APP_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_publishable_key_here
REACT_APP_API_URL=http://localhost:8000

# Sentry Integration
REACT_APP_SENTRY_DSN=https://your-sentry-dsn-for-frontend@ingest.sentry.io/project-id
```
Khởi chạy Frontend cục bộ:
```bash
cd frontend
npm install
npm start
```

### 4. Triển khai sản phẩm (Cloud Deployment)
*   **Backend (Hugging Face Spaces):** Sử dụng cấu trúc Space chạy Docker SDK. Đảm bảo cấu hình các biến môi trường trong mục "Repository Secrets" tại HF Space Settings.
*   **Frontend (Vercel):** Đẩy mã nguồn Frontend lên GitHub, liên kết dự án với Vercel, cấu hình thư mục gốc (Root directory) là `frontend` và thiết lập các biến môi trường tương tự như local.

---

## 7. Kịch Bản Kiểm Thử & Kiểm Định (Testing & Verification)

Hệ thống cung cấp bộ kịch bản kiểm thử tích hợp tự động toàn diện được thiết kế để xác minh sự đồng bộ giữa hệ thống đa tác nhân và cơ sở dữ liệu:

*   **Chạy toàn bộ ca kiểm thử:**
    ```bash
    python backend/scratch/system_comprehensive_test.py
    ```
*   **Hạng mục kiểm định tự động:**
    1.  *Health Check:* Đảm bảo tất cả các cổng kết nối API và Vector DB hoạt động bình thường.
    2.  *Profile Sync & Overwrite:* Xác minh cơ chế PATCH và bảo toàn hồ sơ bệnh án cá nhân.
    3.  *Dictionary CRUD:* Xác thực việc cập nhật cơ sở dữ liệu bệnh lý ICD-10 và trigger làm mới bộ nhớ đệm.
    4.  *Chat Safety & Triage:* Kiểm chứng khả năng phân loại và chặn đứng các truy vấn vi phạm quy tắc an toàn thông tin hoặc ngoài luồng y học.
    5.  *Deadlock Prevention:* Kiểm tra việc ban/unban người dùng rủi ro hoạt động chính xác ngay cả khi logs vi phạm đã bị xóa sạch hoàn toàn.
