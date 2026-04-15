import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings"""

    # API Configuration
    APP_NAME: str = "Medical AI Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Groq API (Llama 3)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Cohere API (Reranker)
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")

    # Qdrant Configuration
    # Hỗ trợ cả Local và Cloud
    QDRANT_MODE: str = os.getenv("QDRANT_MODE", "local")  # "local" hoặc "cloud"

    # Local Qdrant (Docker)
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))

    # Qdrant Cloud
    QDRANT_CLOUD_URL: str = os.getenv("QDRANT_CLOUD_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")

    # Collection name
    QDRANT_COLLECTION: str = "vnhealthqa"

    # Embedding Model
    EMBEDDING_MODEL: str = "bkai-foundation-models/vietnamese-bi-encoder"
    RERANKER_MODEL: str = "rerank-v4.0-pro"

    # Retrieval Configuration
    TOP_K_RETRIEVAL: int = 15
    TOP_K_RERANK: int = 5
    HYBRID_ALPHA: float = 0.5  # Balance between vector and BM25

    # Safety Configuration
    ENABLE_SAFETY_CHECK: bool = True
    WARNING_THRESHOLD: float = 0.7

    # Agent Configuration
    ENABLE_TRIAGE_AGENT: bool = True
    ENABLE_SAFETY_AGENT: bool = True

    # MongoDB Configuration (supports mongodb:// and mongodb+srv://)
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/medical_ai")

    # Clerk Authentication
    CLERK_JWKS_URL: str = os.getenv(
        "CLERK_JWKS_URL", "https://<your-clerk-domain>/.well-known/jwks.json"
    )
    CLERK_ISSUER: str = os.getenv("CLERK_ISSUER", "https://<your-clerk-domain>")

    # Resend Email
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "Medical AI <onboarding@resend.dev>")

    # CORS — thêm FRONTEND_URL (Vercel) vào danh sách Origins khi deploy
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "")

    @property
    def CORS_ORIGINS(self) -> list:
        origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
        ]
        if self.FRONTEND_URL:
            origins.append(self.FRONTEND_URL)
        return origins

    def get_qdrant_client_params(self):
        """
        Trả về parameters cho Qdrant Client dựa trên mode
        """
        if self.QDRANT_MODE == "cloud":
            if not self.QDRANT_CLOUD_URL or not self.QDRANT_API_KEY:
                raise ValueError(
                    "QDRANT_CLOUD_URL và QDRANT_API_KEY bắt buộc khi sử dụng Qdrant Cloud. "
                    "Vui lòng cấu hình trong file .env"
                )
            return {
                "url": self.QDRANT_CLOUD_URL,
                "api_key": self.QDRANT_API_KEY,
                "prefer_grpc": True,  # Tối ưu performance
                "timeout": 60.0,
            }
        else:
            # Local mode
            return {"host": self.QDRANT_HOST, "port": self.QDRANT_PORT, "timeout": 60.0}

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
