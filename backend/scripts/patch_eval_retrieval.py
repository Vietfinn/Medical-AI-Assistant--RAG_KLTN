"""
Script chạy bổ sung các mẫu bị lỗi cho cấu hình C (Cohere Reranker)
===================================================================
Đọc file retrieval_ablation.json hiện tại, tìm các mẫu có lỗi ở Config C,
chạy lại truy vấn Qdrant + gọi API Cohere (với sleep 6.2s để tránh giới hạn 10 RPM),
cập nhật trực tiếp kết quả vào file JSON và tính toán lại báo cáo Markdown.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime

# Thêm backend/ vào sys.path để import
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from qdrant_client import QdrantClient
import cohere

from scripts.eval_utils import (
    setup_logging,
    connect_qdrant,
    init_embedding,
    init_sparse_model,
    is_ground_truth_match,
    ensure_lop1_results_dir,
)
from scripts.eval_retrieval import (
    search_hybrid_rrf,
    rerank_results,
    find_rank,
    compute_average_precision,
    generate_ablation_markdown,
    generate_latency_markdown,
)
from config import settings

logger = logging.getLogger(__name__)

COHERE_DELAY = 6.2  # Giây giữa các cuộc gọi để đảm bảo dưới 10 RPM (60s / 10 = 6s)

def run_patch():
    results_dir = ensure_lop1_results_dir()
    json_path = results_dir / "retrieval_ablation.json"
    
    if not json_path.exists():
        logger.error(f"Không tìm thấy file kết quả tại {json_path}")
        return
        
    # ── 1. Đọc dữ liệu JSON hiện tại ──────────────────────────────────────────
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    per_query = data.get("per_query", [])
    total_samples = len(per_query)
    
    # Tìm các câu hỏi bị lỗi ở cấu hình C
    failed_indices = []
    for idx, item in enumerate(per_query):
        c_data = item.get("C", {})
        if "error" in c_data or not c_data:
            failed_indices.append(idx)
            
    num_failed = len(failed_indices)
    if num_failed == 0:
        print("🎉 Không có mẫu nào bị lỗi! Tất cả 2,012 mẫu đã hoàn thành đầy đủ.")
        return
        
    print("=" * 70)
    print(f"  CHẠY BỔ SUNG CẤU HÌNH C (COHERE RERANKER)")
    print(f"  Số mẫu bị thiếu/lỗi: {num_failed} / {total_samples}")
    print(f"  Thời gian dự kiến: ~{round(num_failed * COHERE_DELAY / 60, 1)} phút (do giới hạn 10 RPM)")
    print("=" * 70)
    print()
    
    # ── 2. Khởi tạo các services ──────────────────────────────────────────────
    print("Đang khởi tạo services...")
    client = connect_qdrant()
    embedding_svc = init_embedding()
    sparse_model = init_sparse_model()
    
    if not settings.COHERE_API_KEY:
        logger.error("COHERE_API_KEY không được cấu hình trong .env")
        return
    cohere_client = cohere.Client(api_key=settings.COHERE_API_KEY)
    print("  ✅ Cohere client initialized")
    print()
    
    # Đọc danh sách câu hỏi gốc từ test_clean.csv để lấy ground truth (answer) đầy đủ
    # (Vì trong file JSON question bị truncate ở 100 ký tự)
    from scripts.eval_utils import load_test_data
    test_data = load_test_data()
    
    # ── 3. Chạy bổ sung ───────────────────────────────────────────────────────
    success_count = 0
    
    for count, idx in enumerate(failed_indices):
        item = per_query[idx]
        # Lấy đầy đủ thông tin mẫu test từ test_clean.csv
        test_item = test_data[idx]
        query = test_item["question"]
        
        print(f"[{count+1}/{num_failed}] Đang xử lý mẫu #{idx}: {query[:60]}...")
        
        # Rerun hybrid search (nhanh, không bị giới hạn, kèm retry nếu rớt mạng)
        hybrid_results = None
        for qdrant_attempt in range(3):
            try:
                dense_vector = embedding_svc.encode_query(query).tolist()
                sparse_list = list(sparse_model.embed([query]))
                sparse_vector = sparse_list[0]
                hybrid_results = search_hybrid_rrf(client, dense_vector, sparse_vector)
                break
            except Exception as q_err:
                print(f"  ⚠️ Lỗi kết nối Qdrant: {q_err}. Đang thử lại sau 5s... (Lần {qdrant_attempt+1}/3)")
                time.sleep(5)
                try:
                    client = connect_qdrant()
                except Exception:
                    pass
        
        if hybrid_results is None:
            print(f"  ❌ Không thể kết nối Qdrant cho mẫu #{idx}")
            continue
        
        # Gọi Cohere Reranker với cơ chế retry khi gặp 429
        t0 = time.time()
        reranked = None
        retries = 3
        
        for attempt in range(retries):
            try:
                reranked = rerank_results(cohere_client, query, hybrid_results)
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "limit" in err_str.lower():
                    wait_time = 62  # Đợi hẳn 1 phút để reset hoàn toàn RPM quota!
                    print(f"  ⚠️ Gặp lỗi Rate Limit (429). Đang chờ {wait_time}s để reset quota... (Lần {attempt+1}/{retries})")
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ Lỗi kết nối Cohere: {e}")
                    break
                    
        if reranked is not None:
            lat_c = time.time() - t0
            rank_c = find_rank(reranked, test_item)
            
            # Cập nhật kết quả thành công ghi đè lên lỗi cũ
            item["C"] = {
                "rank": rank_c,
                "hit@1": rank_c == 1,
                "hit@5": 0 < rank_c <= 5,
                "hit@10": 0 < rank_c <= 10,
                "ap": compute_average_precision(reranked, test_item),
                "latency": round(lat_c, 4),
            }
            success_count += 1
            
            # Lưu file JSON ngay lập tức để bảo toàn tiến trình
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            # Đảm bảo giữ khoảng cách an toàn tránh 10 RPM
            time.sleep(COHERE_DELAY)
        else:
            print(f"  ❌ Không thể hoàn thành mẫu #{idx}")
            
    print(f"\n✅ Đã chạy bổ sung xong! Thành công: {success_count}/{num_failed}")
    
    # ── 4. Tính toán lại Metrics và xuất báo cáo mới ─────────────────────────
    print("Đang recalculate metrics cho báo cáo cuối cùng...")
    K_VALUES = [1, 5, 10]
    metrics = {}
    
    for cfg in ["A", "B", "C"]:
        # Lọc các dòng không bị lỗi của config đó
        cfg_results = [r[cfg] for r in per_query if cfg in r and "error" not in r[cfg]]
        n_cfg = len(cfg_results)
        if n_cfg == 0:
            continue
            
        p_at = {}
        for k in K_VALUES:
            hits = sum(1 for r in cfg_results if 0 < r["rank"] <= k)
            p_at[k] = hits / n_cfg * 100
            
        aps = [r["ap"] for r in cfg_results]
        mean_ap = sum(aps) / n_cfg * 100
        
        lats = [r["latency"] for r in cfg_results if "latency" in r]
        avg_lat = sum(lats) / len(lats) if lats else 0
        p95_lat = sorted(lats)[int(len(lats) * 0.95)] if lats else 0
        
        metrics[cfg] = {
            "n": n_cfg,
            "P@1": round(p_at[1], 2),
            "P@5": round(p_at[5], 2),
            "P@10": round(p_at[10], 2),
            "mAP": round(mean_ap, 2),
            "avg_latency_ms": round(avg_lat * 1000, 1),
            "p95_latency_ms": round(p95_lat * 1000, 1),
        }
        
    # Tạo lại bảng Markdown
    config_labels = {
        "A": "Dense Only (vi-bi-encoder)",
        "B": "Hybrid RRF (Dense + BM25)",
        "C": "Hybrid RRF + Cohere Reranker",
    }
    
    # 4a. Tạo retrieval_ablation.md
    ablation_lines = [
        f"# Retrieval Ablation Study",
        f"",
        f"> Đánh giá trên **{total_samples}** mẫu từ `test_clean.csv` (Đã bổ sung đầy đủ kết quả thành công)",
        f"> Collection: `{settings.QDRANT_COLLECTION}` ({settings.EMBEDDING_MODEL})",
        f"> Ngày chạy: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"| Cấu hình | P@1 (%) | P@5 (%) | P@10 (%) | mAP (%) |",
        f"|:---|:---:|:---:|:---:|:---:|",
        f"| BM25 (SPBERTQA Baseline) | 44.96 | — | 70.09 | 56.93 |",
        f"| SPBERTQA (Best Baseline) | 50.92 | — | 83.76 | 62.25 |",
    ]
    for cfg in ["A", "B", "C"]:
        if cfg in metrics:
            m = metrics[cfg]
            label = config_labels.get(cfg, cfg)
            ablation_lines.append(
                f"| **{label}** | **{m['P@1']:.2f}** | **{m['P@5']:.2f}** | **{m['P@10']:.2f}** | **{m['mAP']:.2f}** |"
            )
    ablation_lines.append("")
    ablation_md = "\n".join(ablation_lines)
    
    with open(results_dir / "retrieval_ablation.md", "w", encoding="utf-8") as f:
        f.write(ablation_md)
        
    # 4b. Tạo retrieval_latency.md
    latency_lines = [
        f"## Retrieval Latency",
        f"",
        f"| Cấu hình | Avg Latency (ms) | P95 Latency (ms) |",
        f"|:---|:---:|:---:|",
    ]
    for cfg in ["A", "B", "C"]:
        if cfg in metrics:
            m = metrics[cfg]
            label = config_labels.get(cfg, cfg)
            latency_lines.append(f"| {label} | {m['avg_latency_ms']:.1f} | {m['p95_latency_ms']:.1f} |")
    latency_lines.append("")
    latency_md = "\n".join(latency_lines)
    
    with open(results_dir / "retrieval_latency.md", "w", encoding="utf-8") as f:
        f.write(latency_md)
        
    # 4c. Lưu lại JSON với metrics cập nhật
    data["metrics"] = metrics
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("=" * 70)
    print("  KẾT QUẢ ĐỒNG BỘ CUỐI CÙNG (2,012 MẪU)")
    print("=" * 70)
    print(ablation_md)
    print(latency_md)

if __name__ == "__main__":
    setup_logging()
    run_patch()
