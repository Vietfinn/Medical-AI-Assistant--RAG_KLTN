from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class HealthProfile(BaseModel):
    """User health profile model"""
    chronic_diseases: List[str] = Field(default_factory=list, description="Danh sách bệnh mãn tính")
    allergies: List[str] = Field(default_factory=list, description="Danh sách dị ứng")
    current_medications: List[str] = Field(default_factory=list, description="Thuốc đang sử dụng")
    age: Optional[int] = Field(None, description="Tuổi")
    gender: Optional[str] = Field(None, description="Giới tính")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chronic_diseases": ["Đau dạ dày", "Tiểu đường"],
                "allergies": ["Aspirin", "Penicillin"],
                "current_medications": ["Metformin"],
                "age": 45,
                "gender": "Nam"
            }
        }

class ChatQuery(BaseModel):
    """Chat query request model"""
    query: str = Field(..., min_length=1, description="Câu hỏi của người dùng")
    health_profile: Optional[HealthProfile] = Field(None, description="Hồ sơ sức khỏe")
    session_id: Optional[str] = Field(None, description="Session ID để theo dõi hội thoại")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Làm sao để chữa đau đầu?",
                "health_profile": {
                    "chronic_diseases": ["Đau dạ dày"],
                    "allergies": ["Aspirin"]
                }
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
    severity: str = Field(..., description="Mức độ nghiêm trọng: low, medium, high")
    message: str = Field(..., description="Nội dung cảnh báo")
    reason: str = Field(..., description="Lý do cảnh báo")
    affected_conditions: List[str] = Field(default_factory=list, description="Các bệnh/dị ứng bị ảnh hưởng")

class RetrievedDocument(BaseModel):
    """Retrieved document model"""
    doc_id: str
    question: str
    answer: str
    score: float
    rank: int

class ChatResponse(BaseModel):
    """Chat response model"""
    answer: str = Field(..., description="Câu trả lời từ AI")
    citations: List[Citation] = Field(default_factory=list, description="Danh sách trích dẫn")
    warnings: List[Warning] = Field(default_factory=list, description="Danh sách cảnh báo an toàn")
    retrieved_docs: List[RetrievedDocument] = Field(default_factory=list, description="Tài liệu đã truy xuất")
    processing_time: float = Field(..., description="Thời gian xử lý (giây)")
    timestamp: datetime = Field(default_factory=datetime.now, description="Thời gian phản hồi")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Để giảm đau đầu, bạn có thể...",
                "citations": [
                    {
                        "doc_id": "VHQ_001",
                        "question": "Làm sao chữa đau đầu?",
                        "answer": "Có thể dùng paracetamol...",
                        "score": 0.95
                    }
                ],
                "warnings": [
                    {
                        "severity": "high",
                        "message": "CẢNH BÁO: Không nên dùng Aspirin",
                        "reason": "Bạn có tiền sử dị ứng với Aspirin",
                        "affected_conditions": ["Aspirin"]
                    }
                ],
                "retrieved_docs": [],
                "processing_time": 1.23,
                "timestamp": "2024-01-15T10:30:00"
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
