"""
Script to index ViHealthQA data into Qdrant vector database
Hỗ trợ cả Qdrant Local và Qdrant Cloud
"""

import json
import logging
import sys
from pathlib import Path
import pandas as pd

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from qdrant_client import QdrantClient
from config import settings
from services import EmbeddingService, HybridRetriever

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_data(file_path: str):
    logger.info(f"Loading data from {file_path}...")
    try:
        # Dùng pandas đọc file CSV bạn đã tạo từ bước EDA
        file_path_obj = Path(file_path)
        suffix = file_path_obj.suffix.lower()

        if suffix == ".json":
            with open(file_path_obj, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON must be a list of records")
            df = pd.DataFrame(data)
        else:
            df = pd.read_csv(file_path_obj, encoding="utf-8-sig")

        missing_cols = [col for col in ["question", "answer"] if col not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Missing required columns: {', '.join(missing_cols)}. "
                "Expected at least 'question' and 'answer'."
            )

        # Xóa các dòng NaN nếu có (phòng hờ)
        df = df.dropna(subset=["question", "answer"])

        # Chuyển DataFrame thành list of dictionaries
        data = df.to_dict("records")

        logger.info(f"Loaded {len(data)} records")
        return data
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        raise


def prepare_documents(data):
    """Prepare documents for indexing"""
    documents = []

    for idx, item in enumerate(data):
        doc = {
            "id": item.get("id", f"VHQ_{idx:05d}"),
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "context": item.get("context", ""),
        }
        documents.append(doc)

    return documents


def main():
    logger.info("=" * 70)
    logger.info("QDRANT DATA INDEXING SCRIPT")
    logger.info("=" * 70)

    # 1. Khởi tạo Qdrant Client và các services
    try:
        # Lấy thông số kết nối từ file config & .env
        qdrant_params = settings.get_qdrant_client_params()
        qdrant_client = QdrantClient(**qdrant_params)

        # Khởi tạo mô hình AI Embedding
        embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
        if not embedding_service.load_model():
            raise RuntimeError("Failed to load embedding model")
        embedding_dim = embedding_service.get_embedding_dimension()

        # SỬA LỖI Ở ĐÂY: Truyền đầy đủ 3 tham số cho Retriever
        retriever = HybridRetriever(
            qdrant_client=qdrant_client,
            collection_name=settings.QDRANT_COLLECTION,
            embedding_service=embedding_service,
            alpha=settings.HYBRID_ALPHA,
        )
        retriever.create_collection(vector_size=embedding_dim)
        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        return

    # 2. XÁC ĐỊNH ĐƯỜNG DẪN FILE CSV (Giữ nguyên đoạn bạn đã sửa trước đó)
    project_root = Path(__file__).parent.parent.parent
    data_file = project_root / "data" / "train_clean.csv"

    if not data_file.exists():
        logger.error(f"❌ Không tìm thấy file dữ liệu tại: {data_file}")
        return

    # 3. Load và Index Data
    try:
        data = load_data(str(data_file))
        documents = prepare_documents(data)

        logger.info(f"Bắt đầu index {len(documents)} bản ghi...")
        retriever.index_documents(documents)

        logger.info("✅ INDEXING COMPLETED SUCCESSFULLY!")

    except Exception as e:
        logger.error(f"❌ Lỗi trong quá trình index: {str(e)}", exc_info=True)
        return


if __name__ == "__main__":
    main()
