import logging
import time
from typing import List, Dict, Optional

import cohere

logger = logging.getLogger(__name__)


class Reranker:
    """
    Reranker using Cohere Rerank API (rerank-v4.0-pro).
    Replaces local CrossEncoder to eliminate CPU bottleneck.
    """

    def __init__(self, api_key: str, model_name: str = "rerank-v4.0-pro"):
        """
        Initialize Cohere Reranker

        Args:
            api_key: Cohere API key
            model_name: Cohere rerank model name
        """
        self.api_key = api_key
        self.model_name = model_name
        self.client: Optional[cohere.Client] = None
        self._is_loaded = False

    def load_model(self):
        """Initialize the Cohere client"""
        try:
            logger.info(f"Initializing Cohere Reranker: {self.model_name}")
            self.client = cohere.Client(api_key=self.api_key)
            self._is_loaded = True
            logger.info("Cohere Reranker initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Cohere Reranker: {str(e)}")
            self._is_loaded = False
            return False

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5,
        return_scores: bool = True,
    ) -> List[Dict]:
        """
        Rerank documents using Cohere Rerank API

        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Number of top documents to return
            return_scores: Whether to include reranking scores

        Returns:
            List of reranked documents
        """
        if not self._is_loaded or self.client is None:
            logger.warning("Cohere client not initialized, returning original order")
            return documents[:top_k]

        if not documents:
            return []

        try:
            start_time = time.time()

            doc_texts = []
            for doc in documents:
                text = f"{doc.get('question', '')} {doc.get('answer', '')}".strip()
                doc_texts.append(text)

            response = self.client.rerank(
                model=self.model_name,
                query=query,
                documents=doc_texts,
                top_n=top_k,
                return_documents=False,
            )

            latency = time.time() - start_time
            logger.info(f"Cohere rerank completed in {latency:.3f}s")

            result = []
            for item in response.results:
                doc_copy = documents[item.index].copy()
                if return_scores:
                    doc_copy["rerank_score"] = float(item.relevance_score)
                result.append(doc_copy)

            return result

        except Exception as e:
            logger.error(f"Error during Cohere reranking: {str(e)}")
            return documents[:top_k]

    def is_loaded(self) -> bool:
        """Check if Cohere client is initialized"""
        return self._is_loaded

    def batch_rerank(
        self,
        queries: List[str],
        document_lists: List[List[Dict]],
        top_k: int = 5,
    ) -> List[List[Dict]]:
        """
        Rerank multiple query-document lists

        Args:
            queries: List of queries
            document_lists: List of document lists (one per query)
            top_k: Number of top documents per query

        Returns:
            List of reranked document lists
        """
        results = []
        for query, documents in zip(queries, document_lists):
            reranked = self.rerank(query, documents, top_k=top_k)
            results.append(reranked)
        return results
