import logging
from typing import List, Dict, Tuple
from sentence_transformers import CrossEncoder
import torch

logger = logging.getLogger(__name__)

class Reranker:
    """Reranker using cross-encoder models"""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initialize reranker
        
        Args:
            model_name: Name of the cross-encoder model
        """
        self.model_name = model_name
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Reranker will use device: {self.device}")
        
    def load_model(self):
        """Load the reranker model"""
        try:
            logger.info(f"Loading reranker model: {self.model_name}")
            self.model = CrossEncoder(self.model_name, device=self.device)
            logger.info("Reranker model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load reranker model: {str(e)}")
            # Try fallback model
            try:
                logger.info("Attempting to load fallback reranker model")
                self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=self.device)
                logger.info("Fallback reranker model loaded successfully")
                return True
            except Exception as e2:
                logger.error(f"Failed to load fallback reranker: {str(e2)}")
                return False
    
    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5,
        return_scores: bool = True
    ) -> List[Dict]:
        """
        Rerank documents based on query relevance
        
        Args:
            query: Search query
            documents: List of documents to rerank
            top_k: Number of top documents to return
            return_scores: Whether to include reranking scores
            
        Returns:
            List of reranked documents
        """
        if self.model is None:
            logger.warning("Reranker model not loaded, returning original order")
            return documents[:top_k]
        
        if not documents:
            return []
        
        try:
            # Prepare query-document pairs
            pairs = []
            for doc in documents:
                # Combine question and answer for better matching
                doc_text = f"{doc.get('question', '')} {doc.get('answer', '')}".strip()
                pairs.append([query, doc_text])
            
            # Get reranking scores
            scores = self.model.predict(pairs, show_progress_bar=False)
            
            # Combine documents with scores
            doc_scores = list(zip(documents, scores))
            
            # Sort by score (descending)
            doc_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Get top-k
            top_docs = doc_scores[:top_k]
            
            # Add rerank scores to documents
            if return_scores:
                result = []
                for doc, score in top_docs:
                    doc_copy = doc.copy()
                    doc_copy['rerank_score'] = float(score)
                    result.append(doc_copy)
                return result
            else:
                return [doc for doc, _ in top_docs]
                
        except Exception as e:
            logger.error(f"Error during reranking: {str(e)}")
            return documents[:top_k]
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
    
    def batch_rerank(
        self,
        queries: List[str],
        document_lists: List[List[Dict]],
        top_k: int = 5
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
