"""
Cấu hình tập trung cho Long Châu Crawler.
Chỉnh sửa file này nếu cấu trúc website thay đổi.
"""

# ============================================================
# CHẾ ĐỘ DEBUG (Bật True để test nhanh, tắt False để chạy full)
# ============================================================
DEBUG_MODE = False
DEBUG_MAX_SITEMAP_URLS = 10   # Bước 1: Chỉ lấy 10 link từ sitemap
DEBUG_MAX_PRODUCTS = 10       # Bước 2: Chỉ cào 10 sản phẩm rồi dừng

# ============================================================
# URL GỐC & SITEMAP
# ============================================================
BASE_URL = "https://nhathuoclongchau.com.vn"
SITEMAP_URL = "https://nhathuoclongchau.com.vn/sitemap_thuoc.xml"

# ============================================================
# ANTI-BAN: Thời gian nghỉ ngẫu nhiên (giây) giữa các request
# ============================================================
SLEEP_MIN = 1.5
SLEEP_MAX = 2.5

# ============================================================
# HTTP HEADERS: Giả lập trình duyệt thật để tránh bị chặn
# ============================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}
REQUEST_TIMEOUT = 20  # Giây

# ============================================================
# NEXT_DATA JSON KEYS (Bước 2 — Vũ khí bí mật)
# Tên các key trong JSON __NEXT_DATA__ để tìm thông tin thuốc.
# Cập nhật đây nếu cấu trúc JSON của Long Châu thay đổi.
# ============================================================
NEXT_DATA_SCRIPT_ID = "__NEXT_DATA__"

# ============================================================
# OUTPUT (Định dạng xuất file dữ liệu)
# ============================================================
OUTPUT_DIR = "output"
OUTPUT_JSON_FILE = "drugs_data.json"
OUTPUT_CSV_FILE = "drugs_data.csv"
LOG_FILE = "crawler.log"
