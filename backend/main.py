import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

from config import settings
from models import (
    ChatQuery,
    ChatResponse,
    HealthStatus,
    Citation,
    Warning,
    RetrievedDocument,
)
from services import EmbeddingService, HybridRetriever, Reranker, GeminiService
from utils import SafetyChecker

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
safety_checker: Optional[SafetyChecker] = None
qdrant_client: Optional[QdrantClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting Medical AI Assistant API...")

    global embedding_service, retriever, reranker, gemini_service, safety_checker, qdrant_client

    try:
        # Initialize Qdrant client (Cloud hoặc Local)
        logger.info(f"Connecting to Qdrant in {settings.QDRANT_MODE} mode...")

        qdrant_params = settings.get_qdrant_client_params()
        logger.info(f"Qdrant connection params: {list(qdrant_params.keys())}")

        qdrant_client = QdrantClient(**qdrant_params)

        # Test connection
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

        # Initialize embedding service
        logger.info("Loading embedding model...")
        embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
        embedding_service.load_model()

        # Initialize retriever
        logger.info("Initializing retriever...")
        retriever = HybridRetriever(
            qdrant_client=qdrant_client,
            collection_name=settings.QDRANT_COLLECTION,
            embedding_service=embedding_service,
            alpha=settings.HYBRID_ALPHA,
        )

        # Initialize reranker
        logger.info("Loading reranker model...")
        reranker = Reranker(model_name=settings.RERANKER_MODEL)
        reranker.load_model()

        # Initialize Gemini service
        logger.info("Configuring Gemini API...")
        gemini_service = GeminiService(
            api_key=settings.GEMINI_API_KEY, model_name=settings.GEMINI_MODEL
        )
        gemini_service.configure()

        # Initialize safety checker
        safety_checker = SafetyChecker()

        logger.info("=" * 60)
        logger.info("✅ All services initialized successfully!")
        logger.info(f"🗄️  Qdrant Mode: {settings.QDRANT_MODE.upper()}")
        if settings.QDRANT_MODE == "cloud":
            logger.info(f"☁️  Cloud URL: {settings.QDRANT_CLOUD_URL[:50]}...")
        else:
            logger.info(f"🏠 Local: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        logger.info("⚕️  Medical AI Assistant API is ready!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Medical AI Assistant API...")
    if qdrant_client:
        qdrant_client.close()


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
        "message": "Medical AI Assistant API",
        "version": settings.APP_VERSION,
        "status": "running",
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
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(query: ChatQuery):
    """
    Main chat endpoint for medical Q&A

    Process flow:
    1. Hybrid search (Vector + BM25)
    2. Reranking
    3. Context assembly
    4. Safety check
    5. LLM generation
    """
    start_time = time.time()

    try:
        logger.info(f"Processing query: {query.query[:100]}...")

        # Step 0: Medical relevance gate (fast path)
        logger.info("Running medical relevance gate...")
        is_medical, gate_response = gemini_service.gate_query(query.query)
        if not is_medical:
            processing_time = time.time() - start_time
            logger.info("Query not medical. Returning gate response.")
            return ChatResponse(
                answer=gate_response,
                citations=[],
                warnings=[],
                retrieved_docs=[],
                processing_time=processing_time,
            )

        # Step 1: Hybrid Search
        logger.info("Performing hybrid search...")
        retrieved_docs = retriever.hybrid_search(
            query=query.query, top_k=settings.TOP_K_RETRIEVAL
        )
        logger.info(f"Retrieved {len(retrieved_docs)} documents")

        # Step 2: Reranking
        logger.info("Reranking documents...")
        reranked_docs = reranker.rerank(
            query=query.query, documents=retrieved_docs, top_k=settings.TOP_K_RERANK
        )
        logger.info(f"Reranked to top {len(reranked_docs)} documents")

        # Step 3: Generate response with Gemini
        logger.info("Generating response with Gemini...")
        health_profile_dict = (
            query.health_profile.model_dump() if query.health_profile else None
        )

        response_text = gemini_service.generate_response(
            query=query.query,
            documents=reranked_docs,
            health_profile=health_profile_dict,
        )
        logger.info("Response generated successfully")

        # Step 4: Safety check
        warnings = []
        if settings.ENABLE_SAFETY_CHECK and query.health_profile:
            logger.info("Performing safety check...")
            warnings = safety_checker.check_safety(
                response_text=response_text, health_profile=query.health_profile
            )
            logger.info(f"Found {len(warnings)} safety warnings")

        # Step 5: Prepare citations
        citations = [
            Citation(
                doc_id=str(doc.get("doc_id", "")),
                question=doc.get("question", ""),
                answer=doc.get("answer", ""),
                score=doc.get("rerank_score", doc.get("score", 0)),
            )
            for doc in reranked_docs
        ]

        # Prepare retrieved documents info
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
        logger.info(f"Request processed in {processing_time:.2f}s")

        return ChatResponse(
            answer=response_text,
            citations=citations,
            warnings=warnings,
            retrieved_docs=retrieved_info,
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profile")
async def save_profile(profile: dict):
    """Save user health profile (placeholder - in production, use database)"""
    # In a real application, this would save to a database
    # For now, just return success
    logger.info("Profile save request received")
    return {"status": "success", "message": "Profile saved successfully"}


@app.get("/api/stats")
async def get_stats():
    """Get API statistics"""
    try:
        # Get collection info
        collection_info = qdrant_client.get_collection(settings.QDRANT_COLLECTION)

        return {
            "total_documents": collection_info.points_count,
            "embedding_dimension": embedding_service.get_embedding_dimension(),
            "qdrant_mode": settings.QDRANT_MODE,
            "models": {
                "embedding": settings.EMBEDDING_MODEL,
                "reranker": settings.RERANKER_MODEL,
                "llm": settings.GEMINI_MODEL,
            },
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
