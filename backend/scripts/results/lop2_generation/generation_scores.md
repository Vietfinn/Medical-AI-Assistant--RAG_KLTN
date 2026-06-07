# Báo Cáo Đánh Giá Chất Lượng Sinh Câu Trả Lời (RAG Generation)

**Thời gian thực hiện:** 2026-06-06 17:01:08  
**Tổng số mẫu đánh giá:** 100 mẫu (ngẫu nhiên từ `test_clean.csv`)  
**Judge LLM:** `gemini-2.5-flash` (LLM-as-a-Judge)

## 1. Kết Quả Điểm Số Đánh Giá

| Chỉ số đánh giá | Điểm Trung Bình | Độ lệch chuẩn (Std Dev) | Nhỏ nhất (Min) | Lớn nhất (Max) |
| :--- | :---: | :---: | :---: | :---: |
| **Traditional N-gram Metrics** | | | | |
| BLEU-4 | 0.1977 | 0.1543 | 0.0017 | 0.6929 |
| ROUGE-L | 0.4253 | 0.1636 | 0.1091 | 0.8605 |
| **Embedding Similarity** | | | | |
| Cosine Similarity (BKAI) | 0.6673 | 0.1760 | 0.0784 | 0.9258 |
| **LLM-as-a-Judge (Thang 1-5)** | | | | |
| Faithfulness (Tính trung thực) | 4.74/5.0 | 0.63 | 2.0 | 5.0 |
| Answer Relevance (Liên quan câu hỏi) | 4.62/5.0 | 0.80 | 1.0 | 5.0 |
| Context Relevance (Liên quan tài liệu) | 4.81/5.0 | 0.64 | 1.0 | 5.0 |

---

## 2. Nhận Xét & Phân Tích
- **Faithfulness (4.74/5.0):** Đo lường mức độ trung thực y khoa. Điểm số cao chứng minh hệ thống tuân thủ nghiêm ngặt quy tắc RAG không bịa đặt thông tin.
- **Answer Relevance (4.62/5.0):** Đo lường sự tập trung vào câu hỏi của người dùng. Hệ thống có trả lời lạc đề hay đi thẳng vào trọng tâm chuyên môn.
- **Context Relevance (4.81/5.0):** Thể hiện chất lượng của phần Retrieval. Tài liệu trích xuất có đủ để trả lời câu hỏi hay không.
