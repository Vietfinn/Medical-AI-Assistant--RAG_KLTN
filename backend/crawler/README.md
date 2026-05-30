# Long Châu Drug Crawler

Công cụ thu thập dữ liệu thuốc (tên thuốc, hoạt chất, nhóm thuốc) từ **nhathuoclongchau.com.vn**, phục vụ cho tính năng Hồ sơ bệnh án của hệ thống A.I.M Care.

---

## Cài đặt

```bash
# Di chuyển vào thư mục crawler
cd backend/crawler

# Cài đặt thư viện (nên dùng môi trường ảo riêng)
pip install -r requirements.txt
```

---

## Cách chạy

### 1. Chế độ DEBUG (Khuyến nghị chạy trước)

Mở file `config.py`, đảm bảo dòng đầu tiên là:
```python
DEBUG_MODE = True
```

Sau đó chạy:
```bash
python longchau_crawler.py
```

Script sẽ chỉ cào **2 danh mục × 1 trang × 5 sản phẩm** và xuất kết quả vào `output/drugs_data.json`. Quá trình chạy khoảng **15-30 giây**. Mở file JSON kiểm tra dữ liệu trước khi chạy full.

### 2. Chế độ FULL (Cào toàn bộ ~8.000-10.000 sản phẩm)

Mở file `config.py`, đổi thành:
```python
DEBUG_MODE = False
```

Chạy lại:
```bash
python longchau_crawler.py
```

> ⚠️ Chế độ FULL sẽ mất khoảng **4-6 tiếng** để hoàn tất do có tích hợp `sleep(1.5-2.5s)` giữa các request để tránh bị chặn IP.

---

## Cấu trúc Output

Sau khi chạy xong, thư mục `output/` sẽ chứa:

| File | Mô tả |
|---|---|
| `drugs_data.json` | Toàn bộ dữ liệu dạng JSON, dễ import vào MongoDB |
| `drugs_data.csv` | Dạng bảng, dễ mở bằng Excel để kiểm tra |
| `crawler.log` | Log chi tiết toàn bộ quá trình cào |

### Cấu trúc một bản ghi

```json
{
  "drug_name": "Exopadin 60mg",
  "raw_name": "Thuốc Exopadin 60mg Trường Thọ điều trị viêm mũi dị ứng",
  "primary_ingredient": "Fexofenadin Hydroclorid",
  "all_ingredients": "Fexofenadin Hydroclorid 60mg; Tá dược vừa đủ",
  "category": "Thuốc dị ứng",
  "source_url": "https://nhathuoclongchau.com.vn/thuoc/exopadin-60mg-...",
  "extraction_source": "__NEXT_DATA__"
}
```

---

## Cách cập nhật khi Long Châu đổi giao diện

> **Dành cho giảng viên phản biện:** Toàn bộ CSS Selector và cấu trúc trích xuất được tách biệt hoàn toàn ra file `config.py`. Khi website đổi giao diện, **chỉ cần cập nhật `config.py`**, không cần chỉnh sửa logic chính.

### Bước 1: Tìm Selector mới

1. Mở trình duyệt Chrome/Edge, vào trang `nhathuoclongchau.com.vn/thuoc`.
2. Nhấn `F12` mở DevTools → Tab **Elements**.
3. Dùng công cụ **Inspector** (biểu tượng mũi tên ở góc trên trái DevTools) click vào khối danh mục hoặc ô sản phẩm cần tìm.
4. Xem thuộc tính `class` hoặc `href` của thẻ `<a>` được highlight.

### Bước 2: Cập nhật `config.py`

Mở `config.py` và chỉnh sửa phần **CSS SELECTORS**:

```python
# Trước (cũ)
CATEGORY_LINK_SELECTOR = "a[href^='/thuoc/']"

# Sau (mới — ví dụ nếu Long Châu đổi class)
CATEGORY_LINK_SELECTOR = "a.new-category-class[href^='/thuoc/']"
```

### Bước 3: Cập nhật JSON Keys (nếu `__NEXT_DATA__` thay đổi)

Nếu dữ liệu chiết xuất từ `__NEXT_DATA__` bị trống:

1. Mở DevTools → Tab **Elements** → Tìm thẻ `<script id="__NEXT_DATA__">`.
2. Copy nội dung, paste vào [jsonviewer.stack.hu](https://jsonviewer.stack.hu/) để xem cây JSON.
3. Tìm key chứa `name`, `ingredients` và cập nhật hàm `_extract_from_next_data()` trong `longchau_crawler.py`.

---

## Chiến lược Dual-Extraction (Anti-Failure)

Script sử dụng 2 tầng trích xuất để đảm bảo không bỏ sót dữ liệu:

```
Ưu tiên 1: __NEXT_DATA__ JSON  →  Chính xác 100%, không bị nhiễu HTML
      ↓ (nếu thất bại)
Ưu tiên 2: HTML Fallback        →  Regex + Bảng thành phần HTML
```

Cột `extraction_source` trong output sẽ cho biết phương án nào được dùng cho từng sản phẩm.
