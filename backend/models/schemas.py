from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class UserDocument(BaseModel):
    """User document stored in MongoDB (linked to Clerk account)"""

    user_id: str = Field(..., description="Clerk user_id (sub claim from JWT)")
    email: str = Field(..., description="Email từ Clerk")
    first_name: Optional[str] = Field(None, description="Tên người dùng từ Clerk")
    health_profile: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            "chronic_diseases": [],
            "allergies": [],
            "current_medications": [],
            "age": None,
            "gender": "",
        },
        description="Hồ sơ sức khỏe (HealthProfile)",
    )
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())

class HealthProfile(BaseModel):
    """User health profile model"""

    chronic_diseases: List[str] = Field(
        default_factory=list, description="Danh sách bệnh mãn tính"
    )
    allergies: List[str] = Field(
        default_factory=list, description="Danh sách dị ứng"
    )
    current_medications: List[str] = Field(
        default_factory=list, description="Thuốc đang sử dụng"
    )
    age: Optional[int] = Field(None, description="Tuổi")
    gender: Optional[str] = Field(None, description="Giới tính")

    class Config:
        json_schema_extra = {
            "example": {
                "chronic_diseases": ["Đau dạ dày", "Tiểu đường"],
                "allergies": ["Aspirin", "Penicillin"],
                "current_medications": ["Metformin"],
                "age": 45,
                "gender": "Nam",
            }
        }


class ChatQuery(BaseModel):
    """Chat query request model"""

    query: str = Field(..., min_length=1, description="Câu hỏi của người dùng")
    health_profile: Optional[HealthProfile] = Field(
        None, description="Hồ sơ sức khỏe"
    )
    session_id: Optional[str] = Field(
        None, description="Session ID để theo dõi hội thoại"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Làm sao để chữa đau đầu?",
                "health_profile": {
                    "chronic_diseases": ["Đau dạ dày"],
                    "allergies": ["Aspirin"],
                },
            }
        }


class Citation(BaseModel):
    """Citation/reference model"""

    doc_id: str = Field(..., description="ID của tài liệu")
    question: str = Field(..., description="Câu hỏi gốc")
    answer: str = Field(..., description="Câu trả lời gốc từ bác sĩ")
    score: float = Field(..., description="Điểm relevance")


class Warning(BaseModel):
    """Safety warning model"""

    severity: str = Field(
        ..., description="Mức độ nghiêm trọng: low, medium, high"
    )
    message: str = Field(..., description="Nội dung cảnh báo")
    reason: str = Field(..., description="Lý do cảnh báo")
    affected_conditions: List[str] = Field(
        default_factory=list, description="Các bệnh/dị ứng bị ảnh hưởng"
    )


class RetrievedDocument(BaseModel):
    """Retrieved document model"""

    doc_id: str
    question: str
    answer: str
    score: float
    rank: int


# ===== Agent Result Schemas =====


class TriageResult(BaseModel):
    """Result from Triage Agent (Giai đoạn 1)"""

    is_medical: bool = Field(..., description="Truy vấn có liên quan y tế không")
    response: Optional[str] = Field(
        None, description="Phản hồi từ chối nếu không phải y tế"
    )
    suggested_title: Optional[str] = Field(
        None, description="Tiêu đề gợi ý cho cuộc hội thoại (5-8 từ)"
    )
    latency: float = Field(0.0, description="Thời gian xử lý (giây)")


class GenerationResult(BaseModel):
    """Result from Clinical RAG Agent (Giai đoạn 3)"""

    draft_response: str = Field(..., description="Bản nháp phản hồi y khoa")
    latency: float = Field(0.0, description="Thời gian xử lý (giây)")


class SafetyResult(BaseModel):
    """Result from Safety Guard Agent (Giai đoạn 4)"""

    final_response: str = Field(..., description="Phản hồi cuối cùng sau kiểm tra")
    warnings: List[Warning] = Field(
        default_factory=list, description="Danh sách cảnh báo an toàn"
    )
    is_safe: bool = Field(True, description="Phản hồi có an toàn không")
    latency: float = Field(0.0, description="Thời gian xử lý (giây)")


class PipelineMetadata(BaseModel):
    """Metadata about the processing pipeline"""

    triage_time: float = Field(0.0, description="Thời gian Triage Agent (giây)")
    retrieval_time: float = Field(0.0, description="Thời gian truy xuất (giây)")
    rerank_time: float = Field(0.0, description="Thời gian reranking (giây)")
    generation_time: float = Field(0.0, description="Thời gian sinh văn bản (giây)")
    safety_time: float = Field(0.0, description="Thời gian kiểm tra an toàn (giây)")
    triage_agent: str = Field("llama-3.3-70b-versatile", description="Model Triage")
    generation_agent: str = Field("gemini-2.5-flash", description="Model Generation")
    safety_agent: str = Field("llama-3.3-70b-versatile", description="Model Safety")


class ChatResponse(BaseModel):
    """Chat response model"""

    answer: str = Field(..., description="Câu trả lời từ AI")
    citations: List[Citation] = Field(
        default_factory=list, description="Danh sách trích dẫn"
    )
    warnings: List[Warning] = Field(
        default_factory=list, description="Danh sách cảnh báo an toàn"
    )
    retrieved_docs: List[RetrievedDocument] = Field(
        default_factory=list, description="Tài liệu đã truy xuất"
    )
    processing_time: float = Field(..., description="Thời gian xử lý (giây)")
    pipeline_metadata: Optional[PipelineMetadata] = Field(
        None, description="Chi tiết thời gian từng giai đoạn"
    )
    session_id: Optional[str] = Field(
        None, description="Session ID hội thoại"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Thời gian phản hồi"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Để giảm đau đầu, bạn có thể...",
                "citations": [
                    {
                        "doc_id": "VHQ_001",
                        "question": "Làm sao chữa đau đầu?",
                        "answer": "Có thể dùng paracetamol...",
                        "score": 0.95,
                    }
                ],
                "warnings": [],
                "retrieved_docs": [],
                "processing_time": 1.23,
                "pipeline_metadata": {
                    "triage_time": 0.05,
                    "retrieval_time": 0.30,
                    "rerank_time": 0.15,
                    "generation_time": 1.20,
                    "safety_time": 0.08,
                    "triage_agent": "llama-3.3-70b-versatile",
                    "generation_agent": "gemini-2.5-flash",
                    "safety_agent": "llama-3.3-70b-versatile",
                },
                "timestamp": "2024-01-15T10:30:00",
            }
        }


class HealthStatus(BaseModel):
    """API health check response"""

    status: str
    version: str
    qdrant_connected: bool
    embedding_model_loaded: bool
    reranker_loaded: bool
    gemini_configured: bool
    groq_configured: bool

# ===== Chat History Schemas =====

class ChatMessage(BaseModel):
    """Một tin nhắn trong phiên chat"""
    id: str = Field(alias="_id")
    session_id: str
    role: str  # 'user' | 'assistant'
    content: str
    citations: List[Citation] = []
    warnings: List[Warning] = []
    created_at: float

class ChatSessionInfo(BaseModel):
    """Thông tin cơ bản phiên chat (Dành cho list sidebar)"""
    id: str = Field(alias="_id")
    title: str
    is_pinned: Optional[bool] = False
    created_at: float
    updated_at: float

class ChatSessionDetails(ChatSessionInfo):
    """Thông tin chi tiết phiên chat bao gồm tin nhắn"""
    messages: List[ChatMessage]
