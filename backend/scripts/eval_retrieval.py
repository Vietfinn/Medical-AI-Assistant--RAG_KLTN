"""
Lớp 1: Đánh Giá Hệ Thống Truy Xuất (Retrieval Ablation Study)
================================================================
Chạy 3 cấu hình truy xuất trên toàn bộ test_clean.csv (2,013 mẫu):
  (A) Dense Only — chỉ dùng vietnamese-bi-encoder
  (B) Hybrid RRF — Dense + Sparse (BM25) kết hợp bằng Reciprocal Rank Fusion
  (C) Hybrid RRF + Cohere Reranker — kết quả (B) qua Cohere rerank-v4.0-pro

Metrics: P@1, P@5, P@10, mAP

So sánh Ground Truth bằng NỘI DUNG question text (không dùng doc_id
vì bị trùng lặp giữa train/val/test trong cùng 1 collection Qdrant).

Usage:
    cd backend
    python scripts/eval_retrieval.py                   # chạy đầy đủ 2,013 mẫu
    python scripts/eval_retrieval.py --limit 10        # dry-run 10 mẫu
    python scripts/eval_retrieval.py --configs A B     # chỉ chạy Dense Only + Hybrid
    python scripts/eval_retrieval.py --resume           # tiếp tục từ checkpoint
"""

import argparse
import json
import time
import logging
from pathlib import Path
from datetime import datetime

from qdrant_client import models
import cohere

# Import tiện ích chung (Lớp 0)
from eval_utils import (
    setup_logging,
    load_test_data,
    connect_qdrant,
    init_embedding,
    init_sparse_model,
    ensure_lop1_results_dir,
    is_ground_truth_match,
    timer,
    print_progress,
    RESULTS_DIR,
)

# Import config để lấy Cohere API key
from config import settings

logger = logging.getLogger(__name__)

# ── Hằng số ──────────────────────────────────────────────────────────────────
COLLECTION_NAME = settings.QDRANT_COLLECTION
EVAL_TOP_K = 10          # Số kết quả truy xuất để đánh giá (P@1, P@5, P@10)
PREFETCH_LIMIT = 50      # Số ứng viên mỗi nhánh Dense/Sparse trước khi fusion
K_VALUES = [1, 5, 10]    # Các giá trị K để tính Precision@K
COHERE_RATE_DELAY = 0.7  # Giây giữa mỗi Cohere API call (tránh 429)


# ═══════════════════════════════════════════════════════════════════════════════
# Hàm truy xuất
# ═══════════════════════════════════════════════════════════════════════════════

def search_dense_only(client, dense_vector: list, top_k: int = EVAL_TOP_K) -> list[dict]:
    """
    Cấu hình A: Dense Only — chỉ dùng cosine similarity trên dense vector.
    
    Returns:
        List[dict] — mỗi dict chứa question, answer, score
    """
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=dense_vector,
        using="",             # unnamed vector = default dense
        limit=top_k,
        with_payload=True,
    )
    
    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append({
            "question": payload.get("question", ""),
            "answer": payload.get("answer", ""),
            "doc_id": payload.get("doc_id", ""),
            "score": point.score,
        })
    return results


def search_hybrid_rrf(
    client, dense_vector: list, sparse_vector, top_k: int = EVAL_TOP_K
) -> list[dict]:
    """
    Cấu hình B: Hybrid RRF — Dense + Sparse (BM25) kết hợp bằng RRF server-side.
    
    Returns:
        List[dict] — mỗi dict chứa question, answer, score
    """
    response = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=dense_vector,
                using="",
                limit=PREFETCH_LIMIT,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vector.indices.tolist(),
                    values=sparse_vector.values.tolist(),
                ),
                using="sparse-text",
                limit=PREFETCH_LIMIT,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    
    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append({
            "question": payload.get("question", ""),
            "answer": payload.get("answer", ""),
            "doc_id": payload.get("doc_id", ""),
            "score": point.score,
        })
    return results


def rerank_results(
    cohere_client, query: str, hybrid_results: list[dict], top_k: int = EVAL_TOP_K
) -> list[dict]:
    """
    Cấu hình C: Hybrid RRF + Cohere Reranker.
    Nhận kết quả từ Hybrid RRF, rerank bằng Cohere rerank-v4.0-pro.
    
    Returns:
        List[dict] — đã sắp xếp lại theo relevance score từ Cohere
    """
    if not hybrid_results:
        return []
    
    # Chuẩn bị text cho Cohere (giống reranker.py production)
    doc_texts = []
    for doc in hybrid_results:
        text = f"{doc.get('question', '')} {doc.get('answer', '')}".strip()
        doc_texts.append(text)
    
    response = cohere_client.rerank(
        model=settings.RERANKER_MODEL,
        query=query,
        documents=doc_texts,
        top_n=min(top_k, len(hybrid_results)),
        return_documents=False,
    )
    
    reranked = []
    for item in response.results:
        doc_copy = hybrid_results[item.index].copy()
        doc_copy["rerank_score"] = float(item.relevance_score)
        doc_copy["score"] = float(item.relevance_score)  # ghi đè score
        reranked.append(doc_copy)
    
    return reranked


# ═══════════════════════════════════════════════════════════════════════════════
# Tính metrics
# ═══════════════════════════════════════════════════════════════════════════════

def compute_hit_at_k(results: list[dict], test_item: dict, k: int) -> bool:
    """Kiểm tra Ground Truth có nằm trong top K kết quả không."""
    for doc in results[:k]:
        if is_ground_truth_match(doc, test_item):
            return True
    return False


def find_rank(results: list[dict], test_item: dict) -> int:
    """
    Tìm vị trí (1-indexed) của Ground Truth trong danh sách kết quả.
    Trả về 0 nếu không tìm thấy.
    """
    for i, doc in enumerate(results):
        if is_ground_truth_match(doc, test_item):
            return i + 1  # 1-indexed
    return 0


def compute_average_precision(results: list[dict], test_item: dict) -> float:
    """
    Tính Average Precision cho 1 query.
    Với 1 relevant doc duy nhất: AP = 1/rank nếu tìm thấy, else 0.
    """
    rank = find_rank(results, test_item)
    if rank == 0:
        return 0.0
    return 1.0 / rank


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoint (lưu/đọc tiến trình)
# ═══════════════════════════════════════════════════════════════════════════════

def get_checkpoint_path() -> Path:
    return ensure_lop1_results_dir() / "retrieval_checkpoint.json"


def save_checkpoint(data: dict):
    """Lưu checkpoint sau mỗi batch."""
    path = get_checkpoint_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_checkpoint() -> dict | None:
    """Đọc checkpoint nếu tồn tại."""
    path = get_checkpoint_path()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Vòng lặp đánh giá chính
# ═══════════════════════════════════════════════════════════════════════════════

def run_evaluation(args):
    """Vòng lặp đánh giá chính."""
    
    # ── 1. Setup ─────────────────────────────────────────────────────────────
    results_dir = ensure_lop1_results_dir()
    
    print("=" * 70)
    print("  RETRIEVAL ABLATION STUDY")
    print("=" * 70)
    
    configs_to_run = [c.upper() for c in args.configs]
    print(f"  Cấu hình:  {', '.join(configs_to_run)}")
    print(f"  Top K:     {EVAL_TOP_K}")
    print(f"  Metrics:   P@{', P@'.join(str(k) for k in K_VALUES)}, mAP")
    print()
    
    # ── 2. Load test data ────────────────────────────────────────────────────
    test_data = load_test_data()
    if args.limit:
        test_data = test_data[:args.limit]
    total = len(test_data)
    print(f"  Số mẫu test: {total}")
    print()
    
    # ── 3. Khởi tạo services ────────────────────────────────────────────────
    print("Đang khởi tạo services...")
    
    client = connect_qdrant()
    embedding_svc = init_embedding()
    sparse_model = init_sparse_model()
    
    cohere_client = None
    if "C" in configs_to_run:
        if not settings.COHERE_API_KEY:
            logger.error("COHERE_API_KEY không được cấu hình trong .env")
            return
        cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)
        print("  ✅ Cohere Reranker client initialized")
    
    print("  ✅ Tất cả services đã sẵn sàng")
    print()
    
    # ── 4. Resume từ checkpoint (nếu có) ─────────────────────────────────────
    start_idx = 0
    per_query_results = []
    
    if args.resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            start_idx = checkpoint.get("next_index", 0)
            per_query_results = checkpoint.get("per_query_results", [])
            print(f"  🔄 Tiếp tục từ checkpoint: index={start_idx} ({len(per_query_results)} mẫu đã xong)")
            print()
    
    # ── 5. Vòng lặp chính ───────────────────────────────────────────────────
    latencies = {cfg: [] for cfg in configs_to_run}
    
    for i in range(start_idx, total):
        item = test_data[i]
        query = item["question"]
        
        row_result = {
            "index": i,
            "question": query[:100],  # truncate cho gọn JSON
        }
        
        # ─ Tính embedding (dùng chung cho Dense Only và Hybrid) ──────────
        dense_vector = embedding_svc.encode_query(query).tolist()
        
        sparse_vector = None
        if "B" in configs_to_run or "C" in configs_to_run:
            sparse_list = list(sparse_model.embed([query]))
            sparse_vector = sparse_list[0]
        
        # ─ Config A: Dense Only ─────────────────────────────────────────
        if "A" in configs_to_run:
            t0 = time.time()
            results_a = search_dense_only(client, dense_vector)
            lat_a = time.time() - t0
            latencies["A"].append(lat_a)
            
            rank_a = find_rank(results_a, item)
            row_result["A"] = {
                "rank": rank_a,
                "hit@1": rank_a == 1,
                "hit@5": 0 < rank_a <= 5,
                "hit@10": 0 < rank_a <= 10,
                "ap": compute_average_precision(results_a, item),
                "latency": round(lat_a, 4),
            }
        
        # ─ Config B: Hybrid RRF ─────────────────────────────────────────
        hybrid_results = None
        if "B" in configs_to_run or "C" in configs_to_run:
            t0 = time.time()
            hybrid_results = search_hybrid_rrf(client, dense_vector, sparse_vector)
            lat_b = time.time() - t0
            
            if "B" in configs_to_run:
                latencies["B"].append(lat_b)
                rank_b = find_rank(hybrid_results, item)
                row_result["B"] = {
                    "rank": rank_b,
                    "hit@1": rank_b == 1,
                    "hit@5": 0 < rank_b <= 5,
                    "hit@10": 0 < rank_b <= 10,
                    "ap": compute_average_precision(hybrid_results, item),
                    "latency": round(lat_b, 4),
                }
        
        # ─ Config C: Hybrid RRF + Reranker ──────────────────────────────
        if "C" in configs_to_run and hybrid_results is not None:
            t0 = time.time()
            try:
                reranked = rerank_results(cohere_client, query, hybrid_results)
                lat_c = time.time() - t0
                latencies["C"].append(lat_c)
                
                rank_c = find_rank(reranked, item)
                row_result["C"] = {
                    "rank": rank_c,
                    "hit@1": rank_c == 1,
                    "hit@5": 0 < rank_c <= 5,
                    "hit@10": 0 < rank_c <= 10,
                    "ap": compute_average_precision(reranked, item),
                    "latency": round(lat_c, 4),
                }
            except Exception as e:
                logger.warning(f"Cohere rerank lỗi ở mẫu {i}: {e}")
                row_result["C"] = {"rank": 0, "hit@1": False, "hit@5": False, "hit@10": False, "ap": 0, "error": str(e)}
            
            # Rate limiting cho Cohere API
            time.sleep(COHERE_RATE_DELAY)
        
        per_query_results.append(row_result)
        
        # ─ Progress & Checkpoint ────────────────────────────────────────
        print_progress(i + 1, total, prefix="Evaluating", every=50)
        
        if (i + 1) % 100 == 0:
            save_checkpoint({
                "next_index": i + 1,
                "per_query_results": per_query_results,
                "configs": configs_to_run,
                "timestamp": datetime.now().isoformat(),
            })
    
    print()
    print("✅ Đánh giá hoàn tất! Đang tính toán metrics...")
    print()
    
    # ── 6. Tính tổng hợp metrics ────────────────────────────────────────────
    metrics = {}
    
    for cfg in configs_to_run:
        cfg_results = [r[cfg] for r in per_query_results if cfg in r]
        n = len(cfg_results)
        if n == 0:
            continue
        
        p_at = {}
        for k in K_VALUES:
            # P@K = tỷ lệ câu hỏi mà ground truth nằm trong top K
            hit_key = f"hit@{k}" if k > 1 else "hit@1"
            # Cần tính lại: hit@K = rank nằm trong [1, K]
            hits = sum(1 for r in cfg_results if 0 < r["rank"] <= k)
            p_at[k] = hits / n * 100
        
        aps = [r["ap"] for r in cfg_results]
        mean_ap = sum(aps) / n * 100
        
        # Latency stats
        lats = latencies.get(cfg, [])
        avg_lat = sum(lats) / len(lats) if lats else 0
        p95_lat = sorted(lats)[int(len(lats) * 0.95)] if lats else 0
        
        metrics[cfg] = {
            "n": n,
            "P@1": round(p_at[1], 2),
            "P@5": round(p_at[5], 2),
            "P@10": round(p_at[10], 2),
            "mAP": round(mean_ap, 2),
            "avg_latency_ms": round(avg_lat * 1000, 1),
            "p95_latency_ms": round(p95_lat * 1000, 1),
        }
    
    # ── 7. Xuất kết quả ─────────────────────────────────────────────────────
    config_labels = {
        "A": "Dense Only (vi-bi-encoder)",
        "B": "Hybrid RRF (Dense + BM25)",
        "C": "Hybrid RRF + Cohere Reranker",
    }
    
    # 7a. Bảng Ablation Study (Markdown)
    ablation_md = generate_ablation_markdown(metrics, config_labels, total)
    ablation_path = results_dir / "retrieval_ablation.md"
    with open(ablation_path, "w", encoding="utf-8") as f:
        f.write(ablation_md)
    print(f"📄 Bảng Ablation Study → {ablation_path}")
    
    # 7b. Bảng Latency (Markdown)
    latency_md = generate_latency_markdown(metrics, config_labels)
    latency_path = results_dir / "retrieval_latency.md"
    with open(latency_path, "w", encoding="utf-8") as f:
        f.write(latency_md)
    print(f"📄 Bảng Latency → {latency_path}")
    
    # 7c. JSON chi tiết
    detail_path = results_dir / "retrieval_ablation.json"
    output_json = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "total_samples": total,
            "eval_top_k": EVAL_TOP_K,
            "configs": configs_to_run,
            "collection": COLLECTION_NAME,
            "embedding_model": settings.EMBEDDING_MODEL,
            "reranker_model": settings.RERANKER_MODEL,
        },
        "metrics": metrics,
        "per_query": per_query_results,
    }
    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)
    print(f"📄 Chi tiết JSON → {detail_path}")
    
    # 7d. In bảng ra console
    print()
    print(ablation_md)
    print(latency_md)
    
    # ── 8. Dọn checkpoint ───────────────────────────────────────────────────
    checkpoint_path = get_checkpoint_path()
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.info("Đã xóa checkpoint file (đánh giá hoàn tất)")


# ═══════════════════════════════════════════════════════════════════════════════
# Tạo bảng Markdown
# ═══════════════════════════════════════════════════════════════════════════════

def generate_ablation_markdown(metrics: dict, labels: dict, total: int) -> str:
    """Tạo bảng Ablation Study dạng Markdown (copy thẳng vào KLTN)."""
    lines = [
        f"# Retrieval Ablation Study",
        f"",
        f"> Đánh giá trên **{total}** mẫu từ `test_clean.csv`",
        f"> Collection: `{COLLECTION_NAME}` ({settings.EMBEDDING_MODEL})",
        f"> Ngày chạy: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"| Cấu hình | P@1 (%) | P@5 (%) | P@10 (%) | mAP (%) |",
        f"|:---|:---:|:---:|:---:|:---:|",
    ]
    
    # Baseline từ bài báo SPBERTQA (để so sánh)
    lines.append(f"| BM25 (SPBERTQA Baseline) | 44.96 | — | 70.09 | 56.93 |")
    lines.append(f"| SPBERTQA (Best Baseline) | 50.92 | — | 83.76 | 62.25 |")
    
    for cfg in ["A", "B", "C"]:
        if cfg in metrics:
            m = metrics[cfg]
            label = labels.get(cfg, cfg)
            lines.append(
                f"| **{label}** | **{m['P@1']:.2f}** | **{m['P@5']:.2f}** | **{m['P@10']:.2f}** | **{m['mAP']:.2f}** |"
            )
    
    lines.append("")
    return "\n".join(lines)


def generate_latency_markdown(metrics: dict, labels: dict) -> str:
    """Tạo bảng Latency dạng Markdown."""
    lines = [
        f"## Retrieval Latency",
        f"",
        f"| Cấu hình | Avg Latency (ms) | P95 Latency (ms) |",
        f"|:---|:---:|:---:|",
    ]
    
    for cfg in ["A", "B", "C"]:
        if cfg in metrics:
            m = metrics[cfg]
            label = labels.get(cfg, cfg)
            lines.append(f"| {label} | {m['avg_latency_ms']:.1f} | {m['p95_latency_ms']:.1f} |")
    
    lines.append("")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Retrieval Ablation Study — Đánh giá hệ thống truy xuất AIMCare"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Giới hạn số mẫu test (dry-run). Mặc định: chạy hết 2,013 mẫu."
    )
    parser.add_argument(
        "--configs", nargs="+", default=["A", "B", "C"],
        choices=["A", "B", "C", "a", "b", "c"],
        help="Chọn cấu hình cần chạy. Mặc định: A B C (tất cả)."
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Tiếp tục từ checkpoint (nếu bị crash giữa chừng)."
    )
    return parser.parse_args()


if __name__ == "__main__":
    setup_logging()
    args = parse_args()
    
    with timer("Tổng thời gian đánh giá"):
        run_evaluation(args)
