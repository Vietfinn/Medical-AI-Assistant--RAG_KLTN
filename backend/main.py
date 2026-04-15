import logging
import time
import uuid
import datetime
from contextlib import asynccontextmanager
from typing import Optional

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
)
from services import EmbeddingService, HybridRetriever, Reranker, GeminiService, GroqService
from services.email_service import configure_gmail, send_welcome_email
from agents import TriageAgent, ClinicalRAGAgent, SafetyGuardAgent
from auth import get_current_user

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global service instances
embedding_service: Optional[EmbeddingService] = None
retriever: Optional[HybridRetriever] = None
reranker: Optional[Reranker] = None
gemini_service: Optional[GeminiService] = None
groq_service: Optional[GroqService] = None
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

    global embedding_service, retriever, reranker, gemini_service, groq_service
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
        await MongoDB.connect(url=settings.MONGODB_URL, db_name="medical_ai")

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

        # ===== Initialize Gemini Service (Clinical RAG Agent) =====
        logger.info("Configuring Gemini API...")
        gemini_service = GeminiService(
            api_key=settings.GEMINI_API_KEY, model_name=settings.GEMINI_MODEL
        )
        gemini_service.configure()

        # ===== Initialize Groq Service (Triage + Safety Agents) =====
        logger.info("Configuring Groq API (Llama 3)...")
        groq_service = GroqService(
            api_key=settings.GROQ_API_KEY, model_name=settings.GROQ_MODEL
        )
        groq_service.configure()

        # ===== Initialize Agents =====
        logger.info("Initializing Multi-Agent system...")

        triage_agent = TriageAgent(groq_service=groq_service)
        logger.info("  ✅ Triage Agent (Llama 3 / Groq) initialized")

        clinical_rag_agent = ClinicalRAGAgent(gemini_service=gemini_service)
        logger.info("  ✅ Clinical RAG Agent (Gemini 2.5 Flash) initialized")

        safety_guard_agent = SafetyGuardAgent(groq_service=groq_service)
        logger.info("  ✅ Safety Guard Agent (Llama 3 / Groq) initialized")

        logger.info("=" * 60)
        logger.info("✅ All services and agents initialized successfully!")
        logger.info(f"🗄️  Qdrant Mode: {settings.QDRANT_MODE.upper()}")
        if settings.QDRANT_MODE == "cloud":
            logger.info(f"☁️  Cloud URL: {settings.QDRANT_CLOUD_URL[:50]}...")
        else:
            logger.info(f"🏠 Local: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        logger.info(f"🤖 Triage/Safety Agent: {settings.GROQ_MODEL}")
        logger.info(f"🧠 Clinical RAG Agent: {settings.GEMINI_MODEL}")
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
            "clinical_rag": settings.GEMINI_MODEL,
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
        gemini_configured=gemini_service is not None and gemini_service.is_configured(),
        groq_configured=groq_service is not None and groq_service.is_configured(),
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
    start_time = time.time()
    pipeline_meta = {}

    try:
        session_id = query.session_id
        is_new_session = False
        chat_history = []
        
        # Bước 1 & Bước 2: Tiếp nhận & Nạp Trí nhớ ngắn hạn
        if not session_id:
            session_id = str(uuid.uuid4())
            is_new_session = True
                
            await get_db()["sessions"].insert_one({
                "_id": session_id,
                "user_id": current_user["user_id"],
                "title": "Đoạn chat mới",
                "created_at": time.time(),
                "updated_at": time.time(),
                "messages": []
            })
            logger.info(f"Created new chat session: {session_id} for user: {current_user['user_id']}")
        else:
            # Check ownership and fetch messages
            session_doc = await get_db()["sessions"].find_one(
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

        logger.info(f"Processing query: {query.query[:100]}... (Context length: {len(chat_history)} msgs)")

        # ============================================================
        # GIAI ĐOẠN 1: Triage Agent (Llama 3 / Groq) - Intent Classification
        # ============================================================
        logger.info("━━━ Giai đoạn 1: Triage Agent ━━━")

        if settings.ENABLE_TRIAGE_AGENT:
            triage_result = triage_agent.execute(query=query.query)
            pipeline_meta["triage_time"] = triage_result.latency

            if is_new_session and triage_result.suggested_title:
                await get_db()["sessions"].update_one(
                    {"_id": session_id},
                    {"$set": {"title": triage_result.suggested_title}}
                )

            if not triage_result.is_medical:
                processing_time = time.time() - start_time
                logger.info("Query classified as NON_MEDICAL → Early Exit")
                return ChatResponse(
                    answer=triage_result.response,
                    citations=[],
                    warnings=[],
                    retrieved_docs=[],
                    processing_time=processing_time,
                    pipeline_metadata=PipelineMetadata(
                        triage_time=triage_result.latency,
                        triage_agent=settings.GROQ_MODEL,
                        generation_agent=settings.GEMINI_MODEL,
                        safety_agent=settings.GROQ_MODEL,
                    ),
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
            query=query.query, documents=retrieved_docs, top_k=settings.TOP_K_RERANK
        )
        pipeline_meta["rerank_time"] = time.time() - rerank_start
        logger.info(f"Reranked to top {len(reranked_docs)} documents")

        # ============================================================
        # GIAI ĐOẠN 3: Clinical RAG Agent (Gemini 2.5 Flash) - Generation
        # ============================================================
        logger.info("━━━ Giai đoạn 3: Clinical RAG Agent ━━━")

        # Load HealthProfile from user account (MongoDB) instead of request body
        health_profile_dict = current_user.get("health_profile")

        generation_result = clinical_rag_agent.execute(
            query=query.query,
            documents=reranked_docs,
            health_profile=health_profile_dict,
            chat_history=chat_history,
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
            generation_agent=settings.GEMINI_MODEL,
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

        return response_obj

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream(
    query: ChatQuery,
    current_user: dict = Depends(get_current_user),
):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    Streams Gemini generation token-by-token for real-time UX.
    """
    import json as _json
    from fastapi.responses import StreamingResponse

    def sse_event(event: str, data) -> str:
        """Format a single SSE event line"""
        return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream_generator():
        start_time = time.time()
        pipeline_meta = {}
        full_response_text = ""

        try:
            # ===== SESSION MANAGEMENT =====
            session_id = query.session_id
            is_new_session = False
            chat_history = []

            if not session_id:
                session_id = str(uuid.uuid4())
                is_new_session = True

                await get_db()["sessions"].insert_one({
                    "_id": session_id,
                    "user_id": current_user["user_id"],
                    "title": "Đoạn chat mới",
                    "created_at": time.time(),
                    "updated_at": time.time(),
                    "messages": []
                })
                logger.info(f"[Stream] Created new session: {session_id}")
            else:
                session_doc = await get_db()["sessions"].find_one(
                    {"_id": session_id, "user_id": current_user["user_id"]},
                    {"messages": {"$slice": -6}}
                )
                if session_doc and "messages" in session_doc:
                    for msg in session_doc["messages"]:
                        chat_history.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

            # ===== GIAI ĐOẠN 1: TRIAGE AGENT =====
            yield sse_event("status", {"message": "🧠 Đang phân tích câu hỏi..."})

            if settings.ENABLE_TRIAGE_AGENT:
                triage_result = triage_agent.execute(query=query.query)
                pipeline_meta["triage_time"] = triage_result.latency

                if is_new_session and triage_result.suggested_title:
                    await get_db()["sessions"].update_one(
                        {"_id": session_id},
                        {"$set": {"title": triage_result.suggested_title}}
                    )

                if not triage_result.is_medical:
                    processing_time = time.time() - start_time
                    logger.info("[Stream] NON_MEDICAL → Early Exit")
                    yield sse_event("token", {"content": triage_result.response})
                    yield sse_event("done", {
                        "citations": [],
                        "warnings": [],
                        "session_id": session_id,
                        "processing_time": round(processing_time, 2),
                    })

                    created_at = time.time()
                    await get_db()["sessions"].update_one(
                        {"_id": session_id, "user_id": current_user["user_id"]},
                        {
                            "$push": {
                                "messages": {
                                    "$each": [
                                        {"id": str(uuid.uuid4()), "role": "user", "content": query.query, "created_at": created_at - 0.001},
                                        {"id": str(uuid.uuid4()), "role": "assistant", "content": triage_result.response, "citations": [], "warnings": [], "created_at": created_at},
                                    ]
                                }
                            },
                            "$set": {"updated_at": created_at}
                        }
                    )
                    return
            else:
                pipeline_meta["triage_time"] = 0.0

            # ===== GIAI ĐOẠN 2: HYBRID RETRIEVAL & RERANKING =====
            yield sse_event("status", {"message": "🔍 Đang tìm kiếm tài liệu y khoa..."})

            retrieval_start = time.time()
            retrieved_docs = retriever.hybrid_search(
                query=query.query, top_k=settings.TOP_K_RETRIEVAL
            )
            pipeline_meta["retrieval_time"] = time.time() - retrieval_start

            yield sse_event("status", {"message": "📊 Đang sắp xếp kết quả..."})

            rerank_start = time.time()
            reranked_docs = reranker.rerank(
                query=query.query, documents=retrieved_docs, top_k=settings.TOP_K_RERANK
            )
            pipeline_meta["rerank_time"] = time.time() - rerank_start

            # ===== GIAI ĐOẠN 3: CLINICAL RAG AGENT (STREAMING) =====
            yield sse_event("status", {"message": "✍️ Đang soạn câu trả lời..."})

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
                yield sse_event("status", {"message": "🛡️ Đang kiểm tra an toàn..."})

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

            yield sse_event("done", {
                "citations": citations,
                "warnings": [w.model_dump() for w in warnings] if warnings else [],
                "session_id": session_id,
                "processing_time": round(processing_time, 2),
            })

            # ===== SAVE TO MONGODB =====
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
                "content": final_response,
                "citations": citations,
                "warnings": [w.model_dump() for w in warnings] if warnings else [],
                "created_at": created_at
            }
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
    """Save user health profile to MongoDB (linked to authenticated user)"""
    user_id = current_user["user_id"]
    logger.info(f"Profile save request from user: {user_id}")

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
                "clinical_rag_agent": settings.GEMINI_MODEL,
                "safety_guard_agent": settings.GROQ_MODEL,
            },
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== CHAT HISTORY REST API =====

@app.get("/api/sessions")
async def get_sessions(current_user: dict = Depends(get_current_user)):
    """Lấy danh sách các session cho Sidebar (của riêng user đang đăng nhập)"""
    try:
        user_id = current_user["user_id"]
        # Sort by is_pinned descending first, then updated_at descending
        cursor = get_db()["sessions"].find({"user_id": user_id}, {"messages": 0}).sort([("is_pinned", -1), ("updated_at", -1)]).limit(50)
        sessions = await cursor.to_list(length=50)
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
            
        return {"status": "success", "message": f"Session {session_id} deleted."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Cannot delete session")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
