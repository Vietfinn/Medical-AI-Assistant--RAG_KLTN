import logging
import sys
from pythonjsonlogger import json as jsonlogger
from config import settings

def setup_logging():
    """Cấu hình logging tập trung cho toàn bộ AIMCare Backend."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Xóa các handler cũ để tránh log trùng lặp
    root_logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.LOG_FORMAT == "json":
        # Production: JSON structured logging
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"asctime": "timestamp", "name": "module", "levelname": "level"},
            datefmt="%Y-%m-%dT%H:%M:%S%z"
        )
    else:
        # Development: Human-readable text
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Giảm độ ồn từ các thư viện bên thứ ba
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("cohere").setLevel(logging.WARNING)
