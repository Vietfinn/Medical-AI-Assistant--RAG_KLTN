import logging
import time
import uuid
import datetime
import hmac
import hashlib
import base64
from contextlib import asynccontextmanager
from typing import Optional
from unidecode import unidecode

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from database.mongo import MongoDB, get_db
from qdrant_client import QdrantClient

from config import settings
from models import (
    ChatQuery,
    ChatResponse,
    HealthStatus,
    Citation,
    Warning,
    RetrievedDocument,
    PipelineMetadata,
    HealthProfile,
    SuggestionItem,
    SuggestionResponse,
    CornerCreate,
    CornerUpdate,
    CornerAssign,
    AdminFeedbackUpdate,
    BulkResolveRequest,
    UnsafeQueryLog,
    UnsafeLogsResponse,
    UnsafeStatsResponse,
    SystemSettings,
    ChatFeedbackCreate,
)
from services import (
    EmbeddingService,
    HybridRetriever,
    Reranker,
    ClinicalLLMService,
    GroqService,
    load_data_to_ram,
    search_conditions,
    get_ingredients,
    search_medications,
    get_medication_categories,
)
from services.email_service import configure_gmail, send_welcome_email
from agents import TriageAgent, ClinicalRAGAgent, SafetyGuardAgent
from auth import get_current_user, get_current_admin

# Configure logging & Sentry (PHẢI gọi trước mọi thứ khác)
from utils.logging_config import setup_logging
from utils.sentry_config import init_sentry

setup_logging()
init_sentry()
logger = logging.getLogger(__name__)


# Global service instances
embedding_service: Optional[EmbeddingService] = None
retriever: Optional[HybridRetriever] = None
reranker: Optional[Reranker] = None
clinical_llm_service: Optional[ClinicalLLMService] = None
triage_groq_service: Optional[GroqService] = None
safety_groq_service: Optional[GroqService] = None
qdrant_client: Optional[QdrantClient] = None



# Global agent instances
triage_agent: Optional[TriageAgent] = None
clinical_rag_agent: Optional[ClinicalRAGAgent] = None
safety_guard_agent: Optional[SafetyGuardAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting Medical AI Assistant API (Multi-Agent RAG)...")

    global embedding_service, retriever, reranker, clinical_llm_service, triage_groq_service, safety_groq_service
    global qdrant_client, triage_agent, clinical_rag_agent, safety_guard_agent

    try:
        # ===== Initialize Qdrant Client =====
        logger.info(f"Connecting to Qdrant in {settings.QDRANT_MODE} mode...")
        qdrant_params = settings.get_qdrant_client_params()
        logger.info(f"Qdrant connection params: {list(qdrant_params.keys())}")
        qdrant_client = QdrantClient(**qdrant_params)

        try:
            collections = qdrant_client.get_collections()
            logger.info(
                f"Connected to Qdrant successfully! Found {len(collections.collections)} collections"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {str(e)}")
            if settings.QDRANT_MODE == "cloud":
                logger.error("Vui lòng kiểm tra:")
                logger.error("1. QDRANT_CLOUD_URL có đúng format không?")
                logger.error("2. QDRANT_API_KEY có hợp lệ không?")
                logger.error("3. Cluster đã được tạo trên Qdrant Cloud chưa?")
                logger.error("4. Network/firewall có block connection không?")
            raise

        # ===== Initialize MongoDB =====
        db = await MongoDB.connect(url=settings.MONGODB_URL, db_name="medical_ai")
        try:
            mig_result = await db["sessions"].update_many(
                {"is_pinned": {"$exists": False}}, 
                {"$set": {"is_pinned": False}}
            )
            if mig_result.modified_count > 0:
                logger.info(f"  ✅ MongoDB Migration: Updated {mig_result.modified_count} sessions with explicit is_pinned: False")
        except Exception as mig_err:
            logger.error(f"  ❌ MongoDB Migration Error: {mig_err}")

        # ===== Create MongoDB Indexes for Production Performance =====
        try:
            logger.info("Creating MongoDB Indexes for Production Performance...")
            
            # Sessions compound index for sidebar listing (User ID + Pin status + Updated time)
            await db["sessions"].create_index([
                ("user_id", 1),
                ("is_pinned", -1),
                ("updated_at", -1)
            ], name="sessions_user_pin_update_idx")
            
            # Feedbacks indexing (status and timestamp)
            await db["chat_feedbacks"].create_index([
                ("status", 1),
                ("created_at", -1)
            ], name="feedbacks_status_created_idx")
            
            # Unsafe logs indexing
            await db["unsafe_logs"].create_index([
                ("user_id", 1),
                ("timestamp", -1)
            ], name="unsafe_logs_user_timestamp_idx")
            
            logger.info("  ✅ MongoDB Indexes created successfully.")
        except Exception as idx_err:
            logger.error(f"  ❌ MongoDB Indexing Error: {idx_err}")

        # ===== Initialize In-Memory Suggestion Engine cache =====
        logger.info("Initializing Suggestion Engine cache...")
        await load_data_to_ram(MongoDB.get_db())

        # ===== Initialize Gmail SMTP Email =====
        configure_gmail()

        # ===== Initialize Embedding Service =====
        logger.info("Loading embedding model...")
        embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
        embedding_service.load_model()

        # ===== Initialize Retriever =====
        logger.info("Initializing retriever...")
        retriever = HybridRetriever(
            qdrant_client=qdrant_client,
            collection_name=settings.QDRANT_COLLECTION,
            embedding_service=embedding_service,
            alpha=settings.HYBRID_ALPHA,
        )

        # ===== Initialize Reranker (Cohere API) =====
        logger.info("Initializing Cohere Reranker...")
        reranker = Reranker(api_key=settings.COHERE_API_KEY, model_name=settings.RERANKER_MODEL)
        reranker.load_model()

        # ===== Initialize Clinical LLM Service (Clinical RAG Agent) =====
        logger.info("Configuring Clinical Groq LLM API...")
        clinical_llm_service = ClinicalLLMService(
            api_key=settings.GROQ_API_KEY2, model_name=settings.GROQ_MODEL
        )
        clinical_llm_service.configure()

        # ===== Initialize Groq Service (Triage Agent) =====
        logger.info("Configuring Groq API for Triage Agent...")
        triage_groq_service = GroqService(
            api_key=settings.GROQ_API_KEY1, model_name=settings.GROQ_MODEL
        )
        triage_groq_service.configure()

        # ===== Initialize Groq Service (Safety Guard Agent) =====
        logger.info("Configuring Groq API for Safety Guard Agent...")
        safety_groq_service = GroqService(
            api_key=settings.GROQ_API_KEY3, model_name=settings.GROQ_MODEL
        )
        safety_groq_service.configure()

        # ===== Initialize Agents =====
        logger.info("Initializing Multi-Agent system...")

        triage_agent = TriageAgent(groq_service=triage_groq_service)
        logger.info("  ✅ Triage Agent (Llama 3 / Groq) initialized")

        clinical_rag_agent = ClinicalRAGAgent(llm_service=clinical_llm_service)
        logger.info("  ✅ Clinical RAG Agent (Llama 3.3 / Groq) initialized")

        safety_guard_agent = SafetyGuardAgent(groq_service=safety_groq_service)
        logger.info("  ✅ Safety Guard Agent (Llama 3 / Groq) initialized")

        logger.info("=" * 60)
        logger.info("✅ All services and agents initialized successfully!")
        logger.info(f"🗄️  Qdrant Mode: {settings.QDRANT_MODE.upper()}")
        if settings.QDRANT_MODE == "cloud":
            logger.info(f"☁️  Cloud URL: {settings.QDRANT_CLOUD_URL[:50]}...")
        else:
            logger.info(f"🏠 Local: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        logger.info(f"🤖 Triage/Safety Agent: {settings.GROQ_MODEL}")
        logger.info(f"🧠 Clinical RAG Agent: {settings.GROQ_MODEL}")
        logger.info("⚕️  Medical AI Assistant API (Multi-Agent RAG) is ready!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Medical AI Assistant API...")
    if qdrant_client:
        qdrant_client.close()
    await MongoDB.close()


# Create FastAPI app
app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_active_system_settings(db) -> dict:
    """
    Hàm helper lấy cấu hình hệ thống từ MongoDB hoặc trả về mặc định.
    Gộp với cấu hình mặc định để đảm bảo tất cả các trường đều tồn tại đầy đủ.
    """
    default_settings = {
        "top_k": 5,
        "similarity_threshold": 0.75,
        "strict_mode": False,
        "fallback_message": "Xin lỗi, tôi là trợ lý AI Y tế. Tôi không thể cung cấp lời khuyên cho vấn đề này. Vui lòng tham khảo ý kiến bác sĩ chuyên khoa.",
        "blacklist": ['tự tử', 'làm hại bản thân', 'chất kích thích']
    }
    try:
        settings_doc = await db["system_settings"].find_one({})
        if settings_doc:
            # Gộp các trường để bảo vệ chống thiếu dữ liệu trong DB
            for k, v in default_settings.items():
                if k not in settings_doc:
                    settings_doc[k] = v
            return settings_doc
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn cấu hình hệ thống từ MongoDB: {e}")
    return default_settings


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Medical AI Assistant API (Multi-Agent RAG)",
        "version": settings.APP_VERSION,
        "status": "running",
        "architecture": "Heterogeneous Multi-Agent RAG",
        "agents": {
            "triage": settings.GROQ_MODEL,
            "clinical_rag": settings.GROQ_MODEL,
            "safety_guard": settings.GROQ_MODEL,
        },
        "qdrant_mode": settings.QDRANT_MODE,
    }


@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint"""
    return HealthStatus(
        status="healthy",
        version=settings.APP_VERSION,
        qdrant_connected=qdrant_client is not None,
        embedding_model_loaded=embedding_service is not None
        and embedding_service.is_loaded(),
        reranker_loaded=reranker is not None and reranker.is_loaded(),
        gemini_configured=clinical_llm_service is not None and clinical_llm_service.is_configured(),
        groq_configured=triage_groq_service is not None and triage_groq_service.is_configured()
        and safety_groq_service is not None and safety_groq_service.is_configured(),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    query: ChatQuery,
    current_user: dict = Depends(get_current_user),
):
    """
    Main chat endpoint for medical Q&A
    ... [Comments truncated for brevity] ...
    """
    # Check if the user is banned from using the system
    if current_user.get("is_banned", False):
        raise HTTPException(
            status_code=403,
            detail="Tài khoản của bạn đã bị cấm khỏi hệ thống trợ lý y tế AI do vi phạm quy tắc an toàn."
        )

    start_time = time.time()
    pipeline_meta = {}

    try:
        db = get_db()
        active_settings = await get_active_system_settings(db)
        
        session_id = query.session_id
        is_new_session = False
        chat_history = []
        
        # Bước 1 & Bước 2: Tiếp nhận & Nạp Trí nhớ ngắn hạn
        if not session_id:
            session_id = str(uuid.uuid4())
            is_new_session = True
            
            session_doc = {
                "_id": session_id,
                "user_id": current_user["user_id"],
                "title": "Đoạn chat mới",
                "created_at": time.time(),
                "updated_at": time.time(),
                "messages": []
            }
            if query.corner_id:
                session_doc["corner_id"] = query.corner_id
                
            await db["sessions"].insert_one(session_doc)
            logger.info(f"Created new chat session: {session_id} for user: {current_user['user_id']}")
        else:
            # Check ownership and fetch messages
            session_doc = await db["sessions"].find_one(
                {"_id": session_id, "user_id": current_user["user_id"]},
                {"messages": {"$slice": -6}}
            )
            
            if session_doc and "messages" in session_doc:
                for msg in session_doc["messages"]:
                    chat_history.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            else:
                logger.warning(f"Session {session_id} not found, starting fresh context.")

        # Kiểm tra từ khóa cấm từ cấu hình hệ thống
        query_lower = query.query.lower()
        if any(word.lower() in query_lower for word in active_settings["blacklist"]):
            logger.info(f"Query matches blacklist keyword. Early exit with fallback message.")
            processing_time = time.time() - start_time
            
            # Lưu lịch sử chat
            created_at = time.time()
            assistant_msg_id = str(uuid.uuid4())
            await db["sessions"].update_one(
                {"_id": session_id, "user_id": current_user["user_id"]},
                {
                    "$push": {
                        "messages": {
                            "$each": [
                                {"id": str(uuid.uuid4()), "role": "user", "content": query.query, "created_at": created_at - 0.001},
                                {"id": assistant_msg_id, "role": "assistant", "content": active_settings["fallback_message"], "citations": [], "warnings": [], "created_at": created_at},
                            ]
                        }
                    },
                    "$set": {"updated_at": created_at}
                }
            )
            await touch_corner_recency(db, session_id, current_user["user_id"], query.corner_id)
            
            return ChatResponse(
                answer=active_settings["fallback_message"],
                citations=[],
                warnings=[],
                retrieved_docs=[],
                processing_time=processing_time,
                pipeline_metadata=PipelineMetadata(
                    triage_time=0.0,
                    triage_agent=settings.GROQ_MODEL,
                    generation_agent=settings.GROQ_MODEL,
                    safety_agent=settings.GROQ_MODEL,
                ),
                session_id=session_id
            )

        logger.info(f"Processing query: {query.query[:100]}... (Context length: {len(chat_history)} msgs)")

        # ============================================================
        # GIAI ĐOẠN 1: Triage Agent (Llama 3 / Groq) - Intent Classification
        # ============================================================
        logger.info("━━━ Giai đoạn 1: Triage Agent ━━━")

        if settings.ENABLE_TRIAGE_AGENT:
            triage_result = triage_agent.execute(query=query.query, chat_history=chat_history)
            pipeline_meta["triage_time"] = triage_result.latency

            if is_new_session and triage_result.suggested_title:
                await get_db()["sessions"].update_one(
                    {"_id": session_id},
                    {"$set": {"title": triage_result.suggested_title}}
                )

            # Log unsafe query to database if detected
            if not triage_result.is_safe:
                try:
                    import datetime
                    await get_db()["unsafe_logs"].insert_one({
                        "query": query.query,
                        "category": triage_result.unsafe_category or "OTHER",
                        "reason": triage_result.unsafe_reason or "Nội dung vi phạm chính sách",
                        "session_id": session_id,
                        "timestamp": datetime.datetime.utcnow().isoformat(),
                        "user_id": current_user["user_id"]
                    })
                    logger.info(f"Logged unsafe query: {triage_result.unsafe_category}")
                except Exception as log_err:
                    logger.error(f"Error logging unsafe query to MongoDB: {log_err}")

            if not triage_result.is_medical:
                processing_time = time.time() - start_time
                logger.info("Query classified as NON_MEDICAL/UNSAFE → Early Exit")
                
                # Lưu lịch sử chat
                created_at = time.time()
                assistant_msg_id = str(uuid.uuid4())
                await get_db()["sessions"].update_one(
                    {"_id": session_id, "user_id": current_user["user_id"]},
                    {
                        "$push": {
                            "messages": {
                                "$each": [
                                    {"id": str(uuid.uuid4()), "role": "user", "content": query.query, "created_at": created_at - 0.001},
                                    {"id": assistant_msg_id, "role": "assistant", "content": triage_result.response, "citations": [], "warnings": [], "created_at": created_at},
                                ]
                            }
                        },
                        "$set": {"updated_at": created_at}
                    }
                )
                await touch_corner_recency(get_db(), session_id, current_user["user_id"], query.corner_id)
                
                return ChatResponse(
                    answer=triage_result.response,
                    citations=[],
                    warnings=[],
                    retrieved_docs=[],
                    processing_time=processing_time,
                    pipeline_metadata=PipelineMetadata(
                        triage_time=triage_result.latency,
                        triage_agent=settings.GROQ_MODEL,
                        generation_agent=settings.GROQ_MODEL,
                        safety_agent=settings.GROQ_MODEL,
                    ),
                    session_id=session_id
                )
        else:
            pipeline_meta["triage_time"] = 0.0
            logger.info("Triage Agent disabled, proceeding to retrieval")

        # ============================================================
        # GIAI ĐOẠN 2: Hybrid Retrieval & Reranking
        # ============================================================
        logger.info("━━━ Giai đoạn 2: Hybrid Retrieval & Reranking ━━━")

        retrieval_start = time.time()
        retrieved_docs = retriever.hybrid_search(
            query=query.query, top_k=settings.TOP_K_RETRIEVAL
        )
        pipeline_meta["retrieval_time"] = time.time() - retrieval_start
        logger.info(f"Retrieved {len(retrieved_docs)} documents")

        rerank_start = time.time()
        reranked_docs = reranker.rerank(
            query=query.query, documents=retrieved_docs, top_k=active_settings["top_k"]
        )
        pipeline_meta["rerank_time"] = time.time() - rerank_start
        logger.info(f"Reranked to top {len(reranked_docs)} documents")

        # ============================================================
        # GIAI ĐOẠN 3: Clinical RAG Agent (Llama 3.3 / Groq) - Generation
        # ============================================================
        logger.info("━━━ Giai đoạn 3: Clinical RAG Agent ━━━")

        # Load HealthProfile from user account (MongoDB) instead of request body
        health_profile_dict = current_user.get("health_profile")

        generation_result = clinical_rag_agent.execute(
            query=query.query,
            documents=reranked_docs,
            health_profile=health_profile_dict,
            chat_history=chat_history,
            strict_mode=active_settings["strict_mode"],
        )
        pipeline_meta["generation_time"] = generation_result.latency
        logger.info("Draft response generated successfully")

        # ============================================================
        # GIAI ĐOẠN 4: Safety Guard Agent (Llama 3 / Groq) - Validation
        # ============================================================
        logger.info("━━━ Giai đoạn 4: Safety Guard Agent ━━━")

        warnings = []
        final_response = generation_result.draft_response

        # Build HealthProfile model from DB data for Safety Agent
        safety_health_profile = None
        if health_profile_dict:
            try:
                safety_health_profile = HealthProfile(**health_profile_dict)
            except Exception:
                logger.warning("Failed to parse health profile for Safety Agent")

        if settings.ENABLE_SAFETY_AGENT and safety_health_profile:
            safety_result = safety_guard_agent.execute(
                draft_response=generation_result.draft_response,
                health_profile=safety_health_profile,
            )
            pipeline_meta["safety_time"] = safety_result.latency
            warnings = safety_result.warnings
            final_response = safety_result.final_response
            logger.info(
                f"Safety check complete: {len(warnings)} warnings found"
            )
        else:
            pipeline_meta["safety_time"] = 0.0
            logger.info("Safety Agent skipped (disabled or no health profile)")

        # ============================================================
        # GIAI ĐOẠN 5: Serialization & Client Delivery
        # ============================================================
        logger.info("━━━ Giai đoạn 5: Serialization ━━━")

        citations = [
            Citation(
                doc_id=str(doc.get("doc_id", "")),
                question=doc.get("question", ""),
                answer=doc.get("answer", ""),
                score=doc.get("rerank_score", doc.get("score", 0)),
            )
            for doc in reranked_docs
        ]

        retrieved_info = [
            RetrievedDocument(
                doc_id=str(doc.get("doc_id", "")),
                question=doc.get("question", ""),
                answer=doc.get("answer", ""),
                score=doc.get("score", 0),
                rank=idx + 1,
            )
            for idx, doc in enumerate(reranked_docs)
        ]

        processing_time = time.time() - start_time

        pipeline_metadata = PipelineMetadata(
            triage_time=pipeline_meta.get("triage_time", 0.0),
            retrieval_time=pipeline_meta.get("retrieval_time", 0.0),
            rerank_time=pipeline_meta.get("rerank_time", 0.0),
            generation_time=pipeline_meta.get("generation_time", 0.0),
            safety_time=pipeline_meta.get("safety_time", 0.0),
            triage_agent=settings.GROQ_MODEL,
            generation_agent=settings.GROQ_MODEL,
            safety_agent=settings.GROQ_MODEL,
        )

        logger.info(f"Request processed in {processing_time:.2f}s")
        logger.info(
            f"  ├─ Triage:     {pipeline_meta.get('triage_time', 0):.3f}s"
        )
        logger.info(
            f"  ├─ Retrieval:  {pipeline_meta.get('retrieval_time', 0):.3f}s"
        )
        logger.info(
            f"  ├─ Rerank:     {pipeline_meta.get('rerank_time', 0):.3f}s"
        )
        logger.info(
            f"  ├─ Generation: {pipeline_meta.get('generation_time', 0):.3f}s"
        )
        logger.info(
            f"  └─ Safety:     {pipeline_meta.get('safety_time', 0):.3f}s"
        )

        response_obj = ChatResponse(
            answer=final_response,
            citations=citations,
            warnings=warnings,
            retrieved_docs=retrieved_info,
            processing_time=processing_time,
            pipeline_metadata=pipeline_metadata,
            session_id=session_id
        )

        # Bước 4: Ghi đè lịch sử (Update) bằng $push (Array Embedding) cực nhanh
        created_at = time.time()
        
        user_msg_doc = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": query.query,
            "created_at": created_at - 0.001
        }
        
        assistant_msg_doc = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response_obj.answer,
            "citations": [c.model_dump() for c in response_obj.citations],
            "warnings": [w.model_dump() for w in response_obj.warnings],
            "created_at": created_at
        }
        
        # Nhét đồng thời 2 mảng vào array messages (chỉ update nếu đúng user_id)
        await get_db()["sessions"].update_one(
            {"_id": session_id, "user_id": current_user["user_id"]},
            {
                "$push": {
                    "messages": {
                        "$each": [user_msg_doc, assistant_msg_doc]
                    }
                },
                "$set": {"updated_at": created_at}
            }
        )

        # Cập nhật last_accessed_at cho Góc sức khỏe nếu session thuộc về Góc đó khi có tương tác (hỏi)
        await touch_corner_recency(get_db(), session_id, current_user["user_id"], query.corner_id)

        return response_obj

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def touch_corner_recency(db, session_id: str, user_id: str, corner_id_opt: Optional[str] = None):
    """Cập nhật thời gian truy cập gần nhất (last_accessed_at) cho Góc sức khỏe"""
    corner_id = corner_id_opt
    if not corner_id:
        session_doc = await db["sessions"].find_one({"_id": session_id, "user_id": user_id}, {"corner_id": 1})
        if session_doc:
            corner_id = session_doc.get("corner_id")
    if corner_id:
        try:
            await db["health_corners"].update_one(
                {"_id": corner_id, "user_id": user_id},
                {"$set": {"last_accessed_at": time.time()}}
            )
            logger.info(f"Touched corner recency {corner_id} on chat update")
        except Exception as err:
            logger.error(f"Error touching corner recency: {err}")


@app.post("/api/chat/stream")
async def chat_stream(
    query: ChatQuery,
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    Streams Clinical RAG generation token-by-token for real-time UX.
    """
    import json as _json
    from fastapi.responses import StreamingResponse

    # Check if the user is banned from using the system
    if current_user.get("is_banned", False):
        raise HTTPException(
            status_code=403,
            detail="Tài khoản của bạn đã bị cấm khỏi hệ thống trợ lý y tế AI do vi phạm quy tắc an toàn."
        )

    def sse_event(event: str, data) -> str:
        """Format a single SSE event line"""
        return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream_generator():
        start_time = time.time()
        pipeline_meta = {}
        full_response_text = ""

        try:
            db = get_db()
            active_settings = await get_active_system_settings(db)
            
            # ===== SESSION MANAGEMENT =====
            session_id = query.session_id
            is_new_session = False
            chat_history = []

            if not session_id:
                session_id = str(uuid.uuid4())
                is_new_session = True

                session_doc = {
                    "_id": session_id,
                    "user_id": current_user["user_id"],
                    "title": "Đoạn chat mới",
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "is_pinned": False,
                    "messages": []
                }
                if query.corner_id:
                    session_doc["corner_id"] = query.corner_id

                await db["sessions"].insert_one(session_doc)
                logger.info(f"[Stream] Created new session: {session_id}")
            else:
                session_doc = await db["sessions"].find_one(
                    {"_id": session_id, "user_id": current_user["user_id"]},
                    {"messages": {"$slice": -6}}
                )
                if session_doc and "messages" in session_doc:
                    for msg in session_doc["messages"]:
                        chat_history.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

            # Kiểm tra từ khóa cấm từ cấu hình hệ thống
            query_lower = query.query.lower()
            if any(word.lower() in query_lower for word in active_settings["blacklist"]):
                logger.info(f"[Stream] Query matches blacklist keyword. Early exit with fallback message.")
                processing_time = time.time() - start_time
                assistant_msg_id = str(uuid.uuid4())
                yield sse_event("token", {"content": active_settings["fallback_message"]})
                yield sse_event("done", {
                    "citations": [],
                    "warnings": [],
                    "session_id": session_id,
                    "processing_time": round(processing_time, 2),
                    "message_id": assistant_msg_id,
                })
                
                # Lưu lịch sử chat
                created_at = time.time()
                await db["sessions"].update_one(
                    {"_id": session_id, "user_id": current_user["user_id"]},
                    {
                        "$push": {
                            "messages": {
                                "$each": [
                                    {"id": str(uuid.uuid4()), "role": "user", "content": query.query, "created_at": created_at - 0.001},
                                    {"id": assistant_msg_id, "role": "assistant", "content": active_settings["fallback_message"], "citations": [], "warnings": [], "created_at": created_at},
                                ]
                            }
                        },
                        "$set": {"updated_at": created_at}
                    }
                )
                await touch_corner_recency(db, session_id, current_user["user_id"], query.corner_id)
                return

            # ===== GIAI ĐOẠN 1: TRIAGE AGENT =====
            yield sse_event("status", {"message": "Đang phân tích câu hỏi..."})

            if settings.ENABLE_TRIAGE_AGENT:
                triage_result = triage_agent.execute(query=query.query, chat_history=chat_history)
                pipeline_meta["triage_time"] = triage_result.latency

                if is_new_session and triage_result.suggested_title:
                    await get_db()["sessions"].update_one(
                        {"_id": session_id},
                        {"$set": {"title": triage_result.suggested_title}}
                    )

                # Log unsafe query to database if detected
                if not triage_result.is_safe:
                    try:
                        import datetime
                        await get_db()["unsafe_logs"].insert_one({
                            "query": query.query,
                            "category": triage_result.unsafe_category or "OTHER",
                            "reason": triage_result.unsafe_reason or "Nội dung vi phạm chính sách",
                            "session_id": session_id,
                            "timestamp": datetime.datetime.utcnow().isoformat(),
                            "user_id": current_user["user_id"]
                        })
                        logger.info(f"[Stream] Logged unsafe query: {triage_result.unsafe_category}")
                    except Exception as log_err:
                        logger.error(f"[Stream] Error logging unsafe query to MongoDB: {log_err}")

                if not triage_result.is_medical:
                    processing_time = time.time() - start_time
                    logger.info("[Stream] NON_MEDICAL/UNSAFE → Early Exit")
                    assistant_msg_id = str(uuid.uuid4())
                    yield sse_event("token", {"content": triage_result.response})
                    yield sse_event("done", {
                        "citations": [],
                        "warnings": [],
                        "session_id": session_id,
                        "processing_time": round(processing_time, 2),
                        "message_id": assistant_msg_id,
                    })

                    created_at = time.time()
                    await get_db()["sessions"].update_one(
                        {"_id": session_id, "user_id": current_user["user_id"]},
                        {
                            "$push": {
                                "messages": {
                                    "$each": [
                                        {"id": str(uuid.uuid4()), "role": "user", "content": query.query, "created_at": created_at - 0.001},
                                        {"id": assistant_msg_id, "role": "assistant", "content": triage_result.response, "citations": [], "warnings": [], "created_at": created_at},
                                    ]
                                }
                            },
                            "$set": {"updated_at": created_at}
                        }
                    )
                    await touch_corner_recency(get_db(), session_id, current_user["user_id"], query.corner_id)
                    return
            else:
                pipeline_meta["triage_time"] = 0.0

            # ===== GIAI ĐOẠN 2: HYBRID RETRIEVAL & RERANKING =====
            yield sse_event("status", {"message": "Đang tìm kiếm tài liệu y khoa..."})

            retrieval_start = time.time()
            retrieved_docs = retriever.hybrid_search(
                query=query.query, top_k=settings.TOP_K_RETRIEVAL
            )
            pipeline_meta["retrieval_time"] = time.time() - retrieval_start

            yield sse_event("status", {"message": "Đang sắp xếp kết quả..."})

            rerank_start = time.time()
            reranked_docs = reranker.rerank(
                query=query.query, documents=retrieved_docs, top_k=active_settings["top_k"]
            )
            pipeline_meta["rerank_time"] = time.time() - rerank_start

            # ===== GIAI ĐOẠN 3: CLINICAL RAG AGENT (STREAMING) =====
            yield sse_event("status", {"message": "Đang soạn câu trả lời..."})

            health_profile_dict = current_user.get("health_profile")
            generation_start = time.time()

            import asyncio
            import queue
            import threading

            chunk_queue = queue.Queue()
            _SENTINEL = object()

            def _run_sync_stream():
                try:
                    for chunk in clinical_rag_agent.execute_stream(
                        query=query.query,
                        documents=reranked_docs,
                        health_profile=health_profile_dict,
                        chat_history=chat_history,
                        strict_mode=active_settings["strict_mode"],
                    ):
                        chunk_queue.put(chunk)
                except Exception as exc:
                    chunk_queue.put(exc)
                finally:
                    chunk_queue.put(_SENTINEL)

            thread = threading.Thread(target=_run_sync_stream, daemon=True)
            thread.start()

            while True:
                item = await asyncio.get_event_loop().run_in_executor(
                    None, chunk_queue.get
                )
                if item is _SENTINEL:
                    break
                if isinstance(item, Exception):
                    raise item
                full_response_text += item
                yield sse_event("token", {"content": item})

            thread.join(timeout=5)
            pipeline_meta["generation_time"] = time.time() - generation_start
            logger.info(f"[Stream] Generation complete ({len(full_response_text)} chars)")

            # ===== GIAI ĐOẠN 4: SAFETY GUARD AGENT =====
            warnings = []
            final_response = full_response_text

            safety_health_profile = None
            if health_profile_dict:
                try:
                    safety_health_profile = HealthProfile(**health_profile_dict)
                except Exception:
                    logger.warning("[Stream] Failed to parse health profile for Safety Agent")

            if settings.ENABLE_SAFETY_AGENT and safety_health_profile:
                yield sse_event("status", {"message": "Đang kiểm tra an toàn..."})

                safety_result = safety_guard_agent.execute(
                    draft_response=full_response_text,
                    health_profile=safety_health_profile,
                )
                pipeline_meta["safety_time"] = safety_result.latency
                warnings = safety_result.warnings
                final_response = safety_result.final_response

                if warnings:
                    yield sse_event("warnings", [w.model_dump() for w in warnings])

                if safety_result.final_response != full_response_text:
                    yield sse_event("replace", {"content": safety_result.final_response})
                    final_response = safety_result.final_response
            else:
                pipeline_meta["safety_time"] = 0.0

            # ===== GIAI ĐOẠN 5: SERIALIZATION & DONE =====
            citations = [
                {
                    "doc_id": str(doc.get("doc_id", "")),
                    "question": doc.get("question", ""),
                    "answer": doc.get("answer", ""),
                    "score": doc.get("rerank_score", doc.get("score", 0)),
                }
                for doc in reranked_docs
            ]

            processing_time = time.time() - start_time
            logger.info(f"[Stream] Total: {processing_time:.2f}s")

            # ===== SAVE TO MONGODB =====
            created_at = time.time()
            assistant_msg_id = str(uuid.uuid4())
            user_msg_doc = {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": query.query,
                "created_at": created_at - 0.001
            }
            assistant_msg_doc = {
                "id": assistant_msg_id,
                "role": "assistant",
                "content": final_response,
                "citations": citations,
                "warnings": [w.model_dump() for w in warnings] if warnings else [],
                "created_at": created_at
            }

            yield sse_event("done", {
                "citations": citations,
                "warnings": [w.model_dump() for w in warnings] if warnings else [],
                "session_id": session_id,
                "processing_time": round(processing_time, 2),
                "message_id": assistant_msg_id,
            })

            await get_db()["sessions"].update_one(
                {"_id": session_id, "user_id": current_user["user_id"]},
                {
                    "$push": {
                        "messages": {
                            "$each": [user_msg_doc, assistant_msg_doc]
                        }
                    },
                    "$set": {"updated_at": created_at}
                }
            )

            # Cập nhật last_accessed_at cho Góc sức khỏe nếu session thuộc về Góc đó khi có tương tác (hỏi) qua Stream
            await touch_corner_recency(get_db(), session_id, current_user["user_id"], query.corner_id)

        except Exception as e:
            logger.error(f"[Stream] Error: {str(e)}", exc_info=True)
            yield sse_event("error", {"message": str(e)})

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/profile")
async def save_profile(
    profile: dict,
    current_user: dict = Depends(get_current_user),
):
    """Save user health profile to MongoDB (linked to authenticated user) - overwrites entire profile"""
    user_id = current_user["user_id"]
    logger.info(f"Profile POST request from user: {user_id}")

    db = get_db()
    await db["users"].update_one(
        {"_id": user_id},
        {
            "$set": {
                "health_profile": profile,
                "updated_at": time.time(),
            }
        },
    )
    return {"status": "success", "message": "Hồ sơ sức khỏe đã được lưu thành công"}


@app.patch("/api/profile")
async def patch_profile(
    profile: dict,
    current_user: dict = Depends(get_current_user),
):
    """Update user health profile fields in MongoDB (linked to authenticated user) - partial update"""
    user_id = current_user["user_id"]
    logger.info(f"Profile PATCH request from user: {user_id}")

    db = get_db()
    update_fields = {}
    for key, value in profile.items():
        update_fields[f"health_profile.{key}"] = value
    update_fields["updated_at"] = time.time()

    await db["users"].update_one(
        {"_id": user_id},
        {
            "$set": update_fields
        },
    )
    return {"status": "success", "message": "Hồ sơ sức khỏe đã được cập nhật thành công"}


@app.get("/api/stats")
async def get_stats():
    """Get API statistics"""
    try:
        collection_info = qdrant_client.get_collection(settings.QDRANT_COLLECTION)

        return {
            "total_documents": collection_info.points_count,
            "embedding_dimension": embedding_service.get_embedding_dimension(),
            "qdrant_mode": settings.QDRANT_MODE,
            "architecture": "Heterogeneous Multi-Agent RAG",
            "models": {
                "embedding": settings.EMBEDDING_MODEL,
                "reranker": settings.RERANKER_MODEL,
                "triage_agent": settings.GROQ_MODEL,
                "clinical_rag_agent": settings.GROQ_MODEL,
                "safety_guard_agent": settings.GROQ_MODEL,
            },
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== SUGGESTION REST API =====

@app.get("/api/suggestions/conditions", response_model=SuggestionResponse)
async def get_condition_suggestions(q: Optional[str] = ""):
    """Autocomplete suggestions for chronic conditions"""
    try:
        results = search_conditions(q)
        items = [
            SuggestionItem(
                label=f"{r.get('icd_code')} - {r.get('label')}",
                value=r.get('label'),
                category=r.get('category'),
            )
            for r in results
        ]
        return SuggestionResponse(items=items, total=len(items), query=q)
    except Exception as e:
        logger.error(f"Error fetching condition suggestions: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch condition suggestions")


@app.get("/api/suggestions/ingredients", response_model=SuggestionResponse)
async def get_ingredient_suggestions(q: Optional[str] = ""):
    """Autocomplete suggestions for allergies (ingredients)"""
    try:
        results = get_ingredients(q)
        items = [
            SuggestionItem(
                label=r.get('name', ''),
                value=r.get('name', ''),
                category=r.get('first_letter'),
            )
            for r in results
        ]
        return SuggestionResponse(items=items, total=len(items), query=q)
    except Exception as e:
        logger.error(f"Error fetching ingredient suggestions: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch ingredient suggestions")


@app.get("/api/suggestions/medications", response_model=SuggestionResponse)
async def get_medication_suggestions(q: Optional[str] = "", category: Optional[str] = None):
    """Autocomplete suggestions for medications"""
    try:
        results = search_medications(q, category)
        items = [
            SuggestionItem(
                label=r.get('drug_name', ''),
                value=r.get('drug_name', ''),
                category=r.get('category'),
                meta={"ingredients": r.get('ingredients', [])}
            )
            for r in results
        ]
        return SuggestionResponse(items=items, total=len(items), query=q)
    except Exception as e:
        logger.error(f"Error fetching medication suggestions: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch medication suggestions")


@app.get("/api/suggestions/categories")
async def get_medications_categories():
    """Get list of unique medication categories"""
    try:
        categories = get_medication_categories()
        return categories
    except Exception as e:
        logger.error(f"Error fetching medication categories: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch medication categories")


@app.post("/api/suggestions/refresh-cache")
async def refresh_suggestion_cache():
    """Refresh the in-memory suggestion engine cache from MongoDB"""
    try:
        await load_data_to_ram(MongoDB.get_db())
        return {"status": "success", "message": "Suggestion cache refreshed successfully"}
    except Exception as e:
        logger.error(f"Error refreshing cache: {e}")
        raise HTTPException(status_code=500, detail="Cannot refresh suggestion cache")


# ===== PROFILE READ API =====

@app.get("/api/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's health profile from MongoDB"""
    try:
        user_id = current_user["user_id"]
        user_doc = await get_db()["users"].find_one({"_id": user_id}, {"health_profile": 1})
        if user_doc and "health_profile" in user_doc:
            return user_doc["health_profile"]
        return {
            "chronic_diseases": [],
            "allergies": [],
            "current_medications": [],
            "age": None,
            "gender": "",
            "height": None,
            "weight": None,
        }
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch health profile")


# ===== SESSION EXTENDED REST APIs =====

@app.get("/api/sessions/search")
async def search_sessions(q: str, current_user: dict = Depends(get_current_user)):
    """Search user chat sessions by title"""
    try:
        user_id = current_user["user_id"]
        cursor = get_db()["sessions"].find(
            {
                "user_id": user_id,
                "title": {"$regex": q, "$options": "i"}
            },
            {"messages": 0}
        ).sort([("is_pinned", -1), ("updated_at", -1)]).limit(50)
        
        sessions = await cursor.to_list(length=50)
        return sessions
    except Exception as e:
        logger.error(f"Error searching sessions: {e}")
        raise HTTPException(status_code=500, detail="Cannot search sessions")


@app.delete("/api/sessions/{session_id}/last-qa")
async def delete_last_qa(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete the last Q&A turn (last 2 messages) from a chat session"""
    try:
        user_id = current_user["user_id"]
        session = await get_db()["sessions"].find_one({"_id": session_id, "user_id": user_id})
        if not session:
            raise HTTPException(status_code=403, detail="Session not found or access denied")
            
        messages = session.get("messages", [])
        if len(messages) >= 2:
            updated_messages = messages[:-2]
            await get_db()["sessions"].update_one(
                {"_id": session_id, "user_id": user_id},
                {"$set": {"messages": updated_messages, "updated_at": time.time()}}
            )
            return {"status": "success", "message": "Last Q&A turn deleted successfully"}
        elif len(messages) == 1:
            await get_db()["sessions"].update_one(
                {"_id": session_id, "user_id": user_id},
                {"$set": {"messages": [], "updated_at": time.time()}}
            )
            return {"status": "success", "message": "Last message deleted successfully"}
        
        return {"status": "success", "message": "No messages to delete"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting last Q&A for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot delete last Q&A")


# ===== HEALTH CORNER REST APIs =====

@app.get("/api/corners")
async def get_corners(current_user: dict = Depends(get_current_user)):
    """Fetch health corners for the current user"""
    try:
        user_id = current_user["user_id"]
        cursor = get_db()["health_corners"].find({"user_id": user_id}).sort("last_accessed_at", -1)
        corners = await cursor.to_list(length=100)
        return corners
    except Exception as e:
        logger.error(f"Error fetching corners: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch health corners")


@app.post("/api/corners")
async def create_new_corner(
    payload: CornerCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new health corner"""
    try:
        user_id = current_user["user_id"]
        corner_id = str(uuid.uuid4())
        corner_doc = {
            "_id": corner_id,
            "user_id": user_id,
            "name": payload.name,
            "emoji": payload.emoji,
            "created_at": time.time(),
            "last_accessed_at": time.time(),
        }
        await get_db()["health_corners"].insert_one(corner_doc)
        return corner_doc
    except Exception as e:
        logger.error(f"Error creating corner: {e}")
        raise HTTPException(status_code=500, detail="Cannot create health corner")


@app.put("/api/corners/{corner_id}")
async def update_existing_corner(
    corner_id: str,
    payload: CornerUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update corner name or emoji"""
    try:
        user_id = current_user["user_id"]
        update_data = {"last_accessed_at": time.time()}
        if payload.name is not None:
            update_data["name"] = payload.name
        if payload.emoji is not None:
            update_data["emoji"] = payload.emoji
            
        result = await get_db()["health_corners"].update_one(
            {"_id": corner_id, "user_id": user_id},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=403, detail="Corner not found or unauthorized")
        
        # Return the updated corner document
        updated = await get_db()["health_corners"].find_one({"_id": corner_id, "user_id": user_id})
        return updated if updated else {"status": "success", "message": "Corner updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating corner {corner_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot update corner")


@app.delete("/api/corners/{corner_id}")
async def delete_existing_corner(
    corner_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a corner and unlink all sessions linked to it"""
    try:
        user_id = current_user["user_id"]
        result = await get_db()["health_corners"].delete_one({"_id": corner_id, "user_id": user_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=403, detail="Corner not found or unauthorized")
            
        await get_db()["sessions"].update_many(
            {"user_id": user_id, "corner_id": corner_id},
            {"$unset": {"corner_id": ""}}
        )
        return {"status": "success", "message": "Corner deleted successfully and sessions unlinked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting corner {corner_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot delete corner")


@app.put("/api/sessions/{session_id}/corner")
async def assign_session_to_health_corner(
    session_id: str,
    payload: CornerAssign,
    current_user: dict = Depends(get_current_user)
):
    """Assign or unassign a chat session to/from a health corner"""
    try:
        user_id = current_user["user_id"]
        if payload.corner_id:
            corner = await get_db()["health_corners"].find_one({"_id": payload.corner_id, "user_id": user_id})
            if not corner:
                raise HTTPException(status_code=403, detail="Corner not found or unauthorized")
                
        if payload.corner_id:
            result = await get_db()["sessions"].update_one(
                {"_id": session_id, "user_id": user_id},
                {"$set": {"corner_id": payload.corner_id, "updated_at": time.time()}}
            )
            # Update corner access recency
            await get_db()["health_corners"].update_one(
                {"_id": payload.corner_id, "user_id": user_id},
                {"$set": {"last_accessed_at": time.time()}}
            )
        else:
            result = await get_db()["sessions"].update_one(
                {"_id": session_id, "user_id": user_id},
                {"$unset": {"corner_id": ""}, "$set": {"updated_at": time.time()}}
            )
            
        if result.matched_count == 0:
            raise HTTPException(status_code=403, detail="Session not found or unauthorized")
            
        return {"status": "success", "message": "Session corner assignment updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning session {session_id} to corner: {e}")
        raise HTTPException(status_code=500, detail="Cannot assign session to corner")


@app.get("/api/corners/{corner_id}/sessions")
async def get_corner_sessions_list(
    corner_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get sessions belonging to a specific health corner"""
    try:
        user_id = current_user["user_id"]
        corner = await get_db()["health_corners"].find_one({"_id": corner_id, "user_id": user_id})
        if not corner:
            raise HTTPException(status_code=403, detail="Corner not found or unauthorized")
            
        cursor = get_db()["sessions"].find(
            {"user_id": user_id, "corner_id": corner_id},
            {"messages": 0}
        ).sort([("is_pinned", -1), ("updated_at", -1)])
        
        sessions = await cursor.to_list(length=100)
        return sessions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching corner sessions: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch corner sessions")


@app.post("/api/feedback", status_code=202)
async def submit_user_feedback(
    payload: ChatFeedbackCreate,
    current_user: dict = Depends(get_current_user)
):
    """Submit user feedback (Like/Dislike) for an AI message"""
    try:
        db = get_db()
        user_id = current_user["user_id"]
        
        # Check if feedback already exists for this interaction_id and user
        existing = await db["chat_feedbacks"].find_one({
            "interaction_id": payload.interaction_id,
            "user_id": user_id
        })
        
        import datetime
        now = datetime.datetime.utcnow()
        
        if existing:
            # Update existing feedback
            await db["chat_feedbacks"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "rating": payload.rating,
                        "reason_tags": payload.reason_tags,
                        "text_feedback": payload.text_feedback,
                        "updated_at": now
                    }
                }
            )
            return {"status": "success", "message": "Feedback updated successfully"}
        else:
            # Create new feedback
            doc = {
                "interaction_id": payload.interaction_id,
                "session_id": payload.session_id,
                "user_id": user_id,
                "query": payload.query,
                "ai_response": payload.ai_response,
                "retrieved_sources": payload.retrieved_sources,
                "rating": payload.rating,
                "reason_tags": payload.reason_tags,
                "text_feedback": payload.text_feedback,
                "status": "pending",
                "admin_notes": "",
                "created_at": now,
                "updated_at": now
            }
            await db["chat_feedbacks"].insert_one(doc)
            return {"status": "success", "message": "Feedback submitted successfully"}
    except Exception as e:
        logger.error(f"Error submitting user feedback: {e}")
        raise HTTPException(status_code=500, detail="Cannot submit feedback")


# ===== ADMIN DASHBOARD SYSTEM STATS =====

@app.get("/api/admin/stats")
async def get_admin_dashboard_stats(current_admin: dict = Depends(get_current_admin)):
    """Get overview statistics for Admin Dashboard"""
    try:
        db = get_db()
        
        # 1. Basic counts
        total_feedbacks = await db["chat_feedbacks"].count_documents({})
        total_like = await db["chat_feedbacks"].count_documents({"rating": 1})
        total_dislike = await db["chat_feedbacks"].count_documents({"rating": -1})
        total_pending = await db["chat_feedbacks"].count_documents({"rating": -1, "status": "pending"})
        
        # CSAT = percentage of Likes out of total rated (Likes + Dislikes)
        total_rated = total_like + total_dislike
        csat = int((total_like / total_rated) * 100) if total_rated > 0 else 100
        
        # 2. Tag distribution (for dislike reason_tags)
        tag_distribution = []
        pipeline = [
            {"$match": {"rating": -1}},
            {"$unwind": "$reason_tags"},
            {"$group": {"_id": "$reason_tags", "count": {"$sum": 1}}},
            {"$project": {"tag": "$_id", "count": 1, "_id": 0}},
            {"$sort": {"count": -1}}
        ]
        cursor = db["chat_feedbacks"].aggregate(pipeline)
        tag_distribution = await cursor.to_list(length=100)
        
        # 3. Trend 7 Days
        import datetime
        trend_7days = []
        today = datetime.datetime.utcnow().date()
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            start_dt = datetime.datetime.combine(d, datetime.time.min)
            end_dt = datetime.datetime.combine(d, datetime.time.max)
            
            # Match both ISO string formats and datetime objects
            start_str = start_dt.isoformat()
            end_str = end_dt.isoformat()
            
            like_count = await db["chat_feedbacks"].count_documents({
                "rating": 1,
                "$or": [
                    {"created_at": {"$gte": start_dt, "$lte": end_dt}},
                    {"created_at": {"$gte": start_str, "$lte": end_str}}
                ]
            })
            dislike_count = await db["chat_feedbacks"].count_documents({
                "rating": -1,
                "$or": [
                    {"created_at": {"$gte": start_dt, "$lte": end_dt}},
                    {"created_at": {"$gte": start_str, "$lte": end_str}}
                ]
            })
            trend_7days.append({
                "date": d.isoformat(),
                "like": like_count,
                "dislike": dislike_count
            })
            
        # 4. Hourly Usage
        hourly_usage = []
        try:
            hourly_pipeline = [
                {"$project": {
                    "date": {
                        "$cond": {
                            "if": {"$eq": [{"$type": "$created_at"}, "string"]},
                            "then": {"$dateFromString": {"dateString": "$created_at"}},
                            "else": "$created_at"
                        }
                    }
                }},
                {"$group": {
                    "_id": {"$hour": "$date"},
                    "count": {"$sum": 1}
                }},
                {"$project": {"hour": "$_id", "count": 1, "_id": 0}},
                {"$sort": {"hour": 1}}
            ]
            hourly_cursor = db["chat_feedbacks"].aggregate(hourly_pipeline)
            hourly_results = await hourly_cursor.to_list(length=24)
            hours_map = {item["hour"]: item["count"] for item in hourly_results if item["hour"] is not None}
            for h in range(24):
                hourly_usage.append({"hour": h, "count": hours_map.get(h, 0)})
        except Exception:
            for h in range(24):
                hourly_usage.append({"hour": h, "count": 0})
                
        # Include dictionary sizes and settings in stats too
        conditions_count = await db["clinical_conditions"].count_documents({})
        medications_count = await db["medications"].count_documents({})
        ingredients_count = await db["ingredients_master"].count_documents({})
        
        qdrant_count = 0
        if qdrant_client:
            try:
                coll = qdrant_client.get_collection(settings.QDRANT_COLLECTION)
                qdrant_count = coll.points_count
            except Exception:
                pass

        return {
            "total": total_feedbacks,
            "csat": csat,
            "total_like": total_like,
            "total_dislike": total_dislike,
            "total_pending": total_pending,
            "tag_distribution": tag_distribution,
            "trend_7days": trend_7days,
            "hourly_usage": hourly_usage,
            "dictionary_sizes": {
                "conditions": conditions_count,
                "medications": medications_count,
                "ingredients": ingredients_count,
            },
            "qdrant_documents": qdrant_count,
            "rag_config": {
                "top_k": settings.TOP_K_RERANK,
                "alpha": settings.HYBRID_ALPHA,
            }
        }
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch admin stats")


# ===== ADMIN FEEDBACKS MANAGEMENT =====

@app.get("/api/admin/feedbacks")
async def get_admin_feedbacks_list(
    page: int = 1,
    limit: int = 15,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    rating: Optional[int] = None,
    date_range: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin),
):
    """Fetch user feedbacks with optional pagination and filters"""
    try:
        db = get_db()
        query = {}
        if status:
            query["status"] = status
        if tag:
            query["reason_tags"] = tag
        if rating is not None:
            query["rating"] = rating
            
        if date_range:
            import datetime
            now = datetime.datetime.utcnow()
            start_date = None
            if date_range == "today":
                start_date = datetime.datetime.combine(now.date(), datetime.time.min)
            elif date_range == "7days":
                start_date = datetime.datetime.combine(now.date() - datetime.timedelta(days=6), datetime.time.min)
            elif date_range == "this_month":
                start_date = datetime.datetime(now.year, now.month, 1)
                
            if start_date:
                query["$or"] = [
                    {"created_at": {"$gte": start_date}},
                    {"created_at": {"$gte": start_date.isoformat()}}
                ]
            
        total = await db["chat_feedbacks"].count_documents(query)
        
        # Sử dụng Aggregation để thiết lập trọng số sắp xếp động:
        # - Lỗi nghiêm trọng CHƯA XỬ LÝ (wrong_medical_info hoặc ignored_allergy) -> Trọng số 1 (Đầu danh sách)
        # - Tất cả phản hồi khác -> Trọng số 0 (Sắp xếp theo ngày giảm dần)
        pipeline = [
            {"$match": query},
            {
                "$addFields": {
                    "sort_weight": {
                        "$cond": {
                            "if": {
                                "$and": [
                                    {"$eq": ["$status", "pending"]},
                                    {
                                        "$or": [
                                            {"$in": ["wrong_medical_info", {"$ifNull": ["$reason_tags", []]}]},
                                            {"$in": ["ignored_allergy", {"$ifNull": ["$reason_tags", []]}]},
                                            {"$in": ["dangerous_advice", {"$ifNull": ["$reason_tags", []]}]},
                                            {"$in": ["hallucination", {"$ifNull": ["$reason_tags", []]}]}
                                        ]
                                    }
                                ]
                            },
                            "then": 1,
                            "else": 0
                        }
                    }
                }
            },
            {"$sort": {"sort_weight": -1, "created_at": -1}},
            {"$skip": (page - 1) * limit},
            {"$limit": limit}
        ]
        
        cursor = db["chat_feedbacks"].aggregate(pipeline)
        feedbacks = await cursor.to_list(length=limit)
        
        for fb in feedbacks:
            fb["id"] = str(fb["_id"])
            del fb["_id"]
            
        import math
        total_pages = math.ceil(total / limit) if limit > 0 else 1
        
        return {"items": feedbacks, "total": total, "total_pages": total_pages, "page": page, "limit": limit}
    except Exception as e:
        logger.error(f"Error fetching feedbacks: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch feedbacks")


@app.delete("/api/admin/feedbacks/{feedback_id}")
async def delete_user_feedback(feedback_id: str, current_admin: dict = Depends(get_current_admin)):
    """Delete a feedback by its ID"""
    try:
        from bson import ObjectId
        db = get_db()
        result = await db["chat_feedbacks"].delete_one({"_id": ObjectId(feedback_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Feedback not found")
        return {"status": "success", "message": "Feedback deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot delete feedback")


@app.patch("/api/admin/feedbacks/bulk-resolve")
async def bulk_resolve_feedbacks_api(payload: BulkResolveRequest, current_admin: dict = Depends(get_current_admin)):
    """Bulk resolve pending feedbacks with a specific tag"""
    try:
        db = get_db()
        
        # Chặn nếu Admin gửi yêu cầu đóng hàng loạt cho một trong các tag lỗi nghiêm trọng
        if payload.tag in ["wrong_medical_info", "ignored_allergy", "dangerous_advice", "hallucination"]:
            raise HTTPException(
                status_code=400, 
                detail="Không thể đóng hàng loạt lỗi an toàn lâm sàng nghiêm trọng. Yêu cầu rà soát thủ công."
            )
            
        query = {
            "status": "pending",
            "reason_tags": {
                "$nin": ["wrong_medical_info", "ignored_allergy", "dangerous_advice", "hallucination"]
            }
        }
        if payload.tag:
            query["reason_tags"] = payload.tag
            
        result = await db["chat_feedbacks"].update_many(
            query,
            {"$set": {"status": "resolved", "admin_notes": "Bulk resolved by Admin"}}
        )
        return {
            "status": "success", 
            "message": f"Successfully resolved {result.modified_count} feedbacks"
        }
    except Exception as e:
        logger.error(f"Error in bulk resolve feedbacks: {e}")
        raise HTTPException(status_code=500, detail="Cannot resolve feedbacks in bulk")


@app.patch("/api/admin/feedbacks/{feedback_id}")
async def update_feedback_status_notes(feedback_id: str, payload: AdminFeedbackUpdate, current_admin: dict = Depends(get_current_admin)):
    """Update status or admin notes on a feedback"""
    try:
        from bson import ObjectId
        db = get_db()
        update_data = {}
        if payload.status is not None:
            update_data["status"] = payload.status
        if payload.admin_notes is not None:
            update_data["admin_notes"] = payload.admin_notes
            
        if not update_data:
            return {"status": "success", "message": "No changes requested"}
            
        result = await db["chat_feedbacks"].update_one(
            {"_id": ObjectId(feedback_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Feedback not found")
            
        return {"status": "success", "message": "Feedback updated successfully"}
    except Exception as e:
        logger.error(f"Error updating feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot update feedback")


def make_vietnamese_accent_insensitive_regex(q: str) -> str:
    """
    Builds a regex pattern for accent-insensitive (diacritic-insensitive)
    Vietnamese search in MongoDB.
    """
    if not q:
        return ""
    char_map = {
        'a': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'à': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'á': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ả': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ã': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ạ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ă': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ằ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ắ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ẳ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ẵ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ặ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'â': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ầ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ấ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ẩ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ẫ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'ậ': '[aàáảãạăằắẳẵặâầấẩẫậ]',
        'e': '[eèéẻẽẹêềếểễệ]',
        'è': '[eèéẻẽẹêềếểễệ]',
        'é': '[eèéẻẽẹêềếểễệ]',
        'ẻ': '[eèéẻẽẹêềếểễệ]',
        'ẽ': '[eèéẻẽẹêềếểễệ]',
        'ẹ': '[eèéẻẽẹêềếểễệ]',
        'ê': '[eèéẻẽẹêềếểễệ]',
        'ề': '[eèéẻẽẹêềếểễệ]',
        'ế': '[eèéẻẽẹêềếểễệ]',
        'ẻ': '[eèéẻẽẹêềếểễệ]',
        'ể': '[eèéẻẽẹêềếểễệ]',
        'ễ': '[eèéẻẽẹêềếểễệ]',
        'ệ': '[eèéẻẽẹêềếểễệ]',
        'i': '[iìíỉĩị]',
        'ì': '[iìíỉĩị]',
        'í': '[iìíỉĩị]',
        'ỉ': '[iìíỉĩị]',
        'ĩ': '[iìíỉĩị]',
        'ị': '[iìíỉĩị]',
        'o': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ò': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ó': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ỏ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'õ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ọ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ô': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ồ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ố': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ổ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ỗ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ộ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ơ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ờ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ớ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ở': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ỡ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'ợ': '[oòóỏõọôồốổỗộơờớởỡợ]',
        'u': '[uùúủũụưừứửữự]',
        'ù': '[uùúủũụưừứửữự]',
        'ú': '[uùúủũụưừứửữự]',
        'ủ': '[uùúủũụưừứửữự]',
        'ũ': '[uùúủũụưừứửữự]',
        'ụ': '[uùúủũụưừứửữự]',
        'ư': '[uùúủũụưừứửữự]',
        'ừ': '[uùúủũụưừứửữự]',
        'ứ': '[uùúủũụưừứửữự]',
        'ử': '[uùúủũụưừứửữự]',
        'ữ': '[uùúủũụưừứửữự]',
        'ự': '[uùúủũụưừứửữự]',
        'y': '[yỳýỷỹỵ]',
        'ỳ': '[yỳýỷỹỵ]',
        'ý': '[yỳýỷỹỵ]',
        'ỷ': '[yỳýỷỹỵ]',
        'ỹ': '[yỳýỷỹỵ]',
        'ỵ': '[yỳýỷỹỵ]',
        'd': '[dđ]',
        'đ': '[dđ]',
    }
    
    escaped_chars = []
    for char in q:
        lower_char = char.lower()
        if lower_char in char_map:
            escaped_chars.append(char_map[lower_char])
        else:
            if char in '.^$*+?()[]{}|\\':
                escaped_chars.append('\\' + char)
            else:
                escaped_chars.append(char)
                
    return "".join(escaped_chars)


# ===== ADMIN DICTIONARY (CRUD) APIs =====

@app.get("/api/admin/dictionary/{dict_type}")
async def get_admin_dictionary_items(
    dict_type: str,
    q: Optional[str] = "",
    field: Optional[str] = "all",
    letter: Optional[str] = "",
    page: int = 1,
    limit: int = 20,
    current_admin: dict = Depends(get_current_admin),
):
    """Fetch clinical conditions, medications, or ingredients with optional filters"""
    try:
        db = get_db()
        query = {}
        
        if dict_type == "conditions":
            coll = "clinical_conditions"
            if q:
                regex_pattern = make_vietnamese_accent_insensitive_regex(q)
                if field == "label":
                    query["label"] = {"$regex": regex_pattern, "$options": "i"}
                elif field == "icd_code":
                    query["icd_code"] = {"$regex": regex_pattern, "$options": "i"}
                elif field == "category":
                    query["category"] = {"$regex": regex_pattern, "$options": "i"}
                else:
                    query["$or"] = [
                        {"label": {"$regex": regex_pattern, "$options": "i"}},
                        {"icd_code": {"$regex": regex_pattern, "$options": "i"}},
                        {"category": {"$regex": regex_pattern, "$options": "i"}},
                    ]
        elif dict_type == "medications":
            coll = "medications"
            if q:
                regex_pattern = make_vietnamese_accent_insensitive_regex(q)
                if field == "drug_name":
                    query["drug_name"] = {"$regex": regex_pattern, "$options": "i"}
                elif field == "category":
                    query["category"] = {"$regex": regex_pattern, "$options": "i"}
                elif field == "ingredients":
                    query["ingredients"] = {"$regex": regex_pattern, "$options": "i"}
                else:
                    query["$or"] = [
                        {"drug_name": {"$regex": regex_pattern, "$options": "i"}},
                        {"category": {"$regex": regex_pattern, "$options": "i"}},
                        {"ingredients": {"$regex": regex_pattern, "$options": "i"}},
                    ]
        elif dict_type == "ingredients":
            coll = "ingredients_master"
            if q:
                regex_pattern = make_vietnamese_accent_insensitive_regex(q)
                query["name"] = {"$regex": regex_pattern, "$options": "i"}
            if letter:
                query["first_letter"] = letter.upper()
        else:
            raise HTTPException(status_code=400, detail="Invalid dictionary type")
            
        total = await db[coll].count_documents(query)
        cursor = db[coll].find(query).skip((page - 1) * limit).limit(limit)
        items = await cursor.to_list(length=limit)
        
        for item in items:
            if "_id" in item:
                item["id"] = str(item["_id"])
                del item["_id"]
                
        return {"items": items, "total": total, "page": page, "limit": limit}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching dictionary {dict_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Cannot fetch dictionary {dict_type}")


@app.post("/api/admin/dictionary/{dict_type}")
async def create_admin_dictionary_item(dict_type: str, payload: dict, current_admin: dict = Depends(get_current_admin)):
    """Add a new item to clinical conditions, medications, or ingredients"""
    try:
        db = get_db()
        if dict_type == "conditions":
            coll = "clinical_conditions"
            if "icd_code" not in payload or "label" not in payload:
                raise HTTPException(status_code=400, detail="Missing required fields icd_code/label")
            payload["_id"] = payload["icd_code"].strip()
            if "search_key" not in payload:
                payload["search_key"] = unidecode(payload["label"]).lower()
        elif dict_type == "medications":
            coll = "medications"
            if "drug_name" not in payload:
                raise HTTPException(status_code=400, detail="Missing required drug_name")
            if "search_key" not in payload:
                payload["search_key"] = unidecode(payload["drug_name"]).lower()
            if "ingredients" in payload:
                if isinstance(payload["ingredients"], str):
                    payload["ingredients"] = [i.strip() for i in payload["ingredients"].split(",") if i.strip()]
                elif not isinstance(payload["ingredients"], list):
                    payload["ingredients"] = []
        elif dict_type == "ingredients":
            coll = "ingredients_master"
            if "name" not in payload:
                raise HTTPException(status_code=400, detail="Missing required name")
            payload["first_letter"] = unidecode(payload["name"][0]).upper() if payload["name"] else "A"
        else:
            raise HTTPException(status_code=400, detail="Invalid dictionary type")
            
        result = await db[coll].insert_one(payload)
        payload["id"] = str(result.inserted_id)
        if "_id" in payload:
            del payload["_id"]
            
        await load_data_to_ram(db)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating dictionary item in {dict_type}: {e}")
        raise HTTPException(status_code=500, detail="Cannot create dictionary item")


@app.put("/api/admin/dictionary/{dict_type}/{item_id}")
async def update_admin_dictionary_item(dict_type: str, item_id: str, payload: dict, current_admin: dict = Depends(get_current_admin)):
    """Update a dictionary item by ID"""
    try:
        from bson import ObjectId
        db = get_db()
        if dict_type == "conditions":
            coll = "clinical_conditions"
        elif dict_type == "medications":
            coll = "medications"
        elif dict_type == "ingredients":
            coll = "ingredients_master"
        else:
            raise HTTPException(status_code=400, detail="Invalid dictionary type")
            
        if "id" in payload:
            del payload["id"]
        if "_id" in payload:
            del payload["_id"]
            
        if dict_type == "conditions":
            if "label" in payload:
                payload["search_key"] = unidecode(payload["label"]).lower()
            try:
                query_id = ObjectId(item_id)
            except Exception:
                query_id = item_id
        elif dict_type == "medications":
            if "drug_name" in payload:
                payload["search_key"] = unidecode(payload["drug_name"]).lower()
            if "ingredients" in payload:
                if isinstance(payload["ingredients"], str):
                    payload["ingredients"] = [i.strip() for i in payload["ingredients"].split(",") if i.strip()]
                elif not isinstance(payload["ingredients"], list):
                    payload["ingredients"] = []
            query_id = ObjectId(item_id)
        elif dict_type == "ingredients":
            if "name" in payload:
                payload["first_letter"] = unidecode(payload["name"][0]).upper() if payload["name"] else "A"
            query_id = ObjectId(item_id)
        else:
            query_id = ObjectId(item_id)

        result = await db[coll].update_one(
            {"_id": query_id},
            {"$set": payload}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Item not found")
            
        await load_data_to_ram(db)
        return {"status": "success", "message": "Dictionary item updated successfully"}
    except Exception as e:
        logger.error(f"Error updating dictionary item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot update dictionary item")


@app.delete("/api/admin/dictionary/{dict_type}/{item_id}")
async def delete_admin_dictionary_item(dict_type: str, item_id: str, current_admin: dict = Depends(get_current_admin)):
    """Delete a dictionary item by ID"""
    try:
        from bson import ObjectId
        db = get_db()
        if dict_type == "conditions":
            coll = "clinical_conditions"
        elif dict_type == "medications":
            coll = "medications"
        elif dict_type == "ingredients":
            coll = "ingredients_master"
        else:
            raise HTTPException(status_code=400, detail="Invalid dictionary type")
            
        if dict_type == "conditions":
            try:
                query_id = ObjectId(item_id)
            except Exception:
                query_id = item_id
        else:
            query_id = ObjectId(item_id)

        result = await db[coll].delete_one({"_id": query_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Item not found")
            
        await load_data_to_ram(db)
        return {"status": "success", "message": "Dictionary item deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting dictionary item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot delete dictionary item")


# ===== ADMIN SYSTEM SETTINGS =====

@app.get("/api/admin/system-settings", response_model=SystemSettings)
async def get_admin_system_settings(current_admin: dict = Depends(get_current_admin)):
    """Fetch current system configurations from MongoDB"""
    try:
        db = get_db()
        settings_doc = await db["system_settings"].find_one({})
        if not settings_doc:
            settings_doc = SystemSettings().model_dump()
            
        # Nạp dữ liệu system_info động đồng bộ với Frontend React
        from services.suggestion_service import _conditions_cache, _ingredients_cache, _medications_cache
        settings_doc["system_info"] = {
            "clinical_rag_model": settings.GROQ_MODEL,
            "triage_safety_model": settings.GROQ_MODEL,
            "temperature": 0.3,
            "embedding_model": settings.EMBEDDING_MODEL,
            "reranker_model": settings.RERANKER_MODEL,
            "suggestion_cache": {
                "conditions_count": len(_conditions_cache),
                "medications_count": len(_medications_cache),
                "ingredients_count": len(_ingredients_cache),
            }
        }
        
        if "_id" in settings_doc:
            del settings_doc["_id"]
        return settings_doc
    except Exception as e:
        logger.error(f"Error fetching system settings: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch system settings")


@app.put("/api/admin/system-settings", response_model=SystemSettings)
async def update_admin_system_settings(payload: SystemSettings, current_admin: dict = Depends(get_current_admin)):
    """Update system configurations in MongoDB"""
    try:
        db = get_db()
        settings_dict = payload.model_dump()
        # Loại bỏ system_info khi lưu xuống database vì đó là tham số chỉ đọc/tĩnh
        if "system_info" in settings_dict:
            del settings_dict["system_info"]
        await db["system_settings"].update_one(
            {},
            {"$set": settings_dict},
            upsert=True
        )
        return payload
    except Exception as e:
        logger.error(f"Error updating system settings: {e}")
        raise HTTPException(status_code=500, detail="Cannot update system settings")


# ===== ADMIN UNSAFE QUERY LOGS & STATS =====

@app.get("/api/admin/unsafe-logs", response_model=UnsafeLogsResponse)
async def get_admin_unsafe_logs_list(
    page: int = 1,
    limit: int = 20,
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin),
):
    """Fetch locked unsafe queries logs with filtering and pagination"""
    try:
        db = get_db()
        query = {}
        if category:
            query["category"] = category
        if search:
            query["query"] = {"$regex": search, "$options": "i"}
            
        total = await db["unsafe_logs"].count_documents(query)
        cursor = db["unsafe_logs"].find(query).sort("timestamp", -1).skip((page - 1) * limit).limit(limit)
        logs = await cursor.to_list(length=limit)
        
        unsafe_logs = []
        for l in logs:
            unsafe_logs.append(
                UnsafeQueryLog(
                    id=str(l["_id"]),
                    query=l.get("query", ""),
                    category=l.get("category", ""),
                    reason=l.get("reason", ""),
                    session_id=l.get("session_id"),
                    timestamp=l.get("timestamp"),
                    user_id=l.get("user_id"),
                )
            )
            
        return UnsafeLogsResponse(total=total, page=page, limit=limit, logs=unsafe_logs)
    except Exception as e:
        logger.error(f"Error fetching unsafe logs: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch unsafe logs")


@app.delete("/api/admin/unsafe-logs/clear")
async def clear_all_unsafe_logs(current_admin: dict = Depends(get_current_admin)):
    """Clear all unsafe query logs from database"""
    try:
        db = get_db()
        await db["unsafe_logs"].delete_many({})
        return {"status": "success", "message": "All unsafe logs cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing unsafe logs: {e}")
        raise HTTPException(status_code=500, detail="Cannot clear unsafe logs")


@app.delete("/api/admin/unsafe-logs/{log_id}")
async def delete_admin_unsafe_log(log_id: str, current_admin: dict = Depends(get_current_admin)):
    """Delete a specific unsafe query log from database"""
    try:
        from bson import ObjectId
        db = get_db()
        result = await db["unsafe_logs"].delete_one({"_id": ObjectId(log_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Log not found")
        return {"status": "success", "message": "Unsafe log deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting unsafe log {log_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot delete unsafe log")


@app.get("/api/admin/unsafe-stats", response_model=UnsafeStatsResponse)
async def get_admin_unsafe_logs_stats(current_admin: dict = Depends(get_current_admin)):
    """Get aggregated statistics about unsafe query attempts"""
    try:
        db = get_db()
        total = await db["unsafe_logs"].count_documents({})
        
        categories = ["SELF_HARM", "ILLEGAL_DRUGS", "ILLEGAL_PRACTICE", "HATE_SPEECH", "OTHER"]
        by_category = {}
        for cat in categories:
            by_category[cat] = await db["unsafe_logs"].count_documents({"category": cat})
            
        # Xu hướng 7 ngày gần đây cho unsafe logs
        import datetime
        recent_trend = []
        today = datetime.datetime.utcnow().date()
        for i in range(6, -1, -1):
            d = today - datetime.timedelta(days=i)
            start_dt = datetime.datetime.combine(d, datetime.time.min)
            end_dt = datetime.datetime.combine(d, datetime.time.max)
            
            start_str = start_dt.isoformat()
            end_str = end_dt.isoformat()
            
            count = await db["unsafe_logs"].count_documents({
                "$or": [
                    {"timestamp": {"$gte": start_str, "$lte": end_str}},
                    {"timestamp": {"$gte": start_dt, "$lte": end_dt}}
                ]
            })
            recent_trend.append({
                "date": d.isoformat(),
                "count": count
            })
            
        return UnsafeStatsResponse(total_unsafe=total, by_category=by_category, recent_trend=recent_trend)
    except Exception as e:
        logger.error(f"Error fetching unsafe stats: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch unsafe stats")


@app.get("/api/admin/unsafe-users")
async def get_admin_unsafe_users_list(current_admin: dict = Depends(get_current_admin)):
    """Get users with unsafe query violations and all currently banned users, enriched with user details"""
    try:
        db = get_db()
        pipeline = [
            {
                "$group": {
                    "_id": "$user_id",
                    "count": {"$sum": 1},
                    "categories": {"$addToSet": "$category"},
                    "last_violation": {"$max": "$timestamp"}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        cursor = db["unsafe_logs"].aggregate(pipeline)
        unsafe_aggregated = await cursor.to_list(length=20)
        
        users_dict = {}
        for u in unsafe_aggregated:
            user_id = u["_id"]
            if not user_id:
                continue
                
            user_doc = await db["users"].find_one({"_id": user_id})
            email = "N/A"
            is_banned = False
            if user_doc:
                email = user_doc.get("email", user_doc.get("primary_email", "N/A"))
                is_banned = user_doc.get("is_banned", False)
                
            users_dict[user_id] = {
                "user_id": user_id,
                "email": email,
                "count": u["count"],
                "categories": list(u["categories"]),
                "is_banned": is_banned,
                "last_violation": u["last_violation"]
            }
            
        # Gộp thêm các user đang bị cấm (is_banned = True) nhưng không có log vi phạm hiện tại
        banned_cursor = db["users"].find({"is_banned": True})
        banned_users = await banned_cursor.to_list(length=None)
        
        for bu in banned_users:
            bu_id = bu["_id"]
            email = bu.get("email", bu.get("primary_email", "N/A"))
            
            if bu_id not in users_dict:
                users_dict[bu_id] = {
                    "user_id": bu_id,
                    "email": email,
                    "count": 0,
                    "categories": [],
                    "is_banned": True,
                    "last_violation": None
                }
            else:
                users_dict[bu_id]["is_banned"] = True
                
        sorted_users = sorted(
            users_dict.values(),
            key=lambda x: (x["is_banned"], x["count"]),
            reverse=True
        )
        
        return {"users": sorted_users}
    except Exception as e:
        logger.error(f"Error fetching unsafe users: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch unsafe users")


@app.post("/api/admin/users/{user_id}/ban")
async def toggle_ban_user_api(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """Ban or unban a user from using the AI Assistant"""
    try:
        db = get_db()
        user = await db["users"].find_one({"_id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        is_banned = user.get("is_banned", False)
        new_ban_status = not is_banned
        
        await db["users"].update_one(
            {"_id": user_id},
            {"$set": {"is_banned": new_ban_status, "updated_at": time.time()}}
        )
        return {
            "status": "success", 
            "message": f"User successfully {'banned' if new_ban_status else 'unbanned'}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling ban for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot toggle ban status")


# ===== CHAT HISTORY REST API =====

@app.get("/api/sessions")
async def get_sessions(current_user: dict = Depends(get_current_user)):
    """Lấy danh sách các session cho Sidebar (của riêng user đang đăng nhập)"""
    try:
        user_id = current_user["user_id"]
        # Sort by is_pinned descending first, then updated_at descending
        cursor = get_db()["sessions"].find({"user_id": user_id}, {"messages": 0}).sort([("is_pinned", -1), ("updated_at", -1)]).limit(50)
        sessions = await cursor.to_list(length=50)
        
        # Sort in memory as a safeguard against any BSON type sorting quirks (unpinned False vs never-pinned None)
        sessions.sort(key=lambda s: (s.get("is_pinned") is True, s.get("updated_at") or 0), reverse=True)
        return sessions
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch sessions")


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Load lại toàn bộ tin nhắn của một session từ trong mảng con (check quyền sở hữu)"""
    try:
        user_id = current_user["user_id"]
        session = await get_db()["sessions"].find_one({"_id": session_id, "user_id": user_id})
        if session and "messages" in session:
            # Gắn lại session_id cho client parse API logic
            messages = session["messages"]
            for msg in messages:
                msg["session_id"] = session_id
            return messages
        
        # Nếu session không tồn tại hoặc không thuộc về user này
        raise HTTPException(status_code=403, detail="Session not found or access denied")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching messages for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot fetch messages")


from pydantic import BaseModel

class RenamePayload(BaseModel):
    title: str

class PinPayload(BaseModel):
    is_pinned: bool

@app.put("/api/sessions/{session_id}/rename")
async def rename_session(
    session_id: str,
    payload: RenamePayload,
    current_user: dict = Depends(get_current_user)
):
    """Rename a specific session"""
    try:
        user_id = current_user["user_id"]
        result = await get_db()["sessions"].update_one(
            {"_id": session_id, "user_id": user_id},
            {"$set": {"title": payload.title, "updated_at": time.time()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=403, detail="Session not found or unauthorized")
            
        return {"status": "success", "message": "Session renamed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error renaming session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot rename session")

@app.put("/api/sessions/{session_id}/pin")
async def pin_session(
    session_id: str,
    payload: PinPayload,
    current_user: dict = Depends(get_current_user)
):
    """Pin or unpin a specific session"""
    try:
        user_id = current_user["user_id"]
        result = await get_db()["sessions"].update_one(
            {"_id": session_id, "user_id": user_id},
            {"$set": {"is_pinned": payload.is_pinned, "updated_at": time.time()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=403, detail="Session not found or unauthorized")
            
        return {"status": "success", "message": f"Session {'pinned' if payload.is_pinned else 'unpinned'} successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pinning session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot pin session")

@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Xóa vĩnh viễn một phiên làm việc (chỉ xóa đc của mình)"""
    try:
        user_id = current_user["user_id"]
        result = await get_db()["sessions"].delete_one({"_id": session_id, "user_id": user_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=403, detail="Cannot delete session: Not found or unauthorized")
            
        # Cascade delete feedbacks and unsafe logs associated with this session
        await get_db()["chat_feedbacks"].delete_many({"session_id": session_id, "user_id": user_id})
        await get_db()["unsafe_logs"].delete_many({"session_id": session_id, "user_id": user_id})
            
        return {"status": "success", "message": f"Session {session_id} deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot delete session")


def verify_clerk_signature(payload_bytes: bytes, svix_id: str, svix_timestamp: str, svix_signature: str) -> bool:
    """
    Verify Clerk webhook signature using HMAC-SHA256.
    Ref: https://clerk.com/docs/webhooks/overview#verify-webhook-signatures
    """
    if not settings.CLERK_WEBHOOK_SECRET:
        logger.error("CLERK_WEBHOOK_SECRET is not configured!")
        return False

    # Extract signing secret prefix if Clerk format is "whsec_..."
    secret = settings.CLERK_WEBHOOK_SECRET
    if secret.startswith("whsec_"):
        secret = secret[6:]

    try:
        # Decode the base64 signing secret
        secret_bytes = base64.b64decode(secret)

        # Re-create signing payload: svix_id + "." + svix_timestamp + "." + raw_payload_bytes
        signing_payload = f"{svix_id}.{svix_timestamp}.".encode("utf-8") + payload_bytes
        
        # Verify signature matching
        mac = hmac.new(
            key=secret_bytes,
            msg=signing_payload,
            digestmod=hashlib.sha256
        )
        
        # The expected signature is Base64 encoded
        expected_sig_b64 = base64.b64encode(mac.digest()).decode("utf-8")
        
        passed = False
        for sig_token in svix_signature.split():
            if sig_token.startswith("v1,"):
                sig = sig_token[3:]
                # Timing-safe comparison to prevent side-channel timing attacks
                if hmac.compare_digest(sig.encode("utf-8"), expected_sig_b64.encode("utf-8")):
                    passed = True
                    break
        return passed
    except Exception as e:
        logger.error(f"Error verifying Clerk signature: {e}")
        return False


from fastapi import Request

@app.post("/api/webhooks/clerk")
async def clerk_webhook(request: Request):
    """
    Clerk webhook receiver to synchronize user profiles and trigger cascade deletion.
    Supports user.deleted and user.updated events.
    """
    svix_id = request.headers.get("svix-id")
    svix_timestamp = request.headers.get("svix-timestamp")
    svix_signature = request.headers.get("svix-signature")

    if not svix_id or not svix_timestamp or not svix_signature:
        logger.warning("Clerk Webhook: Missing required svix headers.")
        raise HTTPException(status_code=400, detail="Missing required signature headers.")

    # Read raw body bytes
    body_bytes = await request.body()

    # Verify signature
    if not verify_clerk_signature(body_bytes, svix_id, svix_timestamp, svix_signature):
        logger.warning("Clerk Webhook: Signature verification failed.")
        raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    event_type = payload.get("type")
    data = payload.get("data", {})
    user_id = data.get("id")

    if not user_id:
        logger.warning("Clerk Webhook: Payload missing user id.")
        return {"status": "success", "message": "No user ID to process."}

    db = get_db()

    # 1. USER DELETED EVENT
    if event_type == "user.deleted":
        logger.info(f"🗑️ Clerk Webhook: Cascade deleting data for user {user_id}...")
        try:
            # Delete across 5 collections
            r1 = await db["users"].delete_one({"_id": user_id})
            r2 = await db["sessions"].delete_many({"user_id": user_id})
            r3 = await db["health_corners"].delete_many({"user_id": user_id})
            r4 = await db["chat_feedbacks"].delete_many({"user_id": user_id})
            r5 = await db["unsafe_logs"].delete_many({"user_id": user_id})
            
            logger.info(
                f"  ✅ Cascade delete completed for user {user_id}: "
                f"Profile={r1.deleted_count}, Sessions={r2.deleted_count}, "
                f"Corners={r3.deleted_count}, Feedbacks={r4.deleted_count}, "
                f"UnsafeLogs={r5.deleted_count}"
            )
            return {
                "status": "success", 
                "message": "Cascade delete completed.",
                "deleted_counts": {
                    "profile": r1.deleted_count,
                    "sessions": r2.deleted_count,
                    "corners": r3.deleted_count,
                    "feedbacks": r4.deleted_count,
                    "unsafe_logs": r5.deleted_count
                }
            }
        except Exception as delete_err:
            logger.error(f"  ❌ Error during cascade delete for user {user_id}: {delete_err}")
            raise HTTPException(status_code=500, detail="Database deletion error.")

    # 2. USER UPDATED EVENT
    elif event_type == "user.updated":
        logger.info(f"🔄 Clerk Webhook: Synchronizing profile metadata for user {user_id}...")
        try:
            # Extract first_name and email
            email_addresses = data.get("email_addresses", [])
            primary_email_id = data.get("primary_email_address_id")
            
            email = ""
            if email_addresses:
                # Find primary email, otherwise fallback to first email
                primary_email_obj = next((e for e in email_addresses if e.get("id") == primary_email_id), None)
                email = primary_email_obj.get("email_address", "") if primary_email_obj else email_addresses[0].get("email_address", "")

            first_name = data.get("first_name") or ""
            
            # Check if user exists in database, if so, update their metadata
            existing = await db["users"].find_one({"_id": user_id})
            if existing:
                update_fields = {}
                if email and email != existing.get("email"):
                    update_fields["email"] = email
                if first_name and first_name != existing.get("first_name"):
                    update_fields["first_name"] = first_name
                
                if update_fields:
                    update_fields["updated_at"] = time.time()
                    await db["users"].update_one({"_id": user_id}, {"$set": update_fields})
                    logger.info(f"  ✅ Profile updated for user {user_id}: {update_fields}")
                    return {"status": "success", "message": "Profile updated."}
                else:
                    return {"status": "success", "message": "Profile metadata already synchronized."}
            else:
                return {"status": "success", "message": "User not registered in database yet."}
        except Exception as sync_err:
            logger.error(f"  ❌ Error during profile metadata synchronization for user {user_id}: {sync_err}")
            raise HTTPException(status_code=500, detail="Database update error.")

    # 3. OTHER EVENTS
    else:
        logger.info(f"ℹ️ Clerk Webhook: Unhandled event type {event_type} ignored.")
        return {"status": "success", "message": f"Event type {event_type} ignored."}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
