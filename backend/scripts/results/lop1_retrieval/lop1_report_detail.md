# Báo Cáo Chi Tiết Đánh Giá Lớp 1: Khả Năng Truy Xuất (Retrieval Evaluation)

Báo cáo này trình bày chi tiết về quá trình thực nghiệm, các thách thức kỹ thuật gặp phải, giải pháp khắc phục và phân tích chuyên sâu các kết quả thu được từ quá trình đánh giá **Lớp 1 (Retrieval Layer)** của hệ thống **AIMCare**.

---

## 1. Tổng Quan Cấu Hình Thử Nghiệm

*   **Bộ dữ liệu**: Toàn bộ **2,012 mẫu câu hỏi - câu trả lời** y khoa sạch từ `test_clean.csv`.
*   **Hạ tầng lưu trữ**: Vector Database **Qdrant** chạy local Docker container.
*   **Collection**: `vnhealthqa` chứa cơ sở tri thức y khoa đã được index.
*   **Mô hình Embedding**: `bkai-foundation-models/vietnamese-bi-encoder` sinh dense vector 768 chiều.
*   **Mô hình Reranker**: `cohere-rerank-v4.0-pro` thông qua Cohere API.
*   **Tham số tìm kiếm**: Top $K = 20$ tài liệu ứng viên từ Hybrid Search trước khi đưa vào Cohere Reranker để chọn ra Top $5$ kết quả cuối cùng.

---

## 2. Quá Trình Chạy Thực Nghiệm & Giải Pháp Kỹ Thuật

Quá trình chạy thử nghiệm Lớp 1 trên lượng dữ liệu lớn (2,012 mẫu) gặp nhiều thách thức liên quan đến giới hạn băng thông API và độ ổn định của kết nối mạng.

### 2.1. Các Thách Thức Gặp Phải
1.  **Lỗi giới hạn tần suất gọi Cohere API (429 Rate Limit)**: API Key miễn phí của Cohere giới hạn khắt khe ở mức **10 RPM (Requests Per Minute)**. Khi chạy tuần tự không kiểm soát tốc độ, hệ thống ngay lập tức bị khóa kết nối sau 10 requests đầu tiên.
2.  **Lỗi kết nối Socket Qdrant khi tải cao**: Khi thực hiện truy vấn dense vector và sparse vector (BM25) liên tục, kết nối gRPC/HTTP tới Qdrant thỉnh thoảng bị nghẽn hoặc ngắt đột ngột (Socket connection reset).

### 2.2. Các Giải Pháp Đã Triển Khai
Để đảm bảo tiến trình chạy liên tục và tự động phục hồi khi gặp lỗi, các cơ chế sau đã được xây dựng và áp dụng:
*   **Cơ chế checkpoint tự động (`retrieval_checkpoint.json`)**: Cứ sau mỗi batch truy vấn, tiến trình sẽ lưu trạng thái hiện tại. Nếu xảy ra lỗi crash hoặc mất mạng, script có thể chạy tiếp tục bằng cờ `--resume` mà không cần chạy lại từ đầu.
*   **Thiết lập khoảng trễ an toàn (Delay-based throttling)**: Đối với cấu hình C sử dụng Cohere Reranker, chúng tôi duy trì `COHERE_DELAY = 6.2` giây giữa mỗi request, giữ tần suất gọi ở mức an toàn ~9.6 RPM.
*   **Cơ chế phòng thủ Rate Limit thông minh**: Nếu gặp lỗi `429 Too Many Requests`, hệ thống tự động phát hiện, tạm dừng (sleep) đúng **62 giây** để reset hoàn toàn cửa sổ thời gian (window quota) của Cohere, sau đó tự động thử lại (tối đa 3 lần).
*   **Tạo bản vá lỗi tự động (`patch_eval_retrieval.py`)**: Bản vá được thiết kế để quét file kết quả JSON, tự động tìm ra các case bị lỗi do Cohere từ chối kết nối trước đó, thực hiện chạy bù và ghi đè trực tiếp kết quả chính xác vào file dữ liệu.

---

## 3. Phân Tích Kết Quả Thu Được

### 3.1. Chỉ Số Chất Lượng Truy Xuất (Ablation Study)

| Cấu hình truy xuất (Retrieval Configuration) | P@1 (%) | P@5 (%) | P@10 (%) | mAP (%) |
| :--- | :---: | :---: | :---: | :---: |
| *BM25 (SPBERTQA Baseline)* | 44.96 | — | 70.09 | 56.93 |
| *SPBERTQA (Best Baseline)* | 50.92 | — | 83.76 | 62.25 |
| **Dense Only** (vietnamese-bi-encoder) | **91.05** | **95.13** | **96.57** | **92.88** |
| **Hybrid RRF** (Dense + BM25) | **95.83** | **99.60** | **99.85** | **97.62** |
| **Hybrid RRF + Cohere Reranker** | **97.47** | **99.75** | **99.85** | **98.51** |

> [!IMPORTANT]
> **Nhận xét quan trọng:**
> *   Hệ thống AIMCare vượt trội hoàn toàn so với các baseline trong bài báo SPBERTQA (với P@1 đạt **97.47%** so với **50.92%** của SPBERTQA). Điều này nhờ vào chất lượng vượt trội của mô hình embedding tiếng Việt hiện đại kết hợp với cơ chế xếp hạng lại.
> *   **Hiệu ứng cộng hưởng của Hybrid Search**: Việc tích hợp từ khóa truyền thống (BM25) song song với ngữ nghĩa (Dense Vector) qua công thức RRF (Reciprocal Rank Fusion) giúp cải thiện P@1 thêm **4.78%** và mAP thêm **4.74%**.
> *   **Reranker đóng vai trò chốt chặn**: Cohere Rerank đẩy P@1 lên mức tối đa **97.47%** (tăng **1.64%** so với Hybrid và **6.42%** so với Dense Only). Việc này đảm bảo tài liệu chính xác nhất luôn nằm ở vị trí số 1, cung cấp ngữ cảnh hoàn hảo nhất cho Clinical Agent sinh câu trả lời.

### 3.2. Hiệu Năng & Độ Trễ (Retrieval Latency)

| Cấu hình truy xuất | Độ trễ Trung bình (ms) | Percentile P95 (ms) |
| :--- | :---: | :---: |
| Dense Only | 421.8 ms | 593.1 ms |
| Hybrid RRF (Dense + BM25) | 409.8 ms | 549.9 ms |
| Hybrid RRF + Cohere Reranker | 1,180.6 ms | 4,060.8 ms |

> [!TIP]
> **Phân tích hiệu năng:**
> *   **Độ trễ nội bộ (Dense / Hybrid RRF)** cực kỳ nhanh, trung bình chỉ khoảng **~410ms**.
> *   **Độ trễ Reranker ngoại vi**: Khi bổ sung Cohere Reranker, độ trễ trung bình tăng lên **1.18 giây** (P95 đạt tới **4.06 giây**). Điều này là do chi phí gọi API đám mây của Cohere và kích thước prompt lớn.
> *   **Giải pháp thực tế**: Với các câu hỏi yêu cầu thời gian phản hồi cực nhanh, cấu hình **Hybrid RRF** (không Rerank) là một lựa chọn tối ưu khi vẫn giữ được P@5 ở mức **99.60%** nhưng tiết kiệm được hơn **65%** thời gian xử lý.

---

## 4. Kết Luận
Quá trình chạy Lớp 1 đã hoàn thành xuất sắc và thu được bộ dữ liệu kiểm chứng chất lượng cao. Sự kết hợp giữa **Hybrid Search** và **Cohere Reranker** đem lại kết quả truy xuất y khoa tiệm cận mức hoàn hảo (Hit Rate@5 đạt **99.75%**), làm nền tảng vững chắc cho quá trình sinh câu trả lời ở Lớp 2.
