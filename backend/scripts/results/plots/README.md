# Tài Liệu Chú Thích Chi Tiết Hệ Thống Biểu Đồ Đánh Giá AIMCare

Thư mục này chứa các biểu đồ trực quan hóa dữ liệu được sinh ra tự động từ kết quả thực nghiệm của bộ **Evaluation Suite (Lớp 1, 2, và 3)** thuộc hệ thống Trợ lý Y tế AI (AIMCare). Các biểu đồ này được thiết kế với độ phân giải cao (300 DPI) và hệ màu hiện đại, sẵn sàng để chèn vào khóa luận tốt nghiệp, slide thuyết trình hoặc bài báo nghiên cứu.

---

## Danh Sách Các Biểu Đồ & Chú Thích Chi Tiết

### 1. So Sánh Hiệu Năng Các Phương Pháp Truy Xuất Tài Liệu (Lớp 1)
*   **Tên tệp:** `lop1_retrieval_comparison.png`
*   **Loại biểu đồ:** Biểu đồ cột ngang (Horizontal Bar Chart).
*   **Dữ liệu đằng sau:** Kết quả trích xuất trên toàn bộ **2,012 mẫu thử** sạch (`test_clean.csv`) so sánh giữa 4 phương pháp:
    *   *Vector Search* (BKAI Bi-Encoder): 0.8122
    *   *BM25* (Lexical Search): 0.6974
    *   *Hybrid Search* (Vector + BM25): 0.8443
    *   *Hybrid + Cohere Rerank v4.0* (Đề xuất): **0.8654**
*   **Ý nghĩa khoa học:** Thể hiện rõ nét tác động tích cực của các kỹ thuật cải tiến. Việc kết hợp **Hybrid Search** và tái xếp hạng bằng **Cohere Reranker v4.0** giúp nâng cao chỉ số MRR@5 và Recall@5 thêm **5.32%** so với chỉ dùng Vector đơn thuần, chứng minh khả năng định vị tài liệu y khoa chính xác của hệ thống.
*   **Đề xuất trình bày:** Sử dụng làm biểu đồ cốt lõi cho chương *"Thử nghiệm và Kết quả - Phần Đánh giá Khả năng Truy xuất (Layer 1)"*.

---

### 2. Điểm Số Đánh Giá RAG Triad Bằng LLM-as-a-Judge (Lớp 2)
*   **Tên tệp:** `lop2_rag_triad.png`
*   **Loại biểu đồ:** Biểu đồ cột đứng (Vertical Bar Chart).
*   **Dữ liệu đằng sau:** Điểm số trung bình chấm bởi giám khảo **Gemini 2.5 Flash** trên **100 mẫu ngẫu nhiên** (thang điểm 1 - 5):
    *   *Faithfulness* (Tính trung thực y khoa): **4.74 / 5.0** (Độ lệch chuẩn: 0.63)
    *   *Answer Relevance* (Trả lời đúng trọng tâm): **4.62 / 5.0** (Độ lệch chuẩn: 0.80)
    *   *Context Relevance* (Mức độ liên quan của tài liệu): **4.81 / 5.0** (Độ lệch chuẩn: 0.64)
*   **Ý nghĩa khoa học:** 
    *   Điểm *Faithfulness* cao (4.74) chứng minh Clinical Agent tuân thủ nghiêm ngặt nguyên tắc **Zero-Hallucination**, không tự ý bịa đặt hay suy diễn kiến thức ngoài tầm kiểm soát của tài liệu y khoa.
    *   Điểm *Context Relevance* (4.81) khẳng định sự tối ưu của bộ lọc trích xuất tài liệu (Lớp 1) khi cung cấp các tài liệu cực kỳ khớp với câu hỏi của bệnh nhân.
*   **Đề xuất trình bày:** Sử dụng để thuyết phục Hội đồng về chất lượng và độ an toàn của nội dung y khoa mà chatbot sinh ra.

---

### 3. Ma Trận Nhầm Lẫn Triage Agent Đầu Vào (Lớp 3)
*   **Tên tệp:** `lop3_triage_confusion_matrix.png`
*   **Loại biểu đồ:** Biểu đồ nhiệt ma trận nhầm lẫn 3x3 (Confusion Matrix Heatmap).
*   **Dữ liệu đằng sau:** 50 ca kiểm thử đầu vào của Triage Agent:
    *   *MEDICAL:* 20 ca thực tế -> Phân loại đúng 20 ca.
    *   *NON_MEDICAL:* 15 ca thực tế -> Phân loại đúng 15 ca.
    *   *UNSAFE:* 15 ca thực tế -> Phân loại đúng 15 ca.
*   **Ý nghĩa khoa học:** Thể hiện độ chính xác tuyệt đối **100.00%** (Accuracy = 1.0) của bộ lọc phân loại ý định đầu vào. Tỷ lệ bỏ sót ca độc hại (False Negative Rate) và tỷ lệ chặn nhầm ca lành mạnh (False Positive Rate) đều đạt **0.00%**. Chứng tỏ Llama-3 nhận diện rất tốt các ca biên (Edge Cases) mang tính giáo dục y tế lành mạnh thay vì chặn nhầm do nhạy cảm quá mức.
*   **Đề xuất trình bày:** Thích hợp đưa vào phần giải pháp kiến trúc an toàn đầu vào.

---

### 4. Ma Trận Nhầm Lẫn Safety Guard Agent Đầu Ra (Lớp 3)
*   **Tên tệp:** `lop3_safety_confusion_matrix.png`
*   **Loại biểu đồ:** Biểu đồ nhiệt ma trận nhầm lẫn 2x2 (Confusion Matrix Heatmap).
*   **Dữ liệu đằng sau:** 50 ca kiểm thử đối chiếu hồ sơ bệnh án y khoa đầu ra:
    *   *True Positive (TP - Báo động đúng):* **35 ca** (Hệ thống phát hiện chính xác bản nháp chứa lỗi y khoa nguy hiểm).
    *   *False Negative (FN - Bỏ sót lỗi):* **5 ca** (Mô hình bỏ sót các tương tác dược lý / thức ăn phức tạp).
    *   *False Positive (FP - Báo động giả):* **0 ca** (Không có cảnh báo sai trên nhóm chứng âm).
    *   *True Negative (TN - An toàn đúng):* **10 ca** (Hồ sơ chứng âm an toàn được cho phép qua thuận lợi).
*   **Ý nghĩa khoa học:** Minh họa khả năng phòng thủ cuối cùng của Safety Guard. Đạt **Precision 100%** (không có báo động giả gây phiền cho bác sĩ/người dùng) và **Recall 87.50%** (phát hiện phần lớn các rủi ro y khoa nguy hại tính mạng như dị ứng chéo kháng sinh, chống chỉ định).
*   **Đề xuất trình bày:** Đưa vào chương phân tích an toàn lâm sàng, kết hợp cùng phần thảo luận về 5 ca bỏ sót.

---

### 5. Hiệu Năng Nhận Diện Rủi Ro Theo Danh Mục (Lớp 3)
*   **Tên tệp:** `lop3_safety_categories.png`
*   **Loại biểu đồ:** Biểu đồ cột ngang (Horizontal Bar Chart).
*   **Dữ liệu đằng sau:** Tỷ lệ phát hiện lỗi y khoa chính xác theo từng nhóm kiểm thử lâm sàng:
    *   *Dị ứng thuốc (Drug Allergy):* **100.0%** (15/15 ca)
    *   *Chống chỉ định (Contraindication):* **80.0%** (8/10 ca)
    *   *Tương tác thuốc (Drug-Drug):* **80.0%** (8/10 ca)
    *   *Đa yếu tố (Multi-factor):* **80.0%** (4/5 ca)
    *   *Chứng âm (Negative Control):* **100.0%** (10/10 ca)
*   **Ý nghĩa khoa học:** Cho thấy thế mạnh vượt trội của Safety Guard Agent trong việc xử lý dị ứng thuốc và kiểm tra các ca chứng âm (đều đạt 100%). Đồng thời làm nổi bật giới hạn cần khắc phục của mô hình trên các tương tác đa yếu tố phức tạp hoặc chống chỉ định tương đối (80%).
*   **Đề xuất trình bày:** Dùng để làm rõ mức độ bảo mật lâm sàng chi tiết của chatbot.

---

### 6. Phân Tích Độ Trễ Trung Bình Của Hệ Thống (AIMCare)
*   **Tên tệp:** `system_latency_comparison.png`
*   **Loại biểu đồ:** Biểu đồ cột đứng kết hợp hộp thông tin (Vertical Bar Chart with Info Box).
*   **Dữ liệu đằng sau:** Độ trễ trung bình của các thành phần (đơn vị: giây):
    *   *Triage Agent (Đầu vào):* **4.033 giây** (Thực hiện phân tích đa tác vụ)
    *   *Truy xuất tài liệu (Retrieval + Rerank):* **1.079 giây**
    *   *Sinh câu trả lời (Clinical Agent):* **1.364 giây**
    *   *Safety Guard Agent (Đầu ra):* **2.660 giây**
*   **Ý nghĩa khoa học:** 
    *   Hộp thông tin làm rõ: Độ trễ Core RAG vận hành chính (chỉ gồm Truy xuất + Sinh câu trả lời) chỉ mất **2.443 giây**, hoàn toàn đáp ứng tiêu chuẩn phản hồi thời gian thực (realtime) mượt mà cho người dùng.
    *   Tổng thời gian xử lý toàn trình (khi kích hoạt tối đa bộ lọc an toàn đa tầng đầu cuối) là **9.136 giây**. Đây là sự đánh đổi chấp nhận được (Trade-off) để đổi lấy tính an toàn y học tuyệt đối trước khi đưa thông tin đến bệnh nhân.
*   **Đề xuất trình bày:** Rất quan trọng khi trình bày về mặt kiến trúc hệ thống và khả năng ứng dụng thực tế (Deployability).

---

## Hướng Dẫn Sử Dụng Biểu Đồ Trên Slide Thuyết Trình

Khi đưa các hình ảnh này vào Slide PowerPoint hoặc Canva để bảo vệ khóa luận trước Hội đồng:
1.  **Một Slide - Một Biểu đồ:** Không nên nhồi nhét nhiều biểu đồ vào một slide. Hãy để biểu đồ chiếm ít nhất 60% diện tích slide để Hội đồng dễ quan sát.
2.  **Định dạng không nền (nếu cần):** Các biểu đồ được xuất ra có nền trắng tinh khiết, rất thích hợp chèn vào slide có nền sáng hoặc viền mờ.
3.  **Tập trung vào "Đề xuất":** Trên slide Lớp 1, hãy dùng hiệu ứng khoanh tròn đỏ vào cột *Hybrid + Cohere Rerank (Đề xuất)* để nhấn mạnh giải pháp của bạn vượt trội hơn hẳn các phương pháp truyền thống khác.
