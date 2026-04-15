import logging
import re
from functools import wraps
from typing import Callable

logger = logging.getLogger("quota_monitor")

def log_quota_errors(func: Callable):
    """
    Decorator để bắt và in ra log cảnh báo chi tiết và dễ hiểu 
    khi gặp lỗi 429 ResourceExhausted (Vượt quá giới hạn API Gemini).
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            
            # Kiểm tra xem có phải lỗi vượt quá hạn mức 429 không
            if "429" in error_msg and ("quota" in error_msg.lower() or "ResourceExhausted" in error_msg):
                wait_time_match = re.search(r"Please retry in (\d+(\.\d+)?)s", error_msg)
                wait_time = wait_time_match.group(1) if wait_time_match else "một khoảng thời gian"
                
                logger.error("")
                logger.error("=" * 70)
                logger.error("🚨 CHÚ Ý: LỖI VƯỢT QUÁ GIỚI HẠN API (QUOTA EXCEEDED) 🚨")
                logger.error("======================================================================")
                logger.error("❌ NGUYÊN NHÂN: Ứng dụng đã gọi API Google Gemini vượt quá giới hạn")
                logger.error("               của gói miễn phí (Free Tier).")
                logger.error("📊 CHI TIẾT:")
                logger.error(f"  - Model             : gemini-2.5-flash")
                logger.error(f"  - Giới hạn gói Free : Chỉ cho phép tối đa 5 requests/phút.")
                logger.error(f"  - Trạng thái        : Bị Google từ chối xử lý.")
                logger.error(f"💡 HƯỚNG KHẮC PHỤC:")
                logger.error(f"  1. Tạm thời: Hãy chờ khoảng {wait_time} giây trước khi gửi tiếp.")
                logger.error(f"  2. Lâu dài : Thêm thẻ tín dụng (Setup Billing) trên nền tảng")
                logger.error(f"               Google AI Studio để bỏ chặn giới hạn 5 yêu cầu này.")
                logger.error("======================================================================")
                logger.error("")
                
            raise e
    return wrapper
