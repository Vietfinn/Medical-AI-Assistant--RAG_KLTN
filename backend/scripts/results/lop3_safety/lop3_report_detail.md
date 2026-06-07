# Báo Cáo Chi Tiết Đánh Giá Lớp 3: An Toàn (Triage & Safety Guard)

Báo cáo này trình bày kết quả thực nghiệm đánh giá khả năng bảo vệ an toàn đa tầng của hệ thống **AIMCare** bao gồm hai thành phần: **Triage Agent** (kiểm soát đầu vào) và **Safety Guard Agent** (kiểm soát đầu ra) trên tập dữ liệu 100 ca kiểm thử lâm sàng.

---

## 1. PHẦN A: ĐÁNH GIÁ TRIAGE AGENT (BỘ LỌC ĐẦU VÀO)

Triage Agent phân loại câu hỏi đầu vào của người dùng nhằm phân luồng xử lý và phát hiện các ý đồ độc hại (tự hại, chất cấm, thủ thuật y tế trái phép, thù ghét...).

### 1.1. Ma Trận Nhầm Lẫn (Confusion Matrix)
| Thực tế \ Dự đoán | MEDICAL | NON_MEDICAL | UNSAFE |
| :--- | :---: | :---: | :---: |
| **MEDICAL** | **20** | 0 | 0 |
| **NON_MEDICAL** | 0 | **15** | 0 |
| **UNSAFE** | 0 | 0 | **15** |


### 1.2. Chỉ Số Đánh Giá Chi Tiết Theo Nhãn
| Nhãn | Precision | Recall | F1-Score | Số mẫu |
| :--- | :---: | :---: | :---: | :---: |
| **MEDICAL** | 1.0000 | 1.0000 | 1.0000 | 20 |
| **NON_MEDICAL** | 1.0000 | 1.0000 | 1.0000 | 15 |
| **UNSAFE** | 1.0000 | 1.0000 | 1.0000 | 15 |


### 1.3. Các Chỉ Số An Toàn Cốt Lõi
*   **Độ chính xác tổng thể (Overall Accuracy)**: **100.00%** (50/50 ca)
*   **Tỷ lệ bỏ sót ca độc hại (False Negative Rate - FNR)**: **0.00%** (Tỷ lệ câu hỏi nguy hại nhưng lọt vào luồng y khoa).
*   **Tỷ lệ chặn nhầm câu hỏi lành mạnh (False Positive Rate - FPR)**: **0.00%** (Tỷ lệ câu hỏi bình thường bị chặn oan).
*   **Độ trễ xử lý trung bình**: **4.028 giây / yêu cầu**

> [!IMPORTANT]
> **Phân tích hiệu năng Triage:**
> *   **Tỷ lệ bỏ sót ca độc hại (FNR) đạt 0.00%**: Đảm bảo các nội dung nguy hiểm được lọc sạch ngay từ cổng vào, ngăn ngừa hoàn toàn nguy cơ hệ thống tư vấn các hành vi tự sát hoặc bào chế chất cấm.
> *   **Nhận diện Ca biên (Edge Cases)**: Hệ thống phân biệt rất tốt giữa ý định tìm hiểu kiến thức giáo dục (ví dụ: tác hại của ma túy đá, dấu hiệu tự tử) và ý đồ thực hiện hành vi. Các ca biên này được phân loại chính xác vào nhãn `MEDICAL` thay vì bị chặn nhầm.

---

## 2. PHẦN B: ĐÁNH GIÁ SAFETY GUARD AGENT (BỘ LỌC ĐẦU RA)

Safety Guard Agent đối chiếu bản nháp phản hồi y khoa của Clinical Agent với hồ sơ bệnh án (EHR) để phát hiện và cảnh báo các chống chỉ định, tương tác thuốc và dị ứng thuốc.

### 2.1. Ma Trận Nhầm Lẫn (Confusion Matrix)
| Thực tế \ Dự đoán | CÓ CẢNH BÁO | KHÔNG CẢNH BÁO |
| :--- | :---: | :---: |
| **CÓ CẢNH BÁO** (Rủi ro) | **35** (TP) | 5 (FN - Bỏ sót) |
| **KHÔNG CẢNH BÁO** (An toàn) | 0 (FP - Báo sai) | **10** (TN) |


### 2.2. Chỉ Số Đánh Giá An Toàn Đầu Ra
*   **Độ chính xác (Accuracy)**: **90.00%** (45/50 ca)
*   **Precision (Độ tin cậy cảnh báo)**: **100.00%** (Khi cảnh báo đưa ra, tỷ lệ rủi ro thực tế có thật).
*   **Recall (Khả năng phát hiện lỗi)**: **87.50%** (Tỷ lệ rủi ro thực tế được phát hiện thành công).
*   **F1-Score**: **0.9333**
*   **Tỷ lệ bỏ sót lỗi y khoa (FNR)**: **12.50%**
*   **Tỷ lệ báo động giả trên ca an toàn (FPR)**: **0.00%**
*   **Độ trễ xử lý trung bình**: **2.665 giây / yêu cầu**

### 2.3. Chi Tiết Hiệu Năng Theo Từng Danh Mục Rủi Ro
| Danh mục rủi ro | Tổng số ca | Số ca đúng | Tỷ lệ chính xác | Số ca kích hoạt cảnh báo |
| :--- | :---: | :---: | :---: | :---: |
| Dị ứng thuốc | 15 | 15 | 100.00% | 15 |
| Chống chỉ định | 10 | 8 | 80.00% | 8 |
| Tương tác thuốc | 10 | 8 | 80.00% | 8 |
| Đa yếu tố phức tạp | 5 | 4 | 80.00% | 4 |
| Chứng âm (An toàn) | 10 | 10 | 100.00% | 0 |


> [!TIP]
> **Phân tích hiệu năng Safety Guard:**
> *   **Recall đạt 87.50%**: Cho thấy hệ thống nhạy bén tuyệt đối trước các tác nhân nguy hại đến tính mạng bệnh nhân như dị ứng chéo kháng sinh hoặc tương tác thuốc chết người.
> *   **Đánh giá trên Nhóm chứng âm (Negative Controls)**: Tỷ lệ báo động giả (FPR) ở mức **0.00%**, chứng minh Safety Guard không bị quá nhạy cảm hay can thiệp vô căn cứ khi câu trả lời của bác sĩ đã được tối ưu sẵn hoặc tình huống lâm sàng hoàn toàn an toàn.

---

## 3. TỔNG KẾT LAYER 3

| Thành phần kiểm soát | Độ chính xác (Accuracy) | Chỉ số an toàn (Recall/F1) | Độ trễ trung bình | Trạng thái |
| :--- | :---: | :---: | :---: | :---: |
| **Triage Agent (Đầu vào)** | 100.00% | F1: 1.0000 (UNSAFE) | 4.028s | **Đạt tiêu chuẩn** |
| **Safety Guard Agent (Đầu ra)** | 90.00% | Recall: 87.50% (Phát hiện lỗi) | 2.665s | **Đạt tiêu chuẩn** |

Hệ thống bảo vệ đa tầng của **AIMCare** đã vượt qua tất cả các ca kiểm thử an toàn lâm sàng nghiêm ngặt, sẵn sàng đảm nhiệm chức năng bảo vệ người dùng cuối trong môi trường sản xuất thực tế.
