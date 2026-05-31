import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from config import settings

logger = logging.getLogger(__name__)

# Danh sách các trường chứa dữ liệu y tế cần lọc bỏ
SENSITIVE_KEYS = {
    "chronic_diseases", "allergies", "current_medications",
    "content", "query", "message", "snippet", "health_profile",
    "age", "gender", "email", "first_name", "last_name",
}

def _scrub_data(data):
    """Đệ quy lọc bỏ dữ liệu nhạy cảm trước khi gửi lên Sentry."""
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k in SENSITIVE_KEYS else _scrub_data(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_scrub_data(item) for item in data]
    return data


def _before_send(event, hint):
    """Hook lọc dữ liệu nhạy cảm trước khi event gửi lên Sentry."""
    # Lọc request body
    if "request" in event and "data" in event["request"]:
        event["request"]["data"] = _scrub_data(event["request"]["data"])
    
    # Lọc breadcrumbs (lịch sử hoạt động gần nhất)
    if "breadcrumbs" in event:
        for crumb in event["breadcrumbs"].get("values", []):
            if "data" in crumb:
                crumb["data"] = _scrub_data(crumb["data"])
    return event


def init_sentry():
    """Khởi tạo Sentry SDK nếu SENTRY_DSN_BACKEND đã được cấu hình."""
    dsn = settings.SENTRY_DSN_BACKEND
    if not dsn:
        logger.info("Sentry DSN not configured — skipping Sentry init.")
        return

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(
                level=logging.INFO,          # Ghi nhận breadcrumbs từ level INFO
                event_level=logging.ERROR,    # Chỉ tạo Sentry Event khi level >= ERROR
            ),
        ],
        traces_sample_rate=0.3,    # Ghi nhận 30% request cho Performance Monitoring
        profiles_sample_rate=0.1,  # Ghi nhận 10% cho Profiling
        before_send=_before_send,
        environment="production",
        release=settings.APP_VERSION,
        send_default_pii=False,    # Không gửi thông tin cá nhân mặc định
    )
    logger.info("Sentry SDK initialized for Backend.")
