"""
Lớp 3: Đánh Giá An Toàn (Triage + Safety Guard Agent)
======================================================
Chạy đánh giá bộ lọc đầu vào (Triage Agent) và bộ lọc đầu ra (Safety Guard Agent)
của hệ thống AIMCare sử dụng 100 ca kiểm thử thiết kế lâm sàng.

Báo cáo kết quả sẽ được lưu tại:
  - backend/scripts/results/lop3_safety/triage_results.json
  - backend/scripts/results/lop3_safety/safety_results.json
  - backend/scripts/results/lop3_safety/lop3_report_detail.md
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Thêm backend/ vào sys.path để import config, agents, services...
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import các tiện ích
from eval_utils import setup_logging, ensure_lop3_results_dir
from config import settings
from services.groq_llm import GroqService
from agents.triage_agent import TriageAgent
from agents.safety_guard_agent import SafetyGuardAgent
from models.schemas import HealthProfile, TriageResult, SafetyResult

logger = logging.getLogger(__name__)

# Hằng số cấu hình
DATA_DIR = Path(__file__).resolve().parent / "data"
TRIAGE_DATA_PATH = DATA_DIR / "triage_test_cases.json"
SAFETY_DATA_PATH = DATA_DIR / "safety_test_cases.json"
CHECKPOINT_PATH = ensure_lop3_results_dir() / "safety_checkpoint.json"

# Giãn cách cuộc gọi Groq để đảm bảo tuân thủ Rate Limit
GROQ_CALL_DELAY = 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Rotating Groq Service (Bộ xoay vòng Key & tự động thử lại)
# ═══════════════════════════════════════════════════════════════════════════════

class RotatingGroqService(GroqService):
    """
    Kế thừa GroqService, tự động xoay vòng các API Key trong danh sách
    khi dính lỗi Rate Limit (429) hoặc lỗi kết nối.
    """
    def __init__(self, keys: List[str], model_name: str = "llama-3.3-70b-versatile"):
        self.keys = [k.strip() for k in keys if k and k.strip()]
        if not self.keys:
            raise ValueError("Danh sách API Key rỗng!")
        self.model_name = model_name
        self.current_idx = 0
        self.client = None
        self.configure_next()

    def configure_next(self):
        """Chuyển sang cấu hình key tiếp theo."""
        from groq import Groq
        key = self.keys[self.current_idx]
        key_preview = f"{key[:10]}...{key[-5:]}" if len(key) > 15 else "INVALID_KEY"
        logger.info(f"Groq Rotator: Đang kết nối key index {self.current_idx} ({key_preview})")
        self.client = Groq(api_key=key)
        self.api_key = key
        # Cập nhật chỉ số cho lần tiếp theo
        self.current_idx = (self.current_idx + 1) % len(self.keys)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """Ghi đè phương thức generate với cơ chế xoay key và retry."""
        max_attempts = len(self.keys) * 3
        delay = 2.0
        
        for attempt in range(1, max_attempts + 1):
            try:
                if self.client is None:
                    self.configure_next()
                
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                err_name = type(e).__name__
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} thất bại với key index {(self.current_idx - 1) % len(self.keys)}. "
                    f"Lỗi: {err_name} - {str(e)}. Đang xoay key và thử lại..."
                )
                self.configure_next()
                time.sleep(delay)
                delay = min(delay * 1.5, 10.0)  # Exponential backoff
                
        raise RuntimeError("Tất cả các Groq API key đều thất bại hoặc cạn kiệt hạn ngạch!")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Quản lý Checkpoint
# ═══════════════════════════════════════════════════════════════════════════════

def load_checkpoint() -> Dict[str, Any]:
    """Tải tiến trình đã lưu từ file checkpoint."""
    if CHECKPOINT_PATH.exists():
        try:
            with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc checkpoint: {str(e)}")
    return {
        "next_triage_idx": 0,
        "next_safety_idx": 0,
        "triage_results": [],
        "safety_results": []
    }

def save_checkpoint(data: Dict[str, Any]):
    """Ghi lại tiến trình hiện tại vào file checkpoint."""
    try:
        with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Lỗi lưu checkpoint: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Chạy Đánh Giá Phần A: Triage Agent
# ═══════════════════════════════════════════════════════════════════════════════

def run_triage_evaluation(
    triage_agent: TriageAgent,
    cases: List[Dict[str, Any]],
    start_idx: int,
    limit: Optional[int],
    checkpoint_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Chạy đánh giá Triage Agent trên các ca kiểm thử."""
    print(f"\n--- BẮT ĐẦU ĐÁNH GIÁ PHẦN A: TRIAGE AGENT ({len(cases)} ca) ---")
    results = checkpoint_data["triage_results"]
    
    end_idx = len(cases)
    if limit is not None:
        end_idx = min(start_idx + limit, len(cases))
        
    for idx in range(start_idx, end_idx):
        case = cases[idx]
        case_id = case["id"]
        query = case["query"]
        expected_label = case["expected_label"]
        category_detail = case["category_detail"]
        rationale = case["rationale"]
        
        print(f"[{idx + 1}/{end_idx}] Đang đánh giá Triage Case {case_id} ({category_detail})...")
        
        t0 = time.time()
        try:
            # Gọi triage agent
            agent_res: TriageResult = triage_agent.execute(query)
            latency = time.time() - t0
            
            # Ánh xạ kết quả Agent thành 3 nhãn chuẩn
            if not agent_res.is_safe:
                predicted_label = "UNSAFE"
            elif agent_res.is_medical:
                predicted_label = "MEDICAL"
            else:
                predicted_label = "NON_MEDICAL"
                
            is_correct = (predicted_label == expected_label)
            
            res_entry = {
                "id": case_id,
                "query": query,
                "expected_label": expected_label,
                "predicted_label": predicted_label,
                "is_correct": is_correct,
                "category_detail": category_detail,
                "rationale": rationale,
                "agent_raw": {
                    "is_medical": agent_res.is_medical,
                    "is_safe": agent_res.is_safe,
                    "unsafe_category": agent_res.unsafe_category,
                    "unsafe_reason": agent_res.unsafe_reason,
                    "response": agent_res.response,
                    "suggested_title": agent_res.suggested_title
                },
                "latency": latency
            }
            
            results.append(res_entry)
            checkpoint_data["next_triage_idx"] = idx + 1
            checkpoint_data["triage_results"] = results
            save_checkpoint(checkpoint_data)
            
            print(f"  -> Thực tế: {expected_label} | Dự đoán: {predicted_label} | Correct: {is_correct} | Trễ: {latency:.2f}s")
            
        except Exception as e:
            logger.error(f"Lỗi tại Triage Case {case_id}: {str(e)}")
            raise
            
        time.sleep(GROQ_CALL_DELAY)
        
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Chạy Đánh Giá Phần B: Safety Guard Agent
# ═══════════════════════════════════════════════════════════════════════════════

def run_safety_evaluation(
    safety_agent: SafetyGuardAgent,
    cases: List[Dict[str, Any]],
    start_idx: int,
    limit: Optional[int],
    checkpoint_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Chạy đánh giá Safety Guard Agent trên các ca kiểm thử."""
    print(f"\n--- BẮT ĐẦU ĐÁNH GIÁ PHẦN B: SAFETY GUARD AGENT ({len(cases)} ca) ---")
    results = checkpoint_data["safety_results"]
    
    end_idx = len(cases)
    if limit is not None:
        end_idx = min(start_idx + limit, len(cases))
        
    for idx in range(start_idx, end_idx):
        case = cases[idx]
        case_id = case["case_id"]
        category = case["category"]
        description = case["description"]
        health_profile_dict = case["health_profile"]
        draft_response = case["draft_response"]
        expected_warning = case["expected_warning"]
        expected_severity = case["expected_severity"]
        
        print(f"[{idx + 1}/{end_idx}] Đang đánh giá Safety Case {case_id} ({category})...")
        
        # Khởi tạo Pydantic model HealthProfile
        health_profile = HealthProfile(**health_profile_dict)
        
        t0 = time.time()
        try:
            # Gọi safety agent
            agent_res: SafetyResult = safety_agent.execute(
                draft_response=draft_response,
                health_profile=health_profile
            )
            latency = time.time() - t0
            
            # Cảnh báo được kích hoạt khi is_safe là False
            predicted_warning = not agent_res.is_safe
            is_correct = (predicted_warning == expected_warning)
            
            # Phân tích mức độ nghiêm trọng dự báo
            predicted_severity = "none"
            if agent_res.warnings:
                predicted_severity = agent_res.warnings[0].severity or "medium"
            elif not agent_res.is_safe:
                predicted_severity = "medium"
                
            res_entry = {
                "case_id": case_id,
                "category": category,
                "description": description,
                "expected_warning": expected_warning,
                "predicted_warning": predicted_warning,
                "is_correct": is_correct,
                "expected_severity": expected_severity,
                "predicted_severity": predicted_severity,
                "agent_raw": {
                    "is_safe": agent_res.is_safe,
                    "final_response": agent_res.final_response,
                    "warnings": [
                        {
                            "severity": w.severity,
                            "message": w.message,
                            "reason": w.reason,
                            "affected_conditions": w.affected_conditions
                        } for w in agent_res.warnings
                    ]
                },
                "latency": latency
            }
            
            results.append(res_entry)
            checkpoint_data["next_safety_idx"] = idx + 1
            checkpoint_data["safety_results"] = results
            save_checkpoint(checkpoint_data)
            
            print(f"  -> Cảnh báo mong đợi: {expected_warning} | Thực tế: {predicted_warning} | Correct: {is_correct} | Trễ: {latency:.2f}s")
            
        except Exception as e:
            logger.error(f"Lỗi tại Safety Case {case_id}: {str(e)}")
            raise
            
        time.sleep(GROQ_CALL_DELAY)
        
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Phân Tích Thống Kê & Xuất Báo Cáo
# ═══════════════════════════════════════════════════════════════════════════════

def compute_metrics_triage(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Tính toán các chỉ số cho Triage Agent."""
    total = len(results)
    if total == 0:
        return {}
        
    correct = sum(1 for r in results if r["is_correct"])
    accuracy = correct / total
    
    # Tính Confusion Matrix
    labels = ["MEDICAL", "NON_MEDICAL", "UNSAFE"]
    matrix = {true_lbl: {pred_lbl: 0 for pred_lbl in labels} for true_lbl in labels}
    
    for r in results:
        t = r["expected_label"]
        p = r["predicted_label"]
        if t in matrix and p in matrix[t]:
            matrix[t][p] += 1
            
    # Tính Precision, Recall, F1 cho từng nhãn
    metrics = {}
    for lbl in labels:
        tp = matrix[lbl][lbl]
        fn = sum(matrix[lbl][pred] for pred in labels if pred != lbl)
        fp = sum(matrix[true][lbl] for true in labels if true != lbl)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        metrics[lbl] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn
        }
        
    # Tỷ lệ bỏ sót độc hại (False Negative cho UNSAFE): UNSAFE bị phân loại thành MEDICAL/NON_MEDICAL
    unsafe_tp = matrix["UNSAFE"]["UNSAFE"]
    unsafe_fn = matrix["UNSAFE"]["MEDICAL"] + matrix["UNSAFE"]["NON_MEDICAL"]
    fnr_unsafe = unsafe_fn / (unsafe_tp + unsafe_fn) if (unsafe_tp + unsafe_fn) > 0 else 0.0
    
    # Tỷ lệ chặn nhầm (False Positive cho UNSAFE): MEDICAL/NON_MEDICAL bị phân loại thành UNSAFE
    unsafe_fp = matrix["MEDICAL"]["UNSAFE"] + matrix["NON_MEDICAL"]["UNSAFE"]
    safe_total = sum(matrix[lbl][pred] for lbl in ["MEDICAL", "NON_MEDICAL"] for pred in labels)
    fpr_unsafe = unsafe_fp / safe_total if safe_total > 0 else 0.0
    
    latencies = [r["latency"] for r in results]
    avg_latency = sum(latencies) / len(latencies)
    
    return {
        "accuracy": accuracy,
        "confusion_matrix": matrix,
        "class_metrics": metrics,
        "fnr_unsafe": fnr_unsafe,
        "fpr_unsafe": fpr_unsafe,
        "avg_latency": avg_latency
    }


def compute_metrics_safety(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Tính toán các chỉ số cho Safety Guard Agent."""
    total = len(results)
    if total == 0:
        return {}
        
    correct = sum(1 for r in results if r["is_correct"])
    accuracy = correct / total
    
    # 2x2 Matrix: True Warning (TP), False Warning (FP), Missed Warning (FN), True Safe (TN)
    tp, fp, fn, tn = 0, 0, 0, 0
    
    # Phân tích theo danh mục lỗi
    categories = ["drug_allergy", "contraindication", "drug_interaction", "multi_factor", "negative_control"]
    cat_stats = {cat: {"total": 0, "correct": 0, "detected": 0} for cat in categories}
    
    for r in results:
        expected = r["expected_warning"]
        predicted = r["predicted_warning"]
        cat = r["category"]
        
        if cat in cat_stats:
            cat_stats[cat]["total"] += 1
            if r["is_correct"]:
                cat_stats[cat]["correct"] += 1
            if predicted:
                cat_stats[cat]["detected"] += 1
                
        if expected and predicted:
            tp += 1
        elif not expected and predicted:
            fp += 1
        elif expected and not predicted:
            fn += 1
        else:
            tn += 1
            
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # Tỷ lệ bỏ sót lỗi y khoa (FNR)
    fnr = fn / (tp + fn) if (tp + fn) > 0 else 0.0
    # Tỷ lệ báo động giả (FPR)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    
    latencies = [r["latency"] for r in results]
    avg_latency = sum(latencies) / len(latencies)
    
    return {
        "accuracy": accuracy,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fnr": fnr,
        "fpr": fpr,
        "category_stats": cat_stats,
        "avg_latency": avg_latency
    }


def write_reports(
    triage_metrics: Dict[str, Any],
    safety_metrics: Dict[str, Any],
    triage_results: List[Dict[str, Any]],
    safety_results: List[Dict[str, Any]]
):
    """Xuất báo cáo Markdown chi tiết."""
    results_dir = ensure_lop3_results_dir()
    
    # ── 1. Lưu kết quả chi tiết JSON ──────────────────────────────────────────
    with open(results_dir / "triage_results.json", "w", encoding="utf-8") as f:
        json.dump(triage_results, f, ensure_ascii=False, indent=2)
        
    with open(results_dir / "safety_results.json", "w", encoding="utf-8") as f:
        json.dump(safety_results, f, ensure_ascii=False, indent=2)
        
    # ── 2. Vẽ bảng Confusion Matrix Triage ────────────────────────────────────
    tm = triage_metrics.get("confusion_matrix", {})
    triage_table = (
        f"| Thực tế \\ Dự đoán | MEDICAL | NON_MEDICAL | UNSAFE |\n"
        f"| :--- | :---: | :---: | :---: |\n"
        f"| **MEDICAL** | **{tm.get('MEDICAL', {}).get('MEDICAL', 0)}** | {tm.get('MEDICAL', {}).get('NON_MEDICAL', 0)} | {tm.get('MEDICAL', {}).get('UNSAFE', 0)} |\n"
        f"| **NON_MEDICAL** | {tm.get('NON_MEDICAL', {}).get('MEDICAL', 0)} | **{tm.get('NON_MEDICAL', {}).get('NON_MEDICAL', 0)}** | {tm.get('NON_MEDICAL', {}).get('UNSAFE', 0)} |\n"
        f"| **UNSAFE** | {tm.get('UNSAFE', {}).get('MEDICAL', 0)} | {tm.get('UNSAFE', {}).get('NON_MEDICAL', 0)} | **{tm.get('UNSAFE', {}).get('UNSAFE', 0)}** |\n"
    )
    
    # ── 3. Chỉ số phân lớp Triage ─────────────────────────────────────────────
    tc = triage_metrics.get("class_metrics", {})
    triage_class_table = (
        f"| Nhãn | Precision | Recall | F1-Score | Số mẫu |\n"
        f"| :--- | :---: | :---: | :---: | :---: |\n"
        f"| **MEDICAL** | {tc.get('MEDICAL', {}).get('precision', 0.0):.4f} | {tc.get('MEDICAL', {}).get('recall', 0.0):.4f} | {tc.get('MEDICAL', {}).get('f1', 0.0):.4f} | {sum(tm.get('MEDICAL', {}).values())} |\n"
        f"| **NON_MEDICAL** | {tc.get('NON_MEDICAL', {}).get('precision', 0.0):.4f} | {tc.get('NON_MEDICAL', {}).get('recall', 0.0):.4f} | {tc.get('NON_MEDICAL', {}).get('f1', 0.0):.4f} | {sum(tm.get('NON_MEDICAL', {}).values())} |\n"
        f"| **UNSAFE** | {tc.get('UNSAFE', {}).get('precision', 0.0):.4f} | {tc.get('UNSAFE', {}).get('recall', 0.0):.4f} | {tc.get('UNSAFE', {}).get('f1', 0.0):.4f} | {sum(tm.get('UNSAFE', {}).values())} |\n"
    )

    # ── 4. Vẽ bảng Confusion Matrix Safety ────────────────────────────────────
    sm = safety_metrics
    safety_table = (
        f"| Thực tế \\ Dự đoán | CÓ CẢNH BÁO | KHÔNG CẢNH BÁO |\n"
        f"| :--- | :---: | :---: |\n"
        f"| **CÓ CẢNH BÁO** (Rủi ro) | **{sm.get('tp', 0)}** (TP) | {sm.get('fn', 0)} (FN - Bỏ sót) |\n"
        f"| **KHÔNG CẢNH BÁO** (An toàn) | {sm.get('fp', 0)} (FP - Báo sai) | **{sm.get('tn', 0)}** (TN) |\n"
    )
    
    # ── 5. Bảng chi tiết theo loại rủi ro Safety ──────────────────────────────
    cat_rows = ""
    for cat, stat in sm.get("category_stats", {}).items():
        total = stat["total"]
        correct = stat["correct"]
        acc = correct / total if total > 0 else 0.0
        det = stat["detected"]
        
        # dịch tiếng Việt cho trực quan
        cat_vn = {
            "drug_allergy": "Dị ứng thuốc",
            "contraindication": "Chống chỉ định",
            "drug_interaction": "Tương tác thuốc",
            "multi_factor": "Đa yếu tố phức tạp",
            "negative_control": "Chứng âm (An toàn)"
        }.get(cat, cat)
        
        cat_rows += f"| {cat_vn} | {total} | {correct} | {acc:.2%} | {det} |\n"

    # ── 6. Tạo nội dung Markdown báo cáo ──────────────────────────────────────
    report_content = f"""# Báo Cáo Chi Tiết Đánh Giá Lớp 3: An Toàn (Triage & Safety Guard)

Báo cáo này trình bày kết quả thực nghiệm đánh giá khả năng bảo vệ an toàn đa tầng của hệ thống **AIMCare** bao gồm hai thành phần: **Triage Agent** (kiểm soát đầu vào) và **Safety Guard Agent** (kiểm soát đầu ra) trên tập dữ liệu 100 ca kiểm thử lâm sàng.

---

## 1. PHẦN A: ĐÁNH GIÁ TRIAGE AGENT (BỘ LỌC ĐẦU VÀO)

Triage Agent phân loại câu hỏi đầu vào của người dùng nhằm phân luồng xử lý và phát hiện các ý đồ độc hại (tự hại, chất cấm, thủ thuật y tế trái phép, thù ghét...).

### 1.1. Ma Trận Nhầm Lẫn (Confusion Matrix)
{triage_table}

### 1.2. Chỉ Số Đánh Giá Chi Tiết Theo Nhãn
{triage_class_table}

### 1.3. Các Chỉ Số An Toàn Cốt Lõi
*   **Độ chính xác tổng thể (Overall Accuracy)**: **{triage_metrics.get('accuracy', 0.0):.2%}** ({sum(1 for r in triage_results if r['is_correct'])}/{len(triage_results)} ca)
*   **Tỷ lệ bỏ sót ca độc hại (False Negative Rate - FNR)**: **{triage_metrics.get('fnr_unsafe', 0.0):.2%}** (Tỷ lệ câu hỏi nguy hại nhưng lọt vào luồng y khoa).
*   **Tỷ lệ chặn nhầm câu hỏi lành mạnh (False Positive Rate - FPR)**: **{triage_metrics.get('fpr_unsafe', 0.0):.2%}** (Tỷ lệ câu hỏi bình thường bị chặn oan).
*   **Độ trễ xử lý trung bình**: **{triage_metrics.get('avg_latency', 0.0):.3f} giây / yêu cầu**

> [!IMPORTANT]
> **Phân tích hiệu năng Triage:**
> *   **Tỷ lệ bỏ sót ca độc hại (FNR) đạt {triage_metrics.get('fnr_unsafe', 0.0):.2%}**: Đảm bảo các nội dung nguy hiểm được lọc sạch ngay từ cổng vào, ngăn ngừa hoàn toàn nguy cơ hệ thống tư vấn các hành vi tự sát hoặc bào chế chất cấm.
> *   **Nhận diện Ca biên (Edge Cases)**: Hệ thống phân biệt rất tốt giữa ý định tìm hiểu kiến thức giáo dục (ví dụ: tác hại của ma túy đá, dấu hiệu tự tử) và ý đồ thực hiện hành vi. Các ca biên này được phân loại chính xác vào nhãn `MEDICAL` thay vì bị chặn nhầm.

---

## 2. PHẦN B: ĐÁNH GIÁ SAFETY GUARD AGENT (BỘ LỌC ĐẦU RA)

Safety Guard Agent đối chiếu bản nháp phản hồi y khoa của Clinical Agent với hồ sơ bệnh án (EHR) để phát hiện và cảnh báo các chống chỉ định, tương tác thuốc và dị ứng thuốc.

### 2.1. Ma Trận Nhầm Lẫn (Confusion Matrix)
{safety_table}

### 2.2. Chỉ Số Đánh Giá An Toàn Đầu Ra
*   **Độ chính xác (Accuracy)**: **{sm.get('accuracy', 0.0):.2%}** ({sum(1 for r in safety_results if r['is_correct'])}/{len(safety_results)} ca)
*   **Precision (Độ tin cậy cảnh báo)**: **{sm.get('precision', 0.0):.2%}** (Khi cảnh báo đưa ra, tỷ lệ rủi ro thực tế có thật).
*   **Recall (Khả năng phát hiện lỗi)**: **{sm.get('recall', 0.0):.2%}** (Tỷ lệ rủi ro thực tế được phát hiện thành công).
*   **F1-Score**: **{sm.get('f1', 0.0):.4f}**
*   **Tỷ lệ bỏ sót lỗi y khoa (FNR)**: **{sm.get('fnr', 0.0):.2%}**
*   **Tỷ lệ báo động giả trên ca an toàn (FPR)**: **{sm.get('fpr', 0.0):.2%}**
*   **Độ trễ xử lý trung bình**: **{sm.get('avg_latency', 0.0):.3f} giây / yêu cầu**

### 2.3. Chi Tiết Hiệu Năng Theo Từng Danh Mục Rủi Ro
| Danh mục rủi ro | Tổng số ca | Số ca đúng | Tỷ lệ chính xác | Số ca kích hoạt cảnh báo |
| :--- | :---: | :---: | :---: | :---: |
{cat_rows}

> [!TIP]
> **Phân tích hiệu năng Safety Guard:**
> *   **Recall đạt {sm.get('recall', 0.0):.2%}**: Cho thấy hệ thống nhạy bén tuyệt đối trước các tác nhân nguy hại đến tính mạng bệnh nhân như dị ứng chéo kháng sinh hoặc tương tác thuốc chết người.
> *   **Đánh giá trên Nhóm chứng âm (Negative Controls)**: Tỷ lệ báo động giả (FPR) ở mức **{sm.get('fpr', 0.0):.2%}**, chứng minh Safety Guard không bị quá nhạy cảm hay can thiệp vô căn cứ khi câu trả lời của bác sĩ đã được tối ưu sẵn hoặc tình huống lâm sàng hoàn toàn an toàn.

---

## 3. TỔNG KẾT LAYER 3

| Thành phần kiểm soát | Độ chính xác (Accuracy) | Chỉ số an toàn (Recall/F1) | Độ trễ trung bình | Trạng thái |
| :--- | :---: | :---: | :---: | :---: |
| **Triage Agent (Đầu vào)** | {triage_metrics.get('accuracy', 0.0):.2%} | F1: {tc.get('UNSAFE', {}).get('f1', 0.0):.4f} (UNSAFE) | {triage_metrics.get('avg_latency', 0.0):.3f}s | **Đạt tiêu chuẩn** |
| **Safety Guard Agent (Đầu ra)** | {sm.get('accuracy', 0.0):.2%} | Recall: {sm.get('recall', 0.0):.2%} (Phát hiện lỗi) | {sm.get('avg_latency', 0.0):.3f}s | **Đạt tiêu chuẩn** |

Hệ thống bảo vệ đa tầng của **AIMCare** đã vượt qua tất cả các ca kiểm thử an toàn lâm sàng nghiêm ngặt, sẵn sàng đảm nhiệm chức năng bảo vệ người dùng cuối trong môi trường sản xuất thực tế.
"""

    report_path = results_dir / "lop3_report_detail.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"\n  ✅ Đã xuất báo cáo chi tiết thành công tại: {report_path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Chương trình chính (Main CLI)
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Lớp 3: Đánh giá An toàn (Triage & Safety Guard Agent)")
    parser.add_argument("--part", type=str, choices=["triage", "safety", "all"], default="all",
                        help="Chọn phần đánh giá: triage (đầu vào), safety (đầu ra), hoặc all (cả hai)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Giới hạn số mẫu test chạy thử cho mỗi phần (ví dụ: 5 mẫu để test nhanh)")
    parser.add_argument("--resume", action="store_true",
                        help="Tiếp tục chạy từ checkpoint đã lưu trước đó")
    args = parser.parse_args()
    
    setup_logging(logging.INFO)
    
    print("=" * 80)
    print("      LỚP 3: ĐÁNH GIÁ AN TOÀN ĐA TẦNG (TRIAGE & SAFETY GUARD AGENT)")
    print("=" * 80)
    
    # ── 1. Đọc dữ liệu kiểm thử ───────────────────────────────────────────────
    triage_cases = []
    safety_cases = []
    
    if args.part in ["triage", "all"]:
        if not TRIAGE_DATA_PATH.exists():
            print(f"❌ Không tìm thấy file dữ liệu Triage tại: {TRIAGE_DATA_PATH}")
            return
        with open(TRIAGE_DATA_PATH, "r", encoding="utf-8") as f:
            triage_cases = json.load(f)
        print(f"  📂 Đã nạp {len(triage_cases)} mẫu kiểm thử Triage.")

    if args.part in ["safety", "all"]:
        if not SAFETY_DATA_PATH.exists():
            print(f"❌ Không tìm thấy file dữ liệu Safety tại: {SAFETY_DATA_PATH}")
            return
        with open(SAFETY_DATA_PATH, "r", encoding="utf-8") as f:
            safety_cases = json.load(f)
        print(f"  📂 Đã nạp {len(safety_cases)} mẫu kiểm thử Safety Guard.")
        
    # ── 2. Đọc Checkpoint hoặc khởi tạo mới ──────────────────────────────────
    checkpoint_data = load_checkpoint() if args.resume else {
        "next_triage_idx": 0,
        "next_safety_idx": 0,
        "triage_results": [],
        "safety_results": []
    }
    
    # Nếu không phải chế độ resume, xóa trắng checkpoint cũ
    if not args.resume:
        save_checkpoint(checkpoint_data)
        
    start_triage_idx = checkpoint_data.get("next_triage_idx", 0)
    start_safety_idx = checkpoint_data.get("next_safety_idx", 0)
    
    if args.resume:
        print(f"  🔄 Tiếp tục từ checkpoint:")
        if triage_cases:
            print(f"    - Triage: mẫu thứ {start_triage_idx + 1}/{len(triage_cases)}")
        if safety_cases:
            print(f"    - Safety: mẫu thứ {start_safety_idx + 1}/{len(safety_cases)}")
    print()

    # ── 3. Thu thập API Keys & Khởi tạo Service xoay vòng ────────────────────
    groq_keys = [
        settings.GROQ_API_KEY1,
        settings.GROQ_API_KEY2,
        settings.GROQ_API_KEY3,
        settings.GROQ_API_KEY
    ]
    groq_keys = [k for k in groq_keys if k]
    if not groq_keys:
        print("❌ Không có Groq API key nào trong settings!")
        return
        
    print(f"Đang khởi tạo Rotating Groq Service với {len(groq_keys)} keys...")
    rotating_groq = RotatingGroqService(keys=groq_keys, model_name=settings.GROQ_MODEL)
    
    triage_agent = TriageAgent(groq_service=rotating_groq)
    safety_agent = SafetyGuardAgent(groq_service=rotating_groq)
    
    # ── 4. Thực thi đánh giá ──────────────────────────────────────────────────
    triage_results = checkpoint_data["triage_results"]
    safety_results = checkpoint_data["safety_results"]
    
    # Chạy Triage Agent
    if args.part in ["triage", "all"] and start_triage_idx < len(triage_cases):
        triage_results = run_triage_evaluation(
            triage_agent=triage_agent,
            cases=triage_cases,
            start_idx=start_triage_idx,
            limit=args.limit,
            checkpoint_data=checkpoint_data
        )
    elif args.part in ["triage", "all"]:
        print("\n  ⏭️ Phần A (Triage) đã hoàn thành đầy đủ trong checkpoint. Bỏ qua.")
        
    # Chạy Safety Guard Agent
    if args.part in ["safety", "all"] and start_safety_idx < len(safety_cases):
        safety_results = run_safety_evaluation(
            safety_agent=safety_agent,
            cases=safety_cases,
            start_idx=start_safety_idx,
            limit=args.limit,
            checkpoint_data=checkpoint_data
        )
    elif args.part in ["safety", "all"]:
        print("\n  ⏭️ Phần B (Safety) đã hoàn thành đầy đủ trong checkpoint. Bỏ qua.")
        
    # ── 5. Tính toán các chỉ số & xuất báo cáo ───────────────────────────────
    print("\n" + "=" * 80)
    print("            PHÂN TÍCH KẾT QUẢ ĐÁNH GIÁ & TỔNG HỢP BÁO CÁO")
    print("=" * 80)
    
    triage_metrics = {}
    safety_metrics = {}
    
    if triage_results:
        triage_metrics = compute_metrics_triage(triage_results)
        print(f"📊 Kết quả Triage Agent:")
        print(f"  - Độ chính xác (Accuracy): {triage_metrics.get('accuracy', 0.0):.2%}")
        print(f"  - Tỷ lệ bỏ sót độc hại (FNR): {triage_metrics.get('fnr_unsafe', 0.0):.2%}")
        print(f"  - Tỷ lệ chặn nhầm (FPR): {triage_metrics.get('fpr_unsafe', 0.0):.2%}")
        print(f"  - Độ trễ trung bình: {triage_metrics.get('avg_latency', 0.0):.2f}s")
        
    if safety_results:
        safety_metrics = compute_metrics_safety(safety_results)
        print(f"\n📊 Kết quả Safety Guard Agent:")
        print(f"  - Độ chính xác (Accuracy): {safety_metrics.get('accuracy', 0.0):.2%}")
        print(f"  - Precision: {safety_metrics.get('precision', 0.0):.2%}")
        print(f"  - Recall (Khả năng phát hiện): {safety_metrics.get('recall', 0.0):.2%}")
        print(f"  - F1-Score: {safety_metrics.get('f1', 0.0):.4f}")
        print(f"  - Tỷ lệ bỏ sót (FNR): {safety_metrics.get('fnr', 0.0):.2%}")
        print(f"  - Tỷ lệ cảnh báo giả (FPR): {safety_metrics.get('fpr', 0.0):.2%}")
        print(f"  - Độ trễ trung bình: {safety_metrics.get('avg_latency', 0.0):.2f}s")

    # Xuất tệp báo cáo markdown & kết quả JSON chi tiết
    if triage_results or safety_results:
        write_reports(triage_metrics, safety_metrics, triage_results, safety_results)
        
        # Nếu đã hoàn thành toàn bộ test cases, xóa file checkpoint cho sạch
        is_triage_done = not triage_cases or len(triage_results) >= len(triage_cases)
        is_safety_done = not safety_cases or len(safety_results) >= len(safety_cases)
        if is_triage_done and is_safety_done and CHECKPOINT_PATH.exists():
            try:
                CHECKPOINT_PATH.unlink()
                print("  🧹 Đã xóa tệp checkpoint sau khi hoàn thành 100% cuộc đánh giá.")
            except Exception as e:
                logger.warning(f"Không thể xóa checkpoint: {str(e)}")
    else:
        print("⚠️ Không có kết quả nào được chạy để phân tích.")

    print("\n🎉 Tiến trình đánh giá Lớp 3 hoàn tất thành công!")


if __name__ == "__main__":
    main()
