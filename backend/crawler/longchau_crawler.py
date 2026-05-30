"""
Script chính: Long Châu Drug Crawler — Pipeline 3 bước ETL (Extract).
Cào tên thuốc, hoạt chất, nhóm thuốc từ nhathuoclongchau.com.vn.
"""

import json
import logging
import os
import random
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

import config

os.makedirs(config.OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(config.OUTPUT_DIR, config.LOG_FILE), encoding="utf-8"
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def get_html(url: str, session: requests.Session) -> BeautifulSoup | None:
    """Tải HTML từ URL và trả về đối tượng BeautifulSoup. Trả về None nếu lỗi."""
    try:
        resp = session.get(url, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.HTTPError as e:
        log.error(f"HTTP Error {e.response.status_code} khi tải: {url}")
    except requests.exceptions.ConnectionError:
        log.error(f"Lỗi kết nối khi tải: {url}")
    except requests.exceptions.Timeout:
        log.error(f"Timeout khi tải: {url}")
    except Exception as e:
        log.error(f"Lỗi không xác định khi tải {url}: {e}")
    return None


def _build_page_url(base_url: str, page_num: int) -> str:
    """Ghép số trang vào URL danh mục."""
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query["page"] = [str(page_num)]
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def step1_get_links_from_sitemap(session: requests.Session) -> list[str]:
    """
    Bước 1 (The Harvester): Cào trực tiếp từ sitemap_thuoc.xml
    để lấy toàn bộ link sản phẩm mà không bị Next.js CSR cản trở.
    Trả về list URL (str).
    """
    log.info("=" * 60)
    log.info("BƯỚC 1: Thu thập link sản phẩm từ Sitemap...")
    
    try:
        resp = session.get(config.SITEMAP_URL, headers=config.HEADERS, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "xml")
    except Exception as e:
        log.error(f"Lỗi khi tải sitemap: {e}")
        return []

    urls = []
    for loc in soup.find_all("loc"):
        url = loc.text.strip()
        if url.endswith(".html") and "/thuoc/" in url:
            urls.append(url)

    # Loại bỏ trùng lặp
    urls = list(set(urls))

    if config.DEBUG_MODE:
        urls = urls[:config.DEBUG_MAX_SITEMAP_URLS]
        log.info(f"[DEBUG MODE] Giới hạn còn {len(urls)} link sitemap.")

    log.info(f"Tìm được {len(urls)} link sản phẩm từ sitemap.")
    return urls


def _extract_from_next_data(soup: BeautifulSoup) -> dict | None:
    """
    Vũ khí bí mật: Khai thác JSON từ thẻ <script id='__NEXT_DATA__'>.
    Đây là nguồn dữ liệu chính xác và đáng tin cậy nhất.
    """
    script_tag = soup.find("script", {"id": config.NEXT_DATA_SCRIPT_ID})
    if not script_tag or not script_tag.string:
        return None

    try:
        data = json.loads(script_tag.string)
    except json.JSONDecodeError:
        return None

    props = data.get("props", {}).get("pageProps", {})

    product_data = (
        props.get("productDetail")
        or props.get("product")
        or props.get("data", {}).get("product")
        or props.get("initialState", {}).get("product", {}).get("detail")
    )

    if not product_data:
        for key in props:
            val = props[key]
            if isinstance(val, dict) and ("name" in val or "ingredients" in val):
                product_data = val
                break

    if not product_data:
        return None

    # Lấy danh mục thuốc
    categories_raw = product_data.get("categories", [])
    category_name = "Không xác định"
    
    # categories_raw thường có dạng: ["Thuốc", "Thuốc tim mạch & máu", "Thuốc tim mạch huyết áp"]
    # Ta ưu tiên lấy danh mục cấp 2 (index 1) hoặc danh mục sâu nhất nếu có.
    if isinstance(categories_raw, list) and len(categories_raw) > 0:
        valid_cats = [c["name"] for c in categories_raw if isinstance(c, dict) and c.get("name")]
        if len(valid_cats) >= 2:
            category_name = valid_cats[1] # Lấy danh mục cấp 2 (ví dụ: "Thuốc tim mạch & máu")
        elif len(valid_cats) == 1:
            category_name = valid_cats[0]

    result = {
        "raw_name": product_data.get("name") or product_data.get("displayName", ""),
        "category": category_name,
        "ingredients": [],
        "short_description": product_data.get("shortDescription", "")
        or product_data.get("description", ""),
    }

    ingredients_raw = (
        product_data.get("ingredients")
        or product_data.get("ingredient")
        or product_data.get("activeIngredients")
        or []
    )

    if isinstance(ingredients_raw, list):
        result["ingredients"] = [
            i.get("name", i) if isinstance(i, dict) else str(i)
            for i in ingredients_raw
        ]
    elif isinstance(ingredients_raw, str) and ingredients_raw:
        result["ingredients"] = [ingredients_raw]

    return result


def _extract_from_html_fallback(soup: BeautifulSoup) -> dict:
    """
    Phương án dự phòng: Cào HTML thủ công nếu __NEXT_DATA__ không có dữ liệu.
    Sử dụng Cách A (Regex) và Cách B (Bảng thành phần).
    """
    result = {"raw_name": "", "category": "Không xác định", "ingredients": [], "short_description": ""}

    h1 = soup.find("h1")
    if h1:
        result["raw_name"] = h1.get_text(strip=True)

    # Lấy danh mục từ Breadcrumb nếu có
    breadcrumb_links = soup.select(".breadcrumb a, nav[aria-label='breadcrumb'] a, ul.flex.flex-wrap li a")
    if len(breadcrumb_links) >= 3:
        # Thông thường: Trang chủ > Tủ thuốc > [Nhóm thuốc] > Tên thuốc
        result["category"] = breadcrumb_links[2].get_text(strip=True)

    desc_el = soup.select_one(".product-detail-description, .drug-introduction, .short-description")
    if desc_el:
        desc_text = desc_el.get_text(" ", strip=True)
        result["short_description"] = desc_text

        pattern = r"thành phần chính[:\s]+(?:là\s+)?([A-Za-zÀ-ỹ\s\d,()]+?)(?:\.|,|;|$)"
        match = re.search(pattern, desc_text, re.IGNORECASE)
        if match:
            result["ingredients"] = [match.group(1).strip()]

    if not result["ingredients"]:
        ingredient_labels = ["Thành phần", "Hoạt chất", "Thành phần chính"]
        rows = soup.select("table tr, .drug-info-row, .product-info-row")
        for row in rows:
            cells = row.find_all(["td", "th", "dt", "dd"])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if any(lbl.lower() in label.lower() for lbl in ingredient_labels):
                    raw_val = cells[1].get_text(" ", strip=True)
                    cleaned = re.sub(r"\s+", " ", raw_val).strip()
                    if cleaned:
                        result["ingredients"] = [cleaned]
                        break

    return result


def _clean_drug_name(raw_name: str) -> str:
    """
    Làm sạch tên thuốc: cắt bỏ phần đuôi mô tả, chỉ giữ tên + hàm lượng.
    Ví dụ: 'Thuốc Exopadin 60mg Trường Thọ điều trị...' -> 'Exopadin 60mg'
    """
    name = re.sub(r"^[Tt]huốc\s+", "", raw_name).strip()
    match = re.match(r"^([A-Za-zÀ-ỹ\d\s\-\.]+?\d+\s*(?:mg|mcg|g|ml|IU|UI|%|đơn vị))", name, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    stop_words = [
        " điều trị", " dùng để", " hỗ trợ", " phòng ngừa",
        " công ty", " Cty", " (hộp", " hộp ", " viên",
    ]
    for word in stop_words:
        idx = name.lower().find(word.lower())
        if idx != -1:
            name = name[:idx].strip()
            break

    return name


def step2_extract_product_details(
    product_urls: list[str], session: requests.Session
) -> list[dict]:
    """
    Bước 2: Truy cập từng link sản phẩm, bóc tách tên thuốc, hoạt chất, nhóm thuốc.
    Tích hợp Anti-Ban sleep và chiến lược dual-extraction (__NEXT_DATA__ + HTML fallback).
    """
    log.info("=" * 60)
    log.info(f"BƯỚC 2: Cào chi tiết {len(product_urls)} sản phẩm...")

    results = []
    urls_to_crawl = list(product_urls)

    if config.DEBUG_MODE:
        total_debug_limit = config.DEBUG_MAX_PRODUCTS
        urls_to_crawl = urls_to_crawl[:total_debug_limit]
        log.info(f"[DEBUG MODE] Giới hạn còn {len(urls_to_crawl)} sản phẩm.")

    for idx, url in enumerate(urls_to_crawl, start=1):
        log.info(f"  [{idx}/{len(urls_to_crawl)}] Đang cào: {url}")

        soup = get_html(url, session)
        if not soup:
            log.warning(f"  Bỏ qua (không tải được): {url}")
            time.sleep(random.uniform(config.SLEEP_MIN, config.SLEEP_MAX))
            continue

        data = _extract_from_next_data(soup)
        source = "__NEXT_DATA__"

        if not data or not data.get("raw_name"):
            data = _extract_from_html_fallback(soup)
            source = "HTML_FALLBACK"

        raw_name = data.get("raw_name", "")
        cleaned_name = _clean_drug_name(raw_name)
        ingredients = data.get("ingredients", [])
        primary_ingredient = ingredients[0] if ingredients else ""
        category = data.get("category", "Không xác định")

        record = {
            "drug_name": cleaned_name,
            "raw_name": raw_name,
            "primary_ingredient": primary_ingredient,
            "all_ingredients": "; ".join(ingredients),
            "category": category,
            "source_url": url,
            "extraction_source": source,
        }
        results.append(record)

        log.info(
            f"     OK [{source}] Nhóm: '{category}' | Tên: '{cleaned_name}' | Hoạt chất: '{primary_ingredient}'"
        )

        time.sleep(random.uniform(config.SLEEP_MIN, config.SLEEP_MAX))

    log.info(f"Cào xong! Thu được dữ liệu của {len(results)}/{len(urls_to_crawl)} sản phẩm.")
    return results


def save_results(results: list[dict]):
    """Lưu kết quả ra file JSON và CSV trong thư mục output/."""
    if not results:
        log.warning("Không có dữ liệu để lưu.")
        return

    json_path = os.path.join(config.OUTPUT_DIR, config.OUTPUT_JSON_FILE)
    csv_path = os.path.join(config.OUTPUT_DIR, config.OUTPUT_CSV_FILE)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info(f"Đã lưu JSON: {json_path}")

    df = pd.DataFrame(results)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    log.info(f"Đã lưu CSV : {csv_path}")

    unique_drugs = df["drug_name"].nunique()
    unique_ingredients = df["primary_ingredient"].nunique()
    log.info(f"TỔNG KẾT: {len(results)} bản ghi | {unique_drugs} tên thuốc | {unique_ingredients} hoạt chất độc nhất")


def main():
    """Hàm chính chạy toàn bộ pipeline 2 bước."""
    mode_label = "DEBUG (giới hạn)" if config.DEBUG_MODE else "FULL (toàn bộ)"
    log.info(f"Bắt đầu Long Châu Drug Crawler — Chế độ: {mode_label}")
    log.info(f"Base URL: {config.BASE_URL}")

    with requests.Session() as session:
        product_urls = step1_get_links_from_sitemap(session)
        if not product_urls:
            log.error("Không lấy được link sản phẩm từ sitemap. Kết thúc.")
            return

        results = step2_extract_product_details(product_urls, session)

    save_results(results)
    log.info("Pipeline hoàn tất.")


if __name__ == "__main__":
    main()
