# Script import dữ liệu bệnh mạn tính ICD-10 vào MongoDB collection clinical_conditions.
# Chạy một lần: python -m scripts.seed_clinical_conditions

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unidecode import unidecode
from database.mongo import MongoDB

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).parent.parent.parent / "data" / "clinical_conditions.json"
COLLECTION_NAME = "clinical_conditions"


def build_search_key(text: str) -> str:
    """Chuyển chuỗi tiếng Việt sang dạng ASCII không dấu, chữ thường."""
    return unidecode(text).lower().strip()


async def seed():
    """Đọc file JSON, tạo search_key và upsert vào MongoDB."""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db = await MongoDB.connect(url=mongo_url, db_name="medical_ai")
    collection = db[COLLECTION_NAME]

    logger.info(f"Reading data from: {DATA_FILE}")
    with open(DATA_FILE, encoding="utf-8") as f:
        raw_data = json.load(f)

    docs = []
    for item in raw_data:
        label = item.get("label", "").strip()
        category = item.get("category", "").strip()
        icd_code = item.get("icd_10_code", item.get("icd_code", "")).strip()
        search_key = build_search_key(f"{label} {category}")

        docs.append({
            "_id": icd_code,
            "icd_code": icd_code,
            "label": label,
            "category": category,
            "search_key": search_key,
        })

    if not docs:
        logger.warning("No data found in file. Aborting.")
        return

    await collection.drop()
    result = await collection.insert_many(docs)
    logger.info(f"✅ Inserted {len(result.inserted_ids)} clinical conditions into MongoDB.")

    await collection.create_index([("label", 1)])
    await collection.create_index([("search_key", 1)])
    await collection.create_index([("category", 1)])
    logger.info("✅ Indexes created on label, search_key, category.")

    await MongoDB.close()


if __name__ == "__main__":
    asyncio.run(seed())
