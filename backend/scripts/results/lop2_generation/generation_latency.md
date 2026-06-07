# Báo Cáo Hiệu Năng & Độ Trễ (Generation Latency)

**Thời gian thực hiện:** 2026-06-06 17:01:08  
**Tổng số mẫu đánh giá:** 100 mẫu  

## 1. Phân Tích Độ Trễ Hệ Thống (Giây)

| Thành phần hệ thống | Thời gian Trung Bình | Percentile P95 |
| :--- | :---: | :---: |
| **Truy xuất tài liệu (Retrieval + Rerank)** | 1.079s | 1.543s |
| **Sinh câu trả lời (Groq Llama 3.3)** | 1.364s | 2.018s |
| **Đánh giá tự động (Gemini Judge)** | 22.491s | 53.458s |
| **Tổng độ trễ mỗi vòng** | 24.934s | 55.581s |

---

## 2. Kết Luận Hiệu Năng
- Tốc độ sinh câu trả lời của Groq Llama 3.3 đạt hiệu suất cực kỳ ấn tượng nhờ hạ tầng tăng tốc phần cứng của Groq Cloud.
- Tác vụ đánh giá tự động bằng Gemini Judge chiếm một phần độ trễ đáng kể nhưng chỉ dùng để chạy offline/eval, không ảnh hưởng đến trải nghiệm realtime của người dùng cuối.
