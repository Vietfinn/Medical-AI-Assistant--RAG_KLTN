from pydantic import BaseModel, Field, field_validator
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
    height: Optional[float] = Field(None, description="Chiều cao (cm)")
    weight: Optional[float] = Field(None, description="Cân nặng (kg)")

    @field_validator("height", "weight", "age", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

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
    corner_id: Optional[str] = Field(
        None, description="Corner ID (Góc sức khỏe) để kích hoạt cross-session context"
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
    """Result from Triage Agent (Giai đoạn 1) - Multi-task Routing"""

    is_medical: bool = Field(..., description="Truy vấn có liên quan y tế không")
    is_safe: bool = Field(True, description="Truy vấn có an toàn không (không chứa nội dung độc hại)")
    unsafe_category: Optional[str] = Field(
        None, description="Nhóm phân loại rủi ro (SELF_HARM, ILLEGAL_DRUGS, ILLEGAL_PRACTICE, HATE_SPEECH, OTHER)"
    )
    unsafe_reason: Optional[str] = Field(
        None, description="Lý do Llama phân loại là UNSAFE"
    )
    response: Optional[str] = Field(
        None, description="Phản hồi từ chối nếu không phải y tế hoặc không an toàn"
    )
    suggested_title: Optional[str] = Field(
        None, description="Tiêu đề gợi ý cho cuộc hội thoại (5-8 từ)"
    )
    latency: float = Field(0.0, description="Thời gian xử lý (giây)")


class UnsafeQueryLog(BaseModel):
    """Log câu hỏi nguy hiểm/độc hại để nghiên cứu & theo dõi hành vi"""

    id: Optional[str] = Field(None, description="ID của log tài liệu trong MongoDB")
    query: str = Field(..., description="Nội dung câu hỏi độc hại")
    category: str = Field(..., description="Nhóm phân loại: SELF_HARM | ILLEGAL_DRUGS | ILLEGAL_PRACTICE | HATE_SPEECH | OTHER")
    reason: str = Field("", description="Phân tích lý do từ Llama-3")
    session_id: Optional[str] = Field(None, description="Session ID của người dùng (nếu có)")
    timestamp: Optional[str] = Field(None, description="Thời gian ghi nhận (ISO 8601)")
    user_id: Optional[str] = Field(None, description="User ID")


class UnsafeLogsResponse(BaseModel):
    total: int = Field(..., description="Tổng số log")
    page: int = Field(..., description="Trang hiện tại")
    limit: int = Field(..., description="Số log mỗi trang")
    logs: List[UnsafeQueryLog] = Field(..., description="Danh sách log")


class UnsafeStatsResponse(BaseModel):
    total_unsafe: int = Field(..., description="Tổng số câu hỏi vi phạm")
    by_category: Dict[str, int] = Field(..., description="Thống kê theo category")
    recent_trend: List[Dict[str, Any]] = Field(..., description="Xu hướng gần đây (nếu có)")

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
    generation_agent: str = Field("llama-3.3-70b-versatile", description="Model Generation")
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
                    "generation_agent": "llama-3.3-70b-versatile",
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


# ===== Suggestion Feature Schemas =====


class ClinicalCondition(BaseModel):
    """Bệnh mạn tính theo chuẩn ICD-10, dùng cho chức năng gợi ý Bệnh tiền sử"""

    icd_code: str = Field(..., description="Mã ICD-10")
    label: str = Field(..., description="Tên bệnh tiếng Việt đầy đủ")
    category: str = Field(..., description="Nhóm bệnh (Tim mạch, Nội tiết, ...)")
    search_key: str = Field(..., description="Chuỗi không dấu để hỗ trợ fuzzy search")


class Ingredient(BaseModel):
    """Hoạt chất duy nhất trích xuất từ dữ liệu thuốc, dùng cho gợi ý Dị ứng"""

    name: str = Field(..., description="Tên hoạt chất (Title Case)")
    first_letter: str = Field(..., description="Chữ cái đầu (in hoa), dùng cho scroll A-Z")


class Medication(BaseModel):
    """Thuốc từ Long Châu, dùng cho gợi ý Thuốc đang sử dụng"""

    drug_name: str = Field(..., description="Tên thuốc thương mại")
    ingredients: List[str] = Field(default_factory=list, description="Mảng hoạt chất")
    category: str = Field(..., description="Nhóm thuốc (Thuốc giảm đau, ...)")
    search_key: str = Field(..., description="Chuỗi không dấu để hỗ trợ fuzzy search")


class SuggestionItem(BaseModel):
    """Một item gợi ý trả về cho Frontend"""

    label: str
    value: str
    category: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class SuggestionResponse(BaseModel):
    """Response chuẩn cho tất cả Suggestion API endpoints"""

    items: List[SuggestionItem]
    total: int
    query: Optional[str] = None


# ===== Feedback (RLHF) Schemas =====


class ChatFeedbackCreate(BaseModel):
    """Schema nhận feedback từ người dùng (POST /api/feedback)"""

    interaction_id: str = Field(..., description="ID duy nhất của cặp Chat (message_id của AI)")
    session_id: str = Field(..., description="Session ID của phiên chat")
    query: str = Field(..., description="Câu hỏi gốc của người dùng")
    ai_response: str = Field(..., description="Câu trả lời của AI bị đánh giá")
    retrieved_sources: List[Any] = Field(
        default_factory=list,
        description="Danh sách các nguồn RAG đã dùng để trả lời (Có thể là ID chuỗi hoặc Object chứa nội dung câu hỏi/trả lời)"
    )
    rating: int = Field(..., ge=-1, le=1, description="1 = Like, -1 = Dislike")
    reason_tags: List[str] = Field(
        default_factory=list,
        description="Các tag lỗi user chọn (VD: wrong_medical_info, irrelevant_source)"
    )
    text_feedback: Optional[str] = Field(
        default="",
        max_length=1000,
        description="Mô tả chi tiết thêm từ người dùng (trường Khác)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "interaction_id": "msg_abc123",
                "session_id": "sess_xyz",
                "query": "Thuốc Paracetamol có tác dụng gì?",
                "ai_response": "Paracetamol dùng để hạ sốt và giảm đau...",
                "retrieved_sources": ["VHQ_001", "VHQ_002"],
                "rating": -1,
                "reason_tags": ["wrong_medical_info", "irrelevant_source"],
                "text_feedback": "AI đề cập sai liều lượng cho trẻ em"
            }
        }


class AdminFeedbackUpdate(BaseModel):
    """Schema Admin cập nhật trạng thái xử lý feedback (PATCH /api/admin/feedbacks/{id})"""

    status: Optional[str] = Field(
        None,
        pattern="^(pending|resolved|ignored)$",
        description="Trạng thái xử lý: pending | resolved | ignored"
    )
    admin_notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Ghi chú Admin về cách khắc phục lỗi"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "resolved",
                "admin_notes": "Đã cập nhật lại tham số Hybrid Search Alpha từ 0.5 lên 0.7"
            }
        }


class BulkResolveRequest(BaseModel):
    """Schema cho request xử lý hàng loạt feedback"""
    
    tag: Optional[str] = Field(
        None,
        description="Tag lỗi cần lọc để xử lý hàng loạt"
    )


# ===== System Settings Schema =====


class SystemSettings(BaseModel):
    """Cấu hình hệ thống được lưu trong MongoDB (collection: system_settings)"""

    # RAG Configuration
    top_k: int = Field(default=5, ge=1, le=10, description="Số lượng tài liệu truy xuất sau Rerank")
    similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0, description="Ngưỡng tương đồng tối thiểu")

    # Safety Guardrails
    strict_mode: bool = Field(default=False, description="Chế độ nghiêm ngặt: chỉ trả lời dựa trên RAG")
    fallback_message: str = Field(
        default="Xin lỗi, tôi là trợ lý AI Y tế. Tôi không thể cung cấp lời khuyên cho vấn đề này. Vui lòng tham khảo ý kiến bác sĩ chuyên khoa.",
        max_length=500,
        description="Thông điệp từ chối khi AI kích hoạt phòng vệ"
    )
    blacklist: List[str] = Field(
        default_factory=lambda: ['tự tử', 'làm hại bản thân', 'chất kích thích'],
        description="Danh sách từ khóa cấm"
    )
    system_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Thông tin mô hình hệ thống và tham số cứng"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "top_k": 5,
                "similarity_threshold": 0.75,
                "strict_mode": False,
                "fallback_message": "Xin lỗi, tôi là trợ lý AI Y tế...",
                "blacklist": ["tự tử", "làm hại bản thân"],
            }
        }


# ===== Health Corner Schemas =====


class CornerCreate(BaseModel):
    """Request body để tạo Góc sức khỏe mới"""
    name: str = Field(..., min_length=1, max_length=100, description="Tên Góc sức khỏe")
    emoji: str = Field(default="🩺", description="Emoji đại diện cho Góc")


class CornerUpdate(BaseModel):
    """Request body để cập nhật Góc sức khỏe"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Tên mới")
    emoji: Optional[str] = Field(None, description="Emoji mới")


class CornerAssign(BaseModel):
    """Request body để gắn/gỡ session vào Góc sức khỏe"""
    corner_id: Optional[str] = Field(None, description="Corner ID để gắn, None để gỡ")
