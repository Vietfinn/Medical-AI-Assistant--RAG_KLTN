# In-Memory Suggestion Engine sử dụng RapidFuzz để cung cấp gợi ý real-time cho 3 trường hồ sơ sức khỏe.
# Dữ liệu được load từ MongoDB một lần khi startup, sau đó mọi query đều chạy trên RAM.

import logging
from typing import Optional

from rapidfuzz import fuzz, process
from unidecode import unidecode

logger = logging.getLogger(__name__)

SUGGESTION_LIMIT = 15

_conditions_cache: list[dict] = []
_ingredients_cache: list[dict] = []
_ingredients_normalized_cache: list[str] = []
_medications_cache: list[dict] = []
_medications_categories_cache: list[str] = []


def _build_search_key(text: str) -> str:
    """Chuẩn hóa chuỗi về dạng ASCII không dấu, chữ thường để so sánh."""
    return unidecode(text).lower().strip()


async def load_data_to_ram(db) -> None:
    """Load toàn bộ 3 collection từ MongoDB vào bộ nhớ RAM.
    Được gọi một lần duy nhất trong FastAPI lifespan startup.
    """
    global _conditions_cache, _ingredients_cache, _ingredients_normalized_cache, _medications_cache, _medications_categories_cache

    conditions_cursor = db["clinical_conditions"].find({}, {"_id": 0})
    _conditions_cache = await conditions_cursor.to_list(length=None)
    logger.info(f"  ✅ Loaded {len(_conditions_cache)} clinical conditions into RAM.")

    ingredients_cursor = db["ingredients_master"].find({}, {"_id": 0}).sort("name", 1)
    _ingredients_cache = await ingredients_cursor.to_list(length=None)
    _ingredients_normalized_cache = [_build_search_key(item.get("name", "")) for item in _ingredients_cache]
    logger.info(f"  ✅ Loaded {len(_ingredients_cache)} ingredients into RAM (and cached normalized names).")

    medications_cursor = db["medications"].find({}, {"_id": 0})
    _medications_cache = await medications_cursor.to_list(length=None)
    logger.info(f"  ✅ Loaded {len(_medications_cache)} medications into RAM.")

    # Cache unique categories once during RAM cache loading
    seen = set()
    categories = []
    for item in _medications_cache:
        cat = item.get("category", "")
        if cat and cat not in seen:
            seen.add(cat)
            categories.append(cat)
    _medications_categories_cache = sorted(categories)
    logger.info(f"  ✅ Cached {len(_medications_categories_cache)} unique medication categories in RAM.")


def search_conditions(query: str) -> list[dict]:
    """Tìm kiếm bệnh mạn tính theo chiến lược Prefix-first + Fuzzy fallback.
    Ưu tiên các bệnh có label bắt đầu bằng query (Prefix Match).
    Sau đó bổ sung bằng Fuzzy Match trên search_key (ASCII không dấu).
    """
    if not query or not _conditions_cache:
        return []

    q_normalized = _build_search_key(query)
    prefix_results = []
    remaining = []

    for item in _conditions_cache:
        sk = item.get("search_key", "")
        if sk.startswith(q_normalized):
            prefix_results.append(item)
        else:
            remaining.append(item)

    needed = SUGGESTION_LIMIT - len(prefix_results)
    if needed > 0 and remaining:
        search_keys = [r.get("search_key", "") for r in remaining]
        fuzzy_hits = process.extract(
            q_normalized,
            search_keys,
            scorer=fuzz.partial_ratio,
            limit=needed,
            score_cutoff=55,
        )
        fuzzy_indices = {hit[2] for hit in fuzzy_hits}
        for idx in fuzzy_indices:
            prefix_results.append(remaining[idx])

    return prefix_results[:SUGGESTION_LIMIT]


def get_ingredients(query: Optional[str] = None) -> list[dict]:
    """Trả về danh sách hoạt chất.
    Nếu không có query: Trả về toàn bộ list đã sắp xếp A-Z (scroll mode).
    Nếu có query: Fuzzy Match trên tên hoạt chất.
    """
    if not _ingredients_cache:
        return []

    if not query:
        return _ingredients_cache[:SUGGESTION_LIMIT]

    q_normalized = _build_search_key(query)

    fuzzy_hits = process.extract(
        q_normalized,
        _ingredients_normalized_cache,
        scorer=fuzz.partial_ratio,
        limit=SUGGESTION_LIMIT,
        score_cutoff=50,
    )
    results = []
    for _, _, idx in fuzzy_hits:
        results.append(_ingredients_cache[idx])

    return results[:SUGGESTION_LIMIT]


def search_medications(query: Optional[str] = None, category: Optional[str] = None) -> list[dict]:
    """Tìm kiếm thuốc theo chiến lược Pure Fuzzy Match.
    Lọc theo category trước (nếu có), sau đó Fuzzy Match trên drug_name (search_key).
    Trả về object đầy đủ gồm cả trường category để Frontend đồng bộ state.
    """
    if not _medications_cache:
        return []

    pool = _medications_cache
    if category:
        pool = [m for m in pool if m.get("category", "") == category]

    if not query:
        return pool[:SUGGESTION_LIMIT]

    q_normalized = _build_search_key(query)
    search_keys = [m.get("search_key", "") for m in pool]

    fuzzy_hits = process.extract(
        q_normalized,
        search_keys,
        scorer=fuzz.WRatio,
        limit=SUGGESTION_LIMIT,
        score_cutoff=45,
    )

    results = []
    for _, _, idx in fuzzy_hits:
        results.append(pool[idx])

    return results[:SUGGESTION_LIMIT]


def get_medication_categories() -> list[str]:
    """Trả về danh sách các nhóm thuốc duy nhất đã được cache (O(1))."""
    return _medications_categories_cache
