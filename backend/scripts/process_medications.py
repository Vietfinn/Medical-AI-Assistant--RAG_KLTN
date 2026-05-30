# Script xử lý và import dữ liệu thuốc từ Long Châu vào MongoDB.
# Chạy một lần: python -m scripts.process_medications

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unidecode import unidecode
from database.mongo import MongoDB

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DRUGS_FILE = Path(__file__).parent.parent / "crawler" / "output" / "drugs_data.json"
MEDICATIONS_COLLECTION = "medications"
INGREDIENTS_COLLECTION = "ingredients_master"


def build_search_key(text: str) -> str:
    """Chuyển chuỗi tiếng Việt sang dạng ASCII không dấu, chữ thường."""
    return unidecode(text).lower().strip()


def parse_ingredients(raw: str) -> list[str]:
    """Tách chuỗi hoạt chất ngăn cách bằng dấu chấm phẩy thành mảng đã chuẩn hóa."""
    if not raw or not raw.strip():
        return []
    parts = re.split(r";|,", raw)
    cleaned = []
    for part in parts:
        ingredient = re.sub(r"\d+(\.\d+)?\s*(mg|mcg|g|ml|%|IU|UI)?", "", part, flags=re.IGNORECASE)
        ingredient = ingredient.strip().strip("-").strip()
        if ingredient:
            cleaned.append(ingredient.title())
    return list(dict.fromkeys(cleaned))


async def seed():
    """Đọc drugs_data.json, chuẩn hóa, import vào medications và ingredients_master."""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db = await MongoDB.connect(url=mongo_url, db_name="medical_ai")

    logger.info(f"Reading data from: {DRUGS_FILE}")
    with open(DRUGS_FILE, encoding="utf-8") as f:
        raw_data = json.load(f)

    medication_docs = []
    all_ingredients: set[str] = set()

    for item in raw_data:
        drug_name = item.get("drug_name", "").strip().title()
        category = item.get("category", "").strip()
        raw_ingredients = item.get("all_ingredients", "")
        ingredients = parse_ingredients(raw_ingredients)

        if not drug_name or not category:
            continue

        search_key = build_search_key(f"{drug_name} {category}")

        medication_docs.append({
            "drug_name": drug_name,
            "ingredients": ingredients,
            "category": category,
            "search_key": search_key,
        })
        all_ingredients.update(ingredients)

    logger.info(f"Processed {len(medication_docs)} medications, {len(all_ingredients)} unique ingredients.")

    med_col = db[MEDICATIONS_COLLECTION]
    await med_col.drop()
    if medication_docs:
        result = await med_col.insert_many(medication_docs)
        logger.info(f"✅ Inserted {len(result.inserted_ids)} medications.")

    await med_col.create_index([("category", 1), ("drug_name", 1)])
    await med_col.create_index([("search_key", 1)])
    logger.info("✅ Indexes created on medications.")

    ingredient_docs = []
    for name in sorted(all_ingredients):
        if not name:
            continue
        first_letter = unidecode(name[0]).upper()
        ingredient_docs.append({
            "name": name,
            "first_letter": first_letter,
        })

    ing_col = db[INGREDIENTS_COLLECTION]
    await ing_col.drop()
    if ingredient_docs:
        result = await ing_col.insert_many(ingredient_docs)
        logger.info(f"✅ Inserted {len(result.inserted_ids)} unique ingredients.")

    await ing_col.create_index([("first_letter", 1), ("name", 1)])
    logger.info("✅ Indexes created on ingredients_master.")

    await MongoDB.close()


if __name__ == "__main__":
    asyncio.run(seed())
