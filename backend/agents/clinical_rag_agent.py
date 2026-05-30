import time
from typing import List, Dict, Optional
from models.schemas import GenerationResult
from services.llm import ClinicalLLMService
from agents.base import BaseAgent


class ClinicalRAGAgent(BaseAgent):
    """
    Giai đoạn 3: Context-Aware Generation & Clinical Synthesis

    Sử dụng Groq Llama 3.3 70B để tổng hợp thông tin từ các tài liệu RAG
    và sinh ra bản nháp phản hồi y khoa (Draft Response).
    Bản nháp bị ràng buộc (grounded) vào tài liệu để giảm hallucination.
    """

    def __init__(self, llm_service: ClinicalLLMService):
        """
        Initialize Clinical RAG Agent

        Args:
            llm_service: ClinicalLLMService instance for clinical inference
        """
        super().__init__(name="ClinicalRAGAgent")
        self.llm_service = llm_service

    def execute(
        self,
        query: str,
        documents: List[Dict],
        health_profile: Optional[Dict] = None,
        chat_history: Optional[List[Dict]] = None,
        strict_mode: bool = True,
    ) -> GenerationResult:
        """
        Generate a draft medical response grounded in retrieved documents.

        Args:
            query: User's medical query
            documents: Top-N reranked documents from retrieval pipeline
            health_profile: User's health profile dict (optional)

        Returns:
            GenerationResult with draft response
        """
        start = time.time()

        try:
            self.logger.info(
                f"Generating response for query with {len(documents)} documents..."
            )

            draft_response = self.llm_service.generate_response(
                query=query,
                documents=documents,
                health_profile=health_profile,
                chat_history=chat_history,
                strict_mode=strict_mode,
            )

            latency = time.time() - start
            self.logger.info(
                f"Draft response generated successfully (latency: {latency:.3f}s)"
            )

            return GenerationResult(
                draft_response=draft_response, latency=latency
            )

        except Exception as e:
            latency = time.time() - start
            self.logger.error(f"Clinical generation failed: {str(e)}")
            raise

    def execute_stream(
        self,
        query: str,
        documents: List[Dict],
        health_profile: Optional[Dict] = None,
        chat_history: Optional[List[Dict]] = None,
        strict_mode: bool = True,
        context_addon: Optional[str] = None,
    ):
        """
        Stream a draft medical response grounded in retrieved documents.
        Yields text chunks as they arrive from Groq Llama 3.3.

        Args:
            query: User's medical query
            documents: Top-N reranked documents from retrieval pipeline
            health_profile: User health profile dict (optional)
            chat_history: Recent conversation context
            context_addon: Optional extra context to append (e.g. cross-session context from Health Corner)

        Yields:
            str: Each text chunk from Groq streaming
        """
        self.logger.info(
            f"Streaming response for query with {len(documents)} documents..."
        )

        try:
            for chunk in self.llm_service.generate_response_stream(
                query=query,
                documents=documents,
                health_profile=health_profile,
                chat_history=chat_history,
                strict_mode=strict_mode,
                context_addon=context_addon,
            ):
                yield chunk
        except Exception as e:
            self.logger.error(f"Clinical streaming generation failed: {str(e)}")
            raise
