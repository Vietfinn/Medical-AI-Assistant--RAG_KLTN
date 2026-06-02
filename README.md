# Hệ Thống Trợ Lý Y Khoa Thông Minh AIMCare (AIMCare Medical AI Assistant)

**AIMCare** là một hệ thống Trợ lý Y khoa Thông minh và giải pháp y tế số toàn diện được xây dựng trên kiến trúc **Đa tác nhân dị biến (Heterogeneous Multi-Agent)** kết hợp với công nghệ **Truy xuất tăng cường sinh (Retrieval-Augmented Generation - RAG)**. Hệ thống được thiết kế nhằm cung cấp các phản hồi y khoa chính xác, cá nhân hóa và đảm bảo mức độ an toàn lâm sàng (Clinical Safety) cao nhất dựa trên hồ sơ sức khỏe cá nhân của người bệnh, đồng thời cung cấp giao diện quản trị, giám sát rủi ro an toàn thông tin và tinh chỉnh hệ thống thời gian thực cho quản trị viên (Admin).

---

## 1. Tổng Quan Kiến Trúc & Công Nghệ (System Architecture & Tech Stack)

Hệ thống được thiết kế theo mô hình 3 tầng độc lập, tối ưu hiệu năng và khả năng mở rộng:

### 1.1. Tầng Giao Diện Người Dùng (Frontend Layer)
*   **React.js (v18):** Thư viện chính để xây dựng giao diện ứng dụng đơn trang (SPA) phản hồi nhanh.
*   **SSE Streaming:** Nhận phản hồi dạng dòng chảy ký tự trực tiếp từ mô hình ngôn ngữ lớn (LLM) để tối ưu thời gian phản hồi đầu tiên (Time To First Token).
*   **Clerk Authentication:** Hệ thống xác thực đồng bộ (Single Sign-On qua Google, Email), phân quyền vai trò (User/Admin) qua Clerk JWT Claims được xác thực bảo mật tại Backend.
*   **React Portals:** Sử dụng để render các tooltip động và menu tùy chọn nổi (`fixed` positioning) ra ngoài DOM con, giải quyết triệt để lỗi đè lớp hiển thị (`z-index` conflict) trong thanh bên.
*   **Vanilla CSS:** Thiết kế giao diện hiện đại với phong cách Glassmorphism, hỗ trợ tự động đồng bộ chế độ sáng/tối (Light/Dark Mode).

### 1.2. Tầng Nghiệp Vụ & Trí Tuệ Nhân Tạo (Backend Layer)
*   **FastAPI:** Framework Python hiệu năng cực cao, xử lý bất đồng bộ (`async/await`) để tối ưu hóa khả năng chịu tải.
*   **Multi-Agent Orchestrator:** Điều phối luồng xử lý câu hỏi y khoa qua chuỗi tác nhân dị biến chuyên biệt:
    *   **Triage Agent (Llama 3.3-70B via Groq):** Phân loại ý đồ câu hỏi (Medical vs. Non-Medical) và lọc sơ bộ các nội dung không phù hợp hoặc vi phạm an toàn.
    *   **Clinical RAG Agent (Llama 3.3 via Groq):** Tác nhân cốt lõi thực hiện tổng hợp câu trả lời y học chuyên sâu dựa trên các tài liệu y khoa được truy xuất.
    *   **Safety Guard Agent (Llama 3.3-70B via Groq):** Hậu kiểm câu trả lời dự thảo đối chiếu trực tiếp với hồ sơ dị ứng, bệnh lý nền của người dùng để đưa ra cảnh báo an toàn đỏ.
*   **Smart Suggestion Engine (RapidFuzz):** Engine tìm kiếm mờ (Fuzzy Matching) chạy trực tiếp trên bộ nhớ RAM (In-Memory Cache), tối ưu tốc độ gợi ý tự động (Autocomplete) bệnh lý ICD-10 và dược phẩm dưới 2ms.
*   **Sentry SDK & JSON Logging:** Giám sát lỗi thời gian thực và ghi log cấu trúc JSON phục vụ phân tích sự cố tự động.

### 1.3. Tầng Cơ Sở Dữ Liệu & Lưu Trữ (Storage Layer)
*   **Qdrant Cloud (Vector Database):** Lưu trữ vector nhúng của bộ tri thức y khoa. Sử dụng phương pháp **Tìm kiếm hỗn hợp (Hybrid Search)** kết hợp giữa Dense Vector (`vietnamese-bi-encoder`) và Sparse Vector (`fastembed` BM25), chấm điểm bằng thuật toán xếp hạng hợp nhất **Reciprocal Rank Fusion (RRF)** và tinh chỉnh mức độ liên quan bằng **Cohere Reranker (Cross-Encoder)**.
*   **MongoDB Atlas (CSDL NoSQL):** Lưu trữ lịch sử hội thoại (Chat History), phiên chat (Sessions), hồ sơ sức khỏe người dùng (Health Profiles), cấu hình hệ thống động (System Settings), phản hồi đánh giá (Feedbacks), danh mục từ điển y khoa và nhật ký vi phạm an toàn (Unsafe Logs).

---

## 2. Quy Trình Xử Lý Đa Tác Nhân (Multi-Agent RAG Pipeline)

Quy trình xử lý một truy vấn y tế được kiểm định nghiêm ngặt qua 4 giai đoạn độc lập:

```mermaid
sequenceDiagram
    participant User as Người dùng (Client)
    participant Auth as Auth Middleware (FastAPI)
    participant Mongo as MongoDB Atlas
    participant Triage as Triage Agent (Llama 3.3)
    participant Qdrant as Qdrant Vector DB
    participant Cohere as Cohere Reranker
    participant Clinical as Clinical Agent (Llama 3.3)
    participant Safety as Safety Agent (Llama 3.3)

    User->>Auth: Gửi câu hỏi + Token xác thực + Session ID
    Auth->>Mongo: Kiểm tra trạng thái cấm (Ban) & Tải hồ sơ bệnh án
    alt Người dùng bị cấm (Banned)
        Auth-->>User: Trả về lỗi 403 Forbidden
    else Hợp lệ
        Auth->>Triage: Chuyển tiếp câu hỏi của người dùng
        Triage->>Triage: Quét từ khóa cấm trong cấu hình hệ thống (Blacklist)
        alt Khớp từ khóa cấm
            Triage-->>User: Phản hồi từ chối y tế mặc định (Early Exit)
        else Hợp lệ
            Triage->>Triage: Phân loại ý định (Medical vs. Non-Medical)
            alt Không liên quan y tế (Non-Medical)
                Triage-->>User: Từ chối lịch sự & Hướng dẫn sử dụng đúng mục đích
            else Liên quan y tế (Medical)
                Triage->>Qdrant: Truy vấn Hybrid Search (Dense + Sparse Vector)
                Qdrant-->>Triage: Trả về Top 30 tài liệu thô liên quan
                Triage->>Cohere: Tiến hành Rerank (Tái xếp hạng Cross-Encoder)
                Cohere-->>Triage: Chọn lọc Top N tài liệu phù hợp nhất
                Triage->>Clinical: Gửi tài liệu, lịch sử chat & hồ sơ sức khỏe
                Clinical-->>Triage: Trả về dự thảo câu trả lời (Draft Response) + Nguồn trích dẫn
                Triage->>Safety: Đối chiếu dự thảo câu trả lời với hồ sơ bệnh án dị ứng
                alt Phát hiện cảnh báo chống chỉ định y khoa
                    Safety-->>User: Trả về câu trả lời kèm nhãn cảnh báo đỏ (Warnings)
                else Hoàn toàn an toàn
                    Safety-->>User: Trả về câu trả lời chuẩn lâm sàng
                end
                Safety->>Mongo: Lưu phiên chat & thông số hiệu năng RAG vào CSDL
            end
        end
    end
```

---

## 3. Bản Đồ Tính Năng Chi Tiết (Feature Map)

### 3.1. Tính Năng Cho Người Dùng Cuối (User Features)
*   **Trang chủ (Landing Page):** Thiết kế trực quan, hiện đại. Các thẻ gợi ý chủ đề (Suggestion Chips: Tra cứu triệu chứng, Tương tác thuốc, Dinh dưỡng, Sơ cứu) hỗ trợ tương tác hover mượt mà, chống lỗi tràn khung hiển thị.
*   **Xác thực đồng bộ:** Đăng ký, đăng nhập nhanh qua Google hoặc Email thông qua Clerk Auth. Tự động hiển thị màn hình khảo sát hồ sơ sức khỏe (Onboarding) đối với người dùng đăng nhập lần đầu.
*   **Hồ sơ sức khỏe cá nhân (Health Profile):** Cho phép khai báo tuổi, giới tính, tiền sử bệnh mạn tính (mã ICD-10), dị ứng hoạt chất y tế, danh sách thuốc thương mại đang sử dụng. Hỗ trợ autocomplete gợi ý nhanh từ cache RAM dưới 2ms.
*   **Trò chuyện y khoa lâm sàng (Clinical Chat):**
    *   Phản hồi dòng chảy (SSE Streaming) kèm thông số thời gian thực.
    *   **Cảnh báo an toàn (Warnings):** Tự động phát hiện chống chỉ định (ví dụ: khuyên dùng hoạt chất mà người dùng dị ứng, hoặc khuyến nghị thuốc tương tác xấu với bệnh nền) và hiển thị cảnh báo đỏ nổi bật.
    *   **Nguồn trích dẫn (Citations):** Hiển thị chi tiết tài liệu y văn chính thống được RAG truy xuất để chứng minh độ tin cậy của câu trả lời.
    *   Chỉnh sửa câu hỏi cũ, tự động tái tạo luồng hội thoại.
    *   Phản hồi chất lượng (Like/Dislike) kèm ghi chú đánh giá chi tiết.
*   **Góc sức khỏe (Health Corners):**
    *   Tạo các thư mục sức khỏe riêng biệt (như Tim mạch, Mắt, Dạ dày) kèm emoji sinh động.
    *   Gán/Di chuyển cuộc hội thoại vào các Góc sức khỏe tương ứng.
    *   Xóa góc sức khỏe (Bảo toàn các cuộc hội thoại bên trong, tự động chuyển ra danh mục "Gần đây" và đồng bộ hóa lập tức trên Sidebar).
*   **Thanh điều hướng bên (Sidebar):**
    *   Quản lý danh sách hội thoại gần đây (Recent) và hội thoại đã ghim (Pinned).
    *   Tùy chọn nhanh: Ghim/Bỏ ghim, Đổi tên, Di chuyển vào Góc sức khỏe, Xóa hội thoại.
    *   Tooltip nổi thông minh hiển thị đầy đủ tiêu đề bị cắt ngắn (Truncated Titles) sử dụng React Portals chống đè z-index và gỡ bỏ hoàn toàn lỗi nhấp nháy/nhảy vị trí nhờ keyframe cô lập.
    *   Tích hợp Clerk UserButton tùy chỉnh thông tin tài khoản cá nhân.
*   **Tìm kiếm lịch sử (Search Canvas):** Tra cứu nhanh các phiên trò chuyện cũ dựa trên từ khóa.

### 3.2. Tính Năng Cho Quản Trị Viên (Admin Features)
*   **Trang quản trị bảo mật (Admin Dashboard):** Chỉ hiển thị cho tài khoản có vai trò `admin` trong Clerk Metadata, bảo vệ bằng JWT validation tại API Backend.
*   **Giám sát an toàn y tế (Safety Monitor):**
    *   Giám sát thời gian thực nhật ký các câu hỏi độc hại hoặc nguy hiểm bị chặn bởi hệ thống (`unsafe_logs`).
    *   Quản lý danh sách người dùng rủi ro cao. Hỗ trợ thao tác cấm/mở cấm tài khoản (`Ban/Unban`) hoạt động ổn định nhờ cơ chế Outer-Join thông tin người dùng từ bảng `users`, ngăn chặn lỗi "mất dấu tài khoản" (Deadlock) kể cả khi admin xóa sạch nhật ký vi phạm.
*   **Quản lý từ điển y khoa (Medical Dictionary):**
    *   Thêm, sửa, xóa (CRUD) danh mục bệnh mạn tính ICD-10, thuốc thương mại và hoạt chất dị ứng.
    *   Tự động chuẩn hóa dữ liệu khi lưu (tách chuỗi nhập phân tách bằng dấu phẩy thành mảng hoạt chất thực tế) để bảo vệ tính nhất quán của dữ liệu RAG.
*   **Tinh chỉnh hệ thống RAG (System Tuning):**
    *   Điều chỉnh trực tiếp các thông số: Số lượng tài liệu truy xuất (`top_k`), Số lượng tài liệu tái xếp hạng (`top_k_rerank`), Ngưỡng tương đồng tối thiểu (`similarity_threshold`), và Tỷ lệ tìm kiếm hỗn hợp (`hybrid_alpha`).
    *   Kích hoạt nạp lại dữ liệu từ điển y khoa lên bộ nhớ cache RAM bất đồng bộ thông qua `BackgroundTasks` của FastAPI để tránh treo luồng chính (Main Thread) của máy chủ.
    *   Theo dõi biểu đồ hiệu năng hệ thống và số lượng bản ghi thực tế được đồng bộ tự động.
*   **Hộp thư phản hồi (Feedback Inbox):**
    *   Theo dõi toàn bộ đánh giá chất lượng (Like/Dislike) kèm ghi chú từ người dùng.
    *   Biểu đồ thống kê trực quan xu hướng phản hồi 7 ngày qua đã được đồng bộ hóa lệch múi giờ (UTC+7).
    *   **Xuất tập dữ liệu vàng (Dataset Export):** Hỗ trợ xuất dữ liệu chất lượng định dạng JSON Lines (JSONL) dưới dạng **Streaming Response** để tránh tràn bộ nhớ máy chủ (Out of Memory) khi tập dữ liệu phình to.

---

## 4. Cơ Chế Kháng Lỗi & Đảm Bảo Nhất Quán (Safety & Consistency Implementations)

Hệ thống triển khai các giải pháp kỹ thuật tối ưu nhằm loại bỏ các lỗi logic và đồng bộ:

> [!IMPORTANT]
> **1. Tránh mất dữ liệu bệnh án (PATCH Partial Update):**
> API `/api/profile` sử dụng phương thức `PATCH` kết hợp cấu trúc Dot-notation trong MongoDB (Ví dụ: `{"$set": {"health_profile.weight": 65}}`). Điều này ngăn chặn việc cập nhật một trường đơn lẻ (như cân nặng) vô tình ghi đè và làm xóa sạch toàn bộ danh sách bệnh lý nền, dị ứng đã điền trước đó.

> [!TIP]
> **2. Đồng bộ bộ nhớ đệm Suggesion (RapidFuzz ASCII Pre-Normalization):**
> Dữ liệu gợi ý được tải lên RAM lúc startup và chuẩn hóa sẵn sang không dấu (ASCII). Khi người dùng gõ từ khóa, hệ thống so khớp mờ trên dữ liệu đã chuẩn hóa giúp giảm độ phức tạp tính toán từ `O(N)` xuống `O(1)`, ngăn chặn tình trạng nghẽn CPU của backend và giật lag giao diện điền bệnh án của người dùng cuối.

> [!WARNING]
> **3. Đồng bộ hóa khi Mount thiết bị (On-Mount Sync):**
> Khi người dùng đăng nhập trên thiết bị mới, ứng dụng frontend chủ động tải thông tin hồ sơ sức khỏe thực tế từ MongoDB Atlas về lưu trữ vào `localStorage`. Điều này ngăn chặn việc đẩy ngược đối tượng cấu hình trống lên server gây mất dữ liệu bệnh án cũ.

> [!NOTE]
> **4. Cô lập hoạt ảnh Tooltip (Keyframe Collision Fix):**
> Đổi tên `@keyframes tooltipFadeIn` của thanh bên thành `sidebarTooltipFadeIn` và cấu hình hoạt ảnh ở chế độ `forwards`. Việc này ngăn chặn sự chồng chéo với hoạt ảnh của bong bóng chat trong `MessageList.css` (vốn dịch chuyển theo trục X), loại bỏ lỗi tooltip của thanh bên nhảy giật từ giữa màn hình về lề phải khi người dùng hover.

---

## 5. Giám Sát & Vận Hành Hệ Thống (Observability & Monitoring)

### 5.1. Sentry Error Tracking (Frontend & Backend)
*   **Phát hiện sự cố tức thì:** Bắt toàn bộ các ngoại lệ (Uncaught Exceptions), lỗi kết nối API và sập giao diện (Component Crashes). Tự động phân loại và gửi cảnh báo tới quản trị viên.
*   **Bảo vệ thông tin nhạy cảm (PII Redaction):** Cấu hình hook `before_send` ở backend và frontend để lọc bỏ toàn bộ thông tin bệnh án, nội dung trò chuyện y khoa, thuốc dị ứng, email cá nhân... Thay thế bằng nhãn `[REDACTED]` trước khi gửi dữ liệu lỗi về máy chủ Sentry, đảm bảo tuân thủ an toàn thông tin y tế toàn diện.
*   **React ErrorBoundary:** Bọc ứng dụng bằng ErrorBoundary của Sentry để hiển thị màn hình báo lỗi thân thiện thay vì làm trắng màn hình giao diện của người dùng.

### 5.2. JSON Logging có cấu trúc
*   Khi cấu hình biến môi trường `LOG_FORMAT=json`, backend FastAPI sẽ tự động định dạng toàn bộ log hệ thống sang cấu trúc JSON.
*   Định dạng JSON giúp các hệ thống gom log tập trung (như Datadog, ELK, hoặc Hugging Face Logs) dễ dàng truy vấn, lọc log theo `level` (INFO, WARNING, ERROR) hoặc `module` để xử lý sự cố nhanh chóng.

---

## 6. Hướng Dẫn Cài Đặt & Triển Khai (Installation & Setup)

### Yêu Cầu Hệ Thống
*   Python 3.10 trở lên
*   Node.js 18 trở lên
*   Đăng ký tài khoản và lấy các API keys hoạt động cho: Groq, Cohere, Clerk, Sentry.

### Giai Đoạn 1: Cấu hình Backend (FastAPI)
1.  Di chuyển vào thư mục backend và tạo môi trường ảo Python:
    ```bash
    cd backend
    python -m venv venv
    source venv/bin/activate  # Trên Windows dùng: venv\Scripts\activate
    ```
2.  Cài đặt các thư viện phụ thuộc:
    ```bash
    pip install -r requirements.txt
    ```
3.  Tạo tệp cấu hình `.env` tại thư mục `backend` theo mẫu sau:
    ```env
    # Model APIs (Groq)
    GROQ_API_KEY1=your_groq_api_key_1
    GROQ_API_KEY2=your_groq_api_key_2
    GROQ_API_KEY3=your_groq_api_key_3
    GROQ_MODEL=llama-3.3-70b-versatile

    # Cohere Reranker API
    COHERE_API_KEY=your_cohere_api_key
    RERANKER_MODEL=rerank-v4.0-pro

    # Qdrant Vector DB
    QDRANT_MODE=cloud
    QDRANT_CLOUD_URL=https://your-qdrant-cluster-url.qdrant.io:6333
    QDRANT_API_KEY=your_qdrant_api_key
    QDRANT_COLLECTION=vnhealthqa

    # MongoDB Connection
    MONGODB_URL=mongodb+srv://admin:password@cluster.mongodb.net/?retryWrites=true&w=majority

    # Authentication (Clerk)
    CLERK_JWKS_URL=https://your-clerk-domain.clerk.accounts.dev/.well-known/jwks.json
    CLERK_ISSUER=https://your-clerk-domain.clerk.accounts.dev

    # SMTP / Google Script
    GMAIL_SENDER=your-system-email@gmail.com
    GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/your-script-id/exec

    # Sentry & Log format
    SENTRY_DSN_BACKEND=https://your-sentry-dsn@ingest.sentry.io/project-id
    LOG_FORMAT=json
    ```
4.  Đẩy cơ sở dữ liệu tri thức y văn dạng vector nhúng vào Qdrant Cloud:
    ```bash
    python scripts/index_data.py
    ```
5.  Seed dữ liệu gợi ý bệnh mạn tính ICD-10 và dược phẩm thương mại vào MongoDB Atlas:
    ```bash
    python -m scripts.seed_clinical_conditions
    python -m scripts.process_medications
    ```
6.  Khởi chạy máy chủ API Backend:
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

### Giai Đoạn 2: Cấu hình Frontend (React)
1.  Di chuyển vào thư mục frontend và cài đặt các gói phụ thuộc:
    ```bash
    cd frontend
    npm install
    ```
2.  Tạo tệp cấu hình `.env` tại thư mục `frontend` với nội dung:
    ```env
    REACT_APP_CLERK_PUBLISHABLE_KEY=pk_test_your_clerk_key
    REACT_APP_API_URL=http://localhost:8000
    REACT_APP_SENTRY_DSN=https://your-sentry-dsn@ingest.sentry.io/project-id
    ```
3.  Khởi chạy máy chủ thử nghiệm Frontend:
    ```bash
    npm start
    ```
4.  Biên dịch đóng gói sản phẩm (Production Build):
    ```bash
    npm run build
    ```

---

## 7. Kịch Bản Kiểm Thử & Kiểm Định (Testing & Verification)

Hệ thống đi kèm bộ kiểm thử tích hợp tự động toàn diện được thiết kế để xác định khả năng liên thông dữ liệu và tính an toàn của luồng đa tác nhân:

*   **Lệnh chạy kiểm thử tự động:**
    ```bash
    python backend/scratch/system_comprehensive_test.py
    ```
*   **Nội dung kiểm định cốt lõi:**
    1.  **Health Check:** Đảm bảo kết nối mạng đến các API ngoại vi, MongoDB Atlas và Qdrant Vector DB thông suốt.
    2.  **Profile Sync & Partial Update:** Xác minh API `PATCH` cập nhật chính xác và bảo toàn các trường thông tin bệnh án cũ.
    3.  **Dictionary CRUD & Cache Rebuilding:** Kiểm tra việc quản trị viên thêm mới từ điển bệnh ICD-10 và thuốc thương mại, xác minh trigger nạp lại RAM cache chạy ngầm không gây nghẽn.
    4.  **Triage & RAG Safety Verification:** Mô phỏng các truy vấn y tế nguy hiểm, thông tin độc hại, hoặc câu hỏi ngoài lề y học để đảm bảo Triage Agent chặn đứng kịp thời. Xác minh Safety Agent gắn chính xác nhãn cảnh báo lâm sàng (Warnings) khi phát hiện chống chỉ định.
    5.  **Ban/Unban Isolation Check:** Mô phỏng thao tác cấm người dùng, xóa sạch lịch sử log vi phạm và xác nhận admin vẫn thực hiện gỡ cấm (unban) thành công bình thường mà không bị rơi vào trạng thái lỗi treo tài khoản (deadlock).
