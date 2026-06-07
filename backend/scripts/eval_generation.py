"""
Lớp 2: Đánh Giá Chất Lượng Sinh Câu Trả Lời (RAG Generation Quality)
====================================================================
Chạy đánh giá chất lượng câu trả lời y khoa của Clinical RAG Agent (Llama 3.3 via Groq)
trên một tập mẫu ngẫu nhiên (mặc định 100 mẫu) từ test_clean.csv.

Các chỉ số được đánh giá bao gồm:
  - Chỉ số truyền thống: BLEU-4, ROUGE-L, Cosine Similarity (BKAI Vietnamese Bi-Encoder).
  - Chỉ số LLM-as-a-Judge (RAG Triad): Faithfulness, Answer Relevance, Context Relevance
    chấm trên thang điểm từ 1-5 sử dụng mô hình gemini-2.5-flash (tự động xoay vòng API key).

Báo cáo kết quả sẽ được lưu tại:
  - backend/scripts/results/generation_scores.md
  - backend/scripts/results/generation_latency.md
  - backend/scripts/results/generation_details.json
"""

import argparse
import json
import time
import logging
import random
from pathlib import Path
from datetime import datetime
import numpy as np

# Import các tiện ích từ Lớp 0
from eval_utils import (
    setup_logging,
    load_test_data,
    connect_qdrant,
    init_embedding,
    ensure_lop2_results_dir,
    calculate_bleu4,
    calculate_rouge_l,
    calculate_cosine_similarity,
    GeminiKeyRotator,
    timer,
    print_progress,
    RESULTS_DIR,
)

# Import các service sản xuất
from services.retriever import HybridRetriever
from services.reranker import Reranker
from services.llm import ClinicalLLMService
from config import settings

logger = logging.getLogger(__name__)

# ── Hằng số cấu hình ─────────────────────────────────────────────────────────
DEFAULT_SAMPLE_LIMIT = 100
RANDOM_SEED = 42
COHERE_RERANK_TOP_K = 5
GROQ_RATE_DELAY = 1.0  # Chờ 1 giây giữa các cuộc gọi Groq để tránh 429

# ── Prompt định nghĩa cho Gemini Judge (RAG Triad) ───────────────────────────
JUDGE_SYSTEM_INSTRUCTION = """Bạn là một chuyên gia đánh giá hệ thống RAG (Retrieval-Augmented Generation) trong lĩnh vực Y khoa.
Nhiệm vụ của bạn là đánh giá câu trả lời của AI dựa trên 3 tiêu chí của RAG Triad:
1. Faithfulness (Tính trung thực/Trung thành): Câu trả lời của AI có được rút ra hoàn toàn từ Tài liệu tham khảo (Context) hay không? Có bịa đặt hay tự suy diễn thông tin nằm ngoài ngữ cảnh không?
2. Answer Relevance (Sự liên quan của câu trả lời): Câu trả lời có giải quyết đúng và đầy đủ câu hỏi của người dùng hay không?
3. Context Relevance (Sự liên quan của tài liệu tham khảo): Tài liệu tham khảo có chứa thông tin liên quan trực tiếp đến câu hỏi của người dùng hay không?

Quy tắc chấm điểm (Thang điểm từ 1 đến 5):
- 5: Xuất sắc, hoàn hảo, hoàn toàn liên quan hoặc hoàn toàn trung thực.
- 4: Tốt, có một vài thiếu sót nhỏ hoặc thông tin phụ không đáng kể.
- 3: Trung bình, chỉ đáp ứng được khoảng một nửa yêu cầu hoặc có một số thông tin không chính xác/không liên quan nhẹ.
- 2: Kém, phần lớn thông tin không chính xác, không liên quan, hoặc bịa đặt nhiều.
- 1: Hoàn toàn không liên quan, bịa đặt hoàn toàn, hoặc không chứa bất kỳ giá trị y khoa nào phù hợp.

Định dạng đầu ra bắt buộc:
Trả về duy nhất định dạng JSON có cấu trúc như ví dụ sau (KHÔNG thêm markdown block ```json hay bất kỳ chữ nào khác ngoài JSON):
{
  "faithfulness": {
    "score": 5,
    "reason": "Lý do chấm điểm..."
  },
  "answer_relevance": {
    "score": 4,
    "reason": "Lý do chấm điểm..."
  },
  "context_relevance": {
    "score": 5,
    "reason": "Lý do chấm điểm..."
  }
}
"""

JUDGE_PROMPT_TEMPLATE = """Dữ liệu đánh giá:
---
[CÂU HỎI CỦA NGƯỜI DÙNG]
{question}

---
[TÀI LIỆU THAM KHẢO (CONTEXT)]
{context}

---
[CÂU TRẢ LỜI CỦA AI]
{ai_answer}

---
[CÂU TRẢ LỜI CHUẨN (GOLD ANSWER)]
{gold_answer}
"""


class GroqKeyRotator:
    """Xoay vòng các Groq API key nhằm tránh rate limit 429 trên Groq."""
    def __init__(self):
        self.keys = [
            settings.GROQ_API_KEY,
            settings.GROQ_API_KEY1,
            settings.GROQ_API_KEY2,
            settings.GROQ_API_KEY3
        ]
        self.keys = [k.strip() for k in self.keys if k and k.strip()]
        self.current_idx = 0
        logger.info(f"GroqKeyRotator: Đã load {len(self.keys)} Groq API keys.")

    def get_service(self) -> ClinicalLLMService:
        if not self.keys:
            raise RuntimeError("Không cấu hình Groq API key nào trong backend/.env!")
        key = self.keys[self.current_idx]
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        
        svc = ClinicalLLMService(api_key=key, model_name=settings.GROQ_MODEL)
        svc.configure()
        return svc


def clean_and_parse_json(text: str) -> dict:
    """Hàm dọn dẹp các khối ```json ... ``` để parse JSON an toàn."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


def get_checkpoint_path() -> Path:
    return ensure_lop2_results_dir() / "generation_checkpoint.json"


def save_checkpoint(data: dict):
    path = get_checkpoint_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_checkpoint() -> dict | None:
    path = get_checkpoint_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def run_evaluation(args):
    results_dir = ensure_lop2_results_dir()
    
    print("=" * 70)
    print("  LỚP 2: ĐÁNH GIÁ CHẤT LƯỢNG SINH CÂU TRẢ LỜI (RAG GENERATION)")
    print("=" * 70)
    
    # ── 1. Load và phân mẫu test ──────────────────────────────────────────────
    test_data = load_test_data()
    total_available = len(test_data)
    
    limit = args.limit or DEFAULT_SAMPLE_LIMIT
    
    # Đọc checkpoint nếu có
    checkpoint = None
    if args.resume:
        checkpoint = load_checkpoint()
        
    if checkpoint:
        sampled_indices = checkpoint.get("sampled_indices", [])
        sampled_data = [test_data[idx] for idx in sampled_indices if idx < total_available]
        start_idx = checkpoint.get("next_index", 0)
        completed_results = checkpoint.get("results", [])
        print(f"  🔄 Tiếp tục từ checkpoint: {start_idx}/{len(sampled_data)} mẫu đã xong")
    else:
        # Lấy ngẫu nhiên các chỉ mục mẫu test với seed cố định
        random.seed(RANDOM_SEED)
        all_indices = list(range(total_available))
        sampled_indices = random.sample(all_indices, min(limit, total_available))
        sampled_data = [test_data[idx] for idx in sampled_indices]
        start_idx = 0
        completed_results = []
        print(f"  🎯 Đã chọn ngẫu nhiên {len(sampled_data)} mẫu test từ {total_available} mẫu gốc")
        
    print()

    # ── 2. Khởi tạo các Service ───────────────────────────────────────────────
    print("Đang khởi tạo các services...")
    qdrant_client = connect_qdrant()
    embedding_svc = init_embedding()
    
    # Retriever
    retriever = HybridRetriever(
        qdrant_client=qdrant_client,
        collection_name=settings.QDRANT_COLLECTION,
        embedding_service=embedding_svc
    )
    
    # Reranker
    if not settings.COHERE_API_KEY:
        raise ValueError("COHERE_API_KEY chưa được cấu hình!")
    reranker = Reranker(api_key=settings.COHERE_API_KEY)
    reranker.load_model()
    
    # Rotator cho Groq và Gemini
    groq_rotator = GroqKeyRotator()
    gemini_rotator = GeminiKeyRotator()
    
    print("  ✅ Tất cả services đã khởi tạo thành công.")
    print()

    # ── 3. Vòng lặp chạy đánh giá ─────────────────────────────────────────────
    results = completed_results
    
    for i in range(start_idx, len(sampled_data)):
        item = sampled_data[i]
        question = item["question"]
        gold_answer = item["answer"]
        original_idx = sampled_indices[i]
        
        print(f"\n[{i+1}/{len(sampled_data)}] Đang xử lý mẫu #{original_idx}...")
        
        # ─ Bước A: Truy xuất tài liệu (Retrieval Pipeline) ──────────────────
        t0 = time.time()
        # 1. Tìm kiếm Hybrid
        hybrid_docs = retriever.hybrid_search(question, top_k=20)
        # 2. Rerank lấy Top 5
        reranked_docs = reranker.rerank(question, hybrid_docs, top_k=COHERE_RERANK_TOP_K)
        retrieval_latency = time.time() - t0
        
        # Định dạng context cho prompt
        context_str = ""
        for idx, doc in enumerate(reranked_docs, 1):
            context_str += f"[Tài liệu {idx}]\nCâu hỏi liên quan: {doc.get('question','')}\nCâu trả lời bác sĩ: {doc.get('answer','')}\n\n"
        context_str = context_str.strip()
        
        # ─ Bước B: Sinh câu trả lời (Groq Llama 3.3) ────────────────────────
        # Chọn Groq service ngẫu nhiên/xoay vòng
        llm_service = groq_rotator.get_service()
        
        t0 = time.time()
        try:
            ai_answer = llm_service.generate_response(
                query=question,
                documents=reranked_docs,
                health_profile=None,
                strict_mode=True
            )
        except Exception as e:
            logger.error(f"Lỗi khi sinh câu trả lời với Groq: {e}. Thử lại với key tiếp theo...")
            time.sleep(2)
            llm_service = groq_rotator.get_service()
            ai_answer = llm_service.generate_response(
                query=question,
                documents=reranked_docs,
                health_profile=None,
                strict_mode=True
            )
        generation_latency = time.time() - t0
        
        # Chờ giãn cách cuộc gọi Groq
        time.sleep(GROQ_RATE_DELAY)
        
        # ─ Bước C: Tính chỉ số truyền thống (BLEU, ROUGE, Cosine Similarity) ─
        bleu4 = calculate_bleu4(gold_answer, ai_answer)
        rouge_l = calculate_rouge_l(gold_answer, ai_answer)
        cosine_sim = calculate_cosine_similarity(embedding_svc, gold_answer, ai_answer)
        
        # ─ Bước D: Đánh giá bằng Gemini (LLM-as-a-Judge) ───────────────────
        judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
            question=question,
            context=context_str if context_str else "Không tìm thấy tài liệu phù hợp.",
            ai_answer=ai_answer,
            gold_answer=gold_answer
        )
        
        t0 = time.time()
        judge_data = None
        # Sử dụng duy nhất gemini-2.5-flash làm judge để đồng bộ hệ thống
        models_to_try = ["gemini-2.5-flash"]
        success = False
        
        for model_to_use in models_to_try:
            if success:
                break
            for attempt in range(3):
                try:
                    raw_judge_response = gemini_rotator.generate_content(
                        model_name=model_to_use,
                        prompt=judge_prompt,
                        system_instruction=JUDGE_SYSTEM_INSTRUCTION,
                        temperature=0.1,
                        max_retries_per_call=15  # Tăng số lần thử xoay vòng key để tránh bị lỗi khi tất cả các key bị 429 cùng lúc
                    )
                    
                    judge_data = clean_and_parse_json(raw_judge_response)
                    
                    # Xác thực cấu trúc trả về
                    for metric in ["faithfulness", "answer_relevance", "context_relevance"]:
                        if metric not in judge_data or "score" not in judge_data[metric]:
                            raise ValueError(f"Thiếu trường '{metric}' hoặc 'score' trong phản hồi JSON.")
                    success = True
                    break
                except Exception as ex:
                    logger.warning(f"Thử gọi {model_to_use} làm giám khảo thất bại (lần thử {attempt+1}): {ex}")
                    time.sleep(1)
                    
        gemini_latency = time.time() - t0
        
        if judge_data is None:
            # Fallback nếu lỗi hoàn toàn
            logger.error("Không nhận được phản hồi chấm điểm hợp lệ từ Gemini. Gán điểm mặc định là 1.0.")
            judge_data = {
                "faithfulness": {"score": 1, "reason": "Lỗi hệ thống khi gọi Gemini Judge"},
                "answer_relevance": {"score": 1, "reason": "Lỗi hệ thống khi gọi Gemini Judge"},
                "context_relevance": {"score": 1, "reason": "Lỗi hệ thống khi gọi Gemini Judge"}
            }

        # Ghi nhận kết quả mẫu
        eval_result = {
            "index": i,
            "original_index": original_idx,
            "question": question,
            "gold_answer": gold_answer,
            "ai_answer": ai_answer,
            "metrics": {
                "bleu4": round(bleu4, 4),
                "rougeL": round(rouge_l, 4),
                "cosine_similarity": round(cosine_sim, 4),
                "faithfulness": judge_data["faithfulness"]["score"],
                "answer_relevance": judge_data["answer_relevance"]["score"],
                "context_relevance": judge_data["context_relevance"]["score"]
            },
            "judge_reasons": {
                "faithfulness": judge_data["faithfulness"].get("reason", ""),
                "answer_relevance": judge_data["answer_relevance"].get("reason", ""),
                "context_relevance": judge_data["context_relevance"].get("reason", "")
            },
            "latencies": {
                "retrieval": round(retrieval_latency, 4),
                "generation": round(generation_latency, 4),
                "judge": round(gemini_latency, 4),
                "total": round(retrieval_latency + generation_latency + gemini_latency, 4)
            }
        }
        
        results.append(eval_result)
        
        # Lưu checkpoint
        save_checkpoint({
            "sampled_indices": sampled_indices,
            "next_index": i + 1,
            "results": results
        })
        
        # In progress
        print(f"    Traditional: BLEU4={bleu4:.3f}, ROUGE-L={rouge_l:.3f}, Cosine={cosine_sim:.3f}")
        print(f"    RAG Triad (1-5): Faithfulness={eval_result['metrics']['faithfulness']}, "
              f"AnswerRel={eval_result['metrics']['answer_relevance']}, ContextRel={eval_result['metrics']['context_relevance']}")
        print(f"    Latency: Retrieval={retrieval_latency:.2f}s, Generation={generation_latency:.2f}s, Judge={gemini_latency:.2f}s")
        
        # Chờ giãn cách 5 giây giữa các mẫu để đảm bảo tần suất gọi dưới 5 RPM theo yêu cầu của user
        time.sleep(5.0)


    # ── 4. Tổng hợp & Xuất báo cáo ────────────────────────────────────────────
    print("\n======================================================================")
    print("  HOÀN THÀNH ĐÁNH GIÁ - ĐANG TỔNG HỢP KẾT QUẢ...")
    print("======================================================================\n")
    
    # Trích xuất mảng điểm
    bleu_scores = [r["metrics"]["bleu4"] for r in results]
    rouge_scores = [r["metrics"]["rougeL"] for r in results]
    cosine_scores = [r["metrics"]["cosine_similarity"] for r in results]
    
    faith_scores = [r["metrics"]["faithfulness"] for r in results]
    ans_rel_scores = [r["metrics"]["answer_relevance"] for r in results]
    ctx_rel_scores = [r["metrics"]["context_relevance"] for r in results]
    
    # Trích xuất độ trễ
    ret_lats = [r["latencies"]["retrieval"] for r in results]
    gen_lats = [r["latencies"]["generation"] for r in results]
    jdg_lats = [r["latencies"]["judge"] for r in results]
    tot_lats = [r["latencies"]["total"] for r in results]
    
    # Hàm tính stats
    def get_stats(arr):
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr))
        }
        
    stats = {
        "bleu4": get_stats(bleu_scores),
        "rougeL": get_stats(rouge_scores),
        "cosine_similarity": get_stats(cosine_scores),
        "faithfulness": get_stats(faith_scores),
        "answer_relevance": get_stats(ans_rel_scores),
        "context_relevance": get_stats(ctx_rel_scores)
    }
    
    # Hàm tính percentile P95
    p95 = lambda arr: float(np.percentile(arr, 95))
    
    # Ghi file JSON chi tiết
    details_path = results_dir / "generation_details.json"
    output_data = {
        "evaluation_timestamp": datetime.now().isoformat(),
        "total_samples": len(results),
        "summary_statistics": stats,
        "latency_statistics": {
            "retrieval": {"mean": float(np.mean(ret_lats)), "p95": p95(ret_lats)},
            "generation": {"mean": float(np.mean(gen_lats)), "p95": p95(gen_lats)},
            "judge": {"mean": float(np.mean(jdg_lats)), "p95": p95(jdg_lats)},
            "total": {"mean": float(np.mean(tot_lats)), "p95": p95(tot_lats)}
        },
        "details": results
    }
    
    with open(details_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    # Tạo báo cáo MD - Điểm số
    scores_md_path = results_dir / "generation_scores.md"
    scores_md_content = f"""# Báo Cáo Đánh Giá Chất Lượng Sinh Câu Trả Lời (RAG Generation)

**Thời gian thực hiện:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Tổng số mẫu đánh giá:** {len(results)} mẫu (ngẫu nhiên từ `test_clean.csv`)  
**Judge LLM:** `gemini-2.5-flash` (LLM-as-a-Judge)

## 1. Kết Quả Điểm Số Đánh Giá

| Chỉ số đánh giá | Điểm Trung Bình | Độ lệch chuẩn (Std Dev) | Nhỏ nhất (Min) | Lớn nhất (Max) |
| :--- | :---: | :---: | :---: | :---: |
| **Traditional N-gram Metrics** | | | | |
| BLEU-4 | {stats['bleu4']['mean']:.4f} | {stats['bleu4']['std']:.4f} | {stats['bleu4']['min']:.4f} | {stats['bleu4']['max']:.4f} |
| ROUGE-L | {stats['rougeL']['mean']:.4f} | {stats['rougeL']['std']:.4f} | {stats['rougeL']['min']:.4f} | {stats['rougeL']['max']:.4f} |
| **Embedding Similarity** | | | | |
| Cosine Similarity (BKAI) | {stats['cosine_similarity']['mean']:.4f} | {stats['cosine_similarity']['std']:.4f} | {stats['cosine_similarity']['min']:.4f} | {stats['cosine_similarity']['max']:.4f} |
| **LLM-as-a-Judge (Thang 1-5)** | | | | |
| Faithfulness (Tính trung thực) | {stats['faithfulness']['mean']:.2f}/5.0 | {stats['faithfulness']['std']:.2f} | {stats['faithfulness']['min']:.1f} | {stats['faithfulness']['max']:.1f} |
| Answer Relevance (Liên quan câu hỏi) | {stats['answer_relevance']['mean']:.2f}/5.0 | {stats['answer_relevance']['std']:.2f} | {stats['answer_relevance']['min']:.1f} | {stats['answer_relevance']['max']:.1f} |
| Context Relevance (Liên quan tài liệu) | {stats['context_relevance']['mean']:.2f}/5.0 | {stats['context_relevance']['std']:.2f} | {stats['context_relevance']['min']:.1f} | {stats['context_relevance']['max']:.1f} |

---

## 2. Nhận Xét & Phân Tích
- **Faithfulness ({stats['faithfulness']['mean']:.2f}/5.0):** Đo lường mức độ trung thực y khoa. Điểm số cao chứng minh hệ thống tuân thủ nghiêm ngặt quy tắc RAG không bịa đặt thông tin.
- **Answer Relevance ({stats['answer_relevance']['mean']:.2f}/5.0):** Đo lường sự tập trung vào câu hỏi của người dùng. Hệ thống có trả lời lạc đề hay đi thẳng vào trọng tâm chuyên môn.
- **Context Relevance ({stats['context_relevance']['mean']:.2f}/5.0):** Thể hiện chất lượng của phần Retrieval. Tài liệu trích xuất có đủ để trả lời câu hỏi hay không.
"""
    with open(scores_md_path, "w", encoding="utf-8") as f:
        f.write(scores_md_content)
        
    # Tạo báo cáo MD - Latency
    latency_md_path = results_dir / "generation_latency.md"
    latency_md_content = f"""# Báo Cáo Hiệu Năng & Độ Trễ (Generation Latency)

**Thời gian thực hiện:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Tổng số mẫu đánh giá:** {len(results)} mẫu  

## 1. Phân Tích Độ Trễ Hệ Thống (Giây)

| Thành phần hệ thống | Thời gian Trung Bình | Percentile P95 |
| :--- | :---: | :---: |
| **Truy xuất tài liệu (Retrieval + Rerank)** | {output_data['latency_statistics']['retrieval']['mean']:.3f}s | {output_data['latency_statistics']['retrieval']['p95']:.3f}s |
| **Sinh câu trả lời (Groq Llama 3.3)** | {output_data['latency_statistics']['generation']['mean']:.3f}s | {output_data['latency_statistics']['generation']['p95']:.3f}s |
| **Đánh giá tự động (Gemini Judge)** | {output_data['latency_statistics']['judge']['mean']:.3f}s | {output_data['latency_statistics']['judge']['p95']:.3f}s |
| **Tổng độ trễ mỗi vòng** | {output_data['latency_statistics']['total']['mean']:.3f}s | {output_data['latency_statistics']['total']['p95']:.3f}s |

---

## 2. Kết Luận Hiệu Năng
- Tốc độ sinh câu trả lời của Groq Llama 3.3 đạt hiệu suất cực kỳ ấn tượng nhờ hạ tầng tăng tốc phần cứng của Groq Cloud.
- Tác vụ đánh giá tự động bằng Gemini Judge chiếm một phần độ trễ đáng kể nhưng chỉ dùng để chạy offline/eval, không ảnh hưởng đến trải nghiệm realtime của người dùng cuối.
"""
    with open(latency_md_path, "w", encoding="utf-8") as f:
        f.write(latency_md_content)

    # Xóa checkpoint khi thành công
    checkpoint_path = get_checkpoint_path()
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        
    print("  ✅ Đã lưu generation_details.json")
    print("  ✅ Đã lưu generation_scores.md")
    print("  ✅ Đã lưu generation_latency.md")
    print("  ✅ Đã dọn dẹp checkpoint file.")
    print("\nChạy đánh giá Lớp 2 hoàn tất thành công!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đánh giá chất lượng sinh câu trả lời RAG (Lớp 2)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng mẫu chạy đánh giá")
    parser.add_argument("--resume", action="store_true", help="Tiếp tục chạy từ checkpoint cũ")
    
    args = parser.parse_args()
    
    setup_logging()
    run_evaluation(args)
