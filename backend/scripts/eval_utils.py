"""
Lớp 0: Tiện ích chung cho Evaluation Suite
==========================================
Cung cấp hàm và cấu hình dùng chung cho eval_retrieval.py, eval_generation.py, eval_safety.py.
Tránh lặp code và đảm bảo các script đánh giá hoạt động nhất quán.
"""

import os
import sys
import io
import time
import logging
from pathlib import Path
from contextlib import contextmanager
import numpy as np
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, PermissionDenied, GoogleAPICallError
import underthesea
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from rouge_score import rouge_scorer

# ── Fix Windows console encoding (cp1252 → UTF-8) ───────────────────────────
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Thêm backend/ vào sys.path để import config, services, v.v. ─────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd
from qdrant_client import QdrantClient
from config import settings
from services.embedding import EmbeddingService
from fastembed import SparseTextEmbedding

logger = logging.getLogger(__name__)

# ── Đường dẫn chuẩn ─────────────────────────────────────────────────────────
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = BACKEND_DIR / "scripts" / "results"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Setup
# ═══════════════════════════════════════════════════════════════════════════════

def setup_logging(level=logging.INFO):
    """Cấu hình logging chuẩn cho các script đánh giá."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def ensure_results_dir() -> Path:
    """Tạo thư mục results/ nếu chưa tồn tại. Trả về Path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def ensure_lop1_results_dir() -> Path:
    """Tạo thư mục results/lop1_retrieval/ nếu chưa tồn tại. Trả về Path."""
    p = RESULTS_DIR / "lop1_retrieval"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_lop2_results_dir() -> Path:
    """Tạo thư mục results/lop2_generation/ nếu chưa tồn tại. Trả về Path."""
    p = RESULTS_DIR / "lop2_generation"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_lop3_results_dir() -> Path:
    """Tạo thư mục results/lop3_safety/ nếu chưa tồn tại. Trả về Path."""
    p = RESULTS_DIR / "lop3_safety"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Load dữ liệu test
# ═══════════════════════════════════════════════════════════════════════════════

def load_test_data(csv_path: str = None) -> list[dict]:
    """
    Đọc test_clean.csv → list[dict].
    
    Mỗi dict có dạng: {"id": ..., "question": "...", "answer": "...", "link": "..."}
    
    Args:
        csv_path: Đường dẫn tuyệt đối hoặc tương đối đến file CSV.
                  Nếu None, mặc định đọc data/test_clean.csv.
    
    Returns:
        List các dict, mỗi dict là một dòng trong CSV.
    """
    if csv_path is None:
        csv_path = DATA_DIR / "test_clean.csv"
    
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    
    # Loại bỏ dòng NaN ở cột question/answer (phòng hờ)
    df = df.dropna(subset=["question", "answer"])
    
    records = df.to_dict("records")
    logger.info(f"Đã load {len(records)} test records từ {Path(csv_path).name}")
    return records


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Kết nối & khởi tạo Services
# ═══════════════════════════════════════════════════════════════════════════════

def connect_qdrant() -> QdrantClient:
    """Kết nối Qdrant Cloud/Local dựa trên config.py."""
    params = settings.get_qdrant_client_params()
    client = QdrantClient(**params)
    
    # Verify kết nối bằng cách lấy info collection
    info = client.get_collection(settings.QDRANT_COLLECTION)
    logger.info(
        f"Qdrant connected: collection='{settings.QDRANT_COLLECTION}', "
        f"points={info.points_count}"
    )
    return client


def init_embedding() -> EmbeddingService:
    """Load model embedding vietnamese-bi-encoder, trả về EmbeddingService đã sẵn sàng."""
    svc = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
    if not svc.load_model():
        raise RuntimeError(f"Không thể load embedding model: {settings.EMBEDDING_MODEL}")
    logger.info(f"Embedding model loaded: {settings.EMBEDDING_MODEL}")
    return svc


def init_sparse_model() -> SparseTextEmbedding:
    """Load model Sparse BM25 từ fastembed."""
    model = SparseTextEmbedding(model_name="Qdrant/bm25")
    logger.info("Sparse model (Qdrant/bm25) loaded")
    return model


# ═══════════════════════════════════════════════════════════════════════════════
# 4. So sánh text
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_text(text: str) -> str:
    """
    Chuẩn hóa text để so sánh Ground Truth.
    Loại bỏ whitespace thừa, giữ nguyên nội dung.
    """
    if not text:
        return ""
    return " ".join(str(text).strip().split())


def is_ground_truth_match(result_payload: dict, test_item: dict) -> bool:
    """
    Kiểm tra xem một kết quả truy xuất có khớp với Ground Truth hay không.
    
    So sánh bằng nội dung 'question' (KHÔNG dùng doc_id vì bị trùng lặp
    giữa train/val/test trong cùng 1 collection Qdrant).
    
    Args:
        result_payload: Payload từ Qdrant point (chứa question, answer, ...)
        test_item: Dict từ test_clean.csv (chứa question, answer, ...)
    
    Returns:
        True nếu question text khớp chính xác (sau chuẩn hóa).
    """
    q_result = normalize_text(result_payload.get("question", ""))
    q_test = normalize_text(test_item.get("question", ""))
    return q_result == q_test and q_result != ""


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Timer & Progress
# ═══════════════════════════════════════════════════════════════════════════════

@contextmanager
def timer(label: str = ""):
    """Context manager đo thời gian thực thi."""
    start = time.time()
    yield lambda: time.time() - start  # cho phép đọc elapsed trong block
    elapsed = time.time() - start
    if label:
        logger.info(f"⏱ {label}: {elapsed:.2f}s")


def print_progress(current: int, total: int, prefix: str = "", every: int = 100):
    """In tiến trình mỗi `every` bước."""
    if current % every == 0 or current == total:
        pct = current / total * 100
        print(f"\r  {prefix} [{current}/{total}] {pct:.1f}%", end="", flush=True)
        if current == total:
            print()  # newline khi hoàn tất


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Các chỉ số Đánh giá & So sánh Sinh câu trả lời (Lớp 2)
# ═══════════════════════════════════════════════════════════════════════════════

def tokenize_vietnamese(text: str) -> list[str]:
    """Tách từ tiếng Việt bằng underthesea, fallback về split cơ bản."""
    if not text:
        return []
    text = text.lower().strip()
    try:
        return underthesea.word_tokenize(text)
    except Exception:
        # Fallback split
        for char in ".,!?[](){}\"\'-":
            text = text.replace(char, " ")
        return text.split()


def calculate_bleu4(reference: str, hypothesis: str) -> float:
    """Tính BLEU-4 dùng NLTK với SmoothingMethod."""
    if not reference or not hypothesis:
        return 0.0
    ref_tokens = tokenize_vietnamese(reference)
    hyp_tokens = tokenize_vietnamese(hypothesis)
    if not ref_tokens or not hyp_tokens:
        return 0.0
    
    smoothing = SmoothingFunction().method1
    try:
        return float(sentence_bleu([ref_tokens], hyp_tokens, weights=(0.25, 0.25, 0.25, 0.25), smoothing_function=smoothing))
    except Exception as e:
        logger.error(f"Lỗi tính BLEU-4: {e}")
        return 0.0


def calculate_rouge_l(reference: str, hypothesis: str) -> float:
    """Tính ROUGE-L F1-score dùng rouge-score library."""
    if not reference or not hypothesis:
        return 0.0
    try:
        scorer = rouge_scorer.RougeScorer(['rougeL'], use_stemmer=False)
        scores = scorer.score(reference, hypothesis)
        return float(scores['rougeL'].fmeasure)
    except Exception as e:
        logger.error(f"Lỗi tính ROUGE-L: {e}")
        return 0.0


def calculate_cosine_similarity(emb_service: EmbeddingService, text1: str, text2: str) -> float:
    """Tính Cosine Similarity giữa 2 văn bản dựa trên Vietnamese Bi-Encoder."""
    if not text1 or not text2:
        return 0.0
    try:
        vec1 = emb_service.encode_query(text1, normalize=True)
        vec2 = emb_service.encode_query(text2, normalize=True)
        return float(np.dot(vec1, vec2))
    except Exception as e:
        logger.error(f"Lỗi tính Cosine Similarity: {e}")
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Xoay vòng Gemini API Keys
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiKeyRotator:
    """Xoay vòng các Gemini API Key cấu hình trong .env nhằm tránh lỗi Rate Limit (429) & Project Blocked (403)"""
    def __init__(self):
        # Đọc từ biến GEMINI_KEY
        gemini_keys_str = os.getenv("GEMINI_KEY", "")
        self.keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]
        
        # Cũng đọc các biến GEMINI_KEY_1, GEMINI_KEY_2,... đề phòng cấu hình riêng lẻ
        idx = 1
        while True:
            key = os.getenv(f"GEMINI_KEY_{idx}")
            if not key:
                if idx > 10:
                    break
            else:
                key_stripped = key.strip()
                if key_stripped and key_stripped not in self.keys:
                    self.keys.append(key_stripped)
            idx += 1
            
        logger.info(f"GeminiKeyRotator: Đã load {len(self.keys)} Gemini API keys từ môi trường.")
        self.current_idx = 0
        self.banned_keys = set()    # Lưu các key bị 403 (Permission Denied)
        self.temp_cooldowns = {}     # Lưu cooldown cho các key bị 429: {key_index: resume_timestamp}

    def get_next_key(self) -> str:
        """Lấy key khả dụng tiếp theo, chờ nếu tất cả đang cooldown."""
        if not self.keys:
            raise RuntimeError("Không tìm thấy Gemini API Key nào được cấu hình trong backend/.env!")
            
        total_keys = len(self.keys)
        
        for _ in range(total_keys):
            idx = self.current_idx
            self.current_idx = (self.current_idx + 1) % total_keys
            key = self.keys[idx]
            
            if key in self.banned_keys:
                continue
                
            if idx in self.temp_cooldowns:
                cooldown_until = self.temp_cooldowns[idx]
                if time.time() < cooldown_until:
                    continue
                else:
                    del self.temp_cooldowns[idx]
            
            return key
            
        # Nếu tất cả các key đều bị cấm/cooldown
        active_keys = [k for k in self.keys if k not in self.banned_keys]
        if not active_keys:
            raise RuntimeError("TẤT CẢ các Gemini API keys đã cấu hình đều bị 403 Permission Denied!")
            
        # Tìm key có thời điểm hết cooldown sớm nhất
        next_ready_idx = min(self.temp_cooldowns.keys(), key=lambda k: self.temp_cooldowns[k])
        wait_time = max(1.0, self.temp_cooldowns[next_ready_idx] - time.time())
        logger.warning(f"Tất cả Gemini API keys đang bị 429 Rate Limit. Tự động chờ {wait_time:.1f} giây...")
        time.sleep(wait_time)
        
        if next_ready_idx in self.temp_cooldowns:
            del self.temp_cooldowns[next_ready_idx]
            
        self.current_idx = (next_ready_idx + 1) % total_keys
        return self.keys[next_ready_idx]

    def generate_content(self, model_name: str, prompt: str, system_instruction: str = None, temperature: float = 0.2, max_retries_per_call: int = 15) -> str:
        """Gọi Gemini API và tự động thử lại/xoay vòng key khi lỗi."""
        for attempt in range(max_retries_per_call):
            key = self.get_next_key()
            key_preview = f"{key[:10]}...{key[-5:]}" if len(key) > 10 else "KEY_SHORT"
            
            try:
                genai.configure(api_key=key)
                
                if system_instruction:
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=system_instruction
                    )
                else:
                    model = genai.GenerativeModel(model_name=model_name)
                    
                response = model.generate_content(
                    prompt,
                    generation_config={"temperature": temperature}
                )
                
                if not response.candidates:
                    logger.warning(f"Key {key_preview} trả về response không có candidates.")
                    continue
                    
                candidate = response.candidates[0]
                finish_reason = candidate.finish_reason.name if hasattr(candidate, 'finish_reason') and hasattr(candidate.finish_reason, 'name') else str(candidate.finish_reason)
                
                if finish_reason not in ["STOP", "MAX_TOKENS", "1", "2"]:
                    logger.warning(f"Key {key_preview} có finish_reason không mong đợi: {finish_reason}")
                    continue
                
                if not response.text:
                    logger.warning(f"Key {key_preview} trả về text rỗng.")
                    continue
                    
                return response.text.strip()
                
            except PermissionDenied as e:
                logger.error(f"Key {key_preview} bị 403 Permission Denied. Loại bỏ khỏi danh sách.")
                self.banned_keys.add(key)
                
            except ResourceExhausted as e:
                logger.warning(f"Key {key_preview} bị 429 Rate Limit/Quota Exceeded. Cooldown 60s.")
                try:
                    idx = self.keys.index(key)
                    self.temp_cooldowns[idx] = time.time() + 60.0
                except ValueError:
                    pass
                    
            except GoogleAPICallError as e:
                logger.error(f"Lỗi API từ Google ({key_preview}): {e}")
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Lỗi kết nối hoặc lỗi thư viện với key ({key_preview}): {e}")
                time.sleep(2)
                
        raise RuntimeError(f"Lỗi: Không thể hoàn thành cuộc gọi Gemini {model_name} sau {max_retries_per_call} lần thử xoay vòng key!")
