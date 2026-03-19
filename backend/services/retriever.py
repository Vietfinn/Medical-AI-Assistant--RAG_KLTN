import logging
from typing import List, Dict, Any, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, SearchRequest
from rank_bm25 import BM25Okapi
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)

class HybridRetriever:
    """Hybrid retriever combining vector search and BM25"""
    
    def __init__(
        self,
        qdrant_client: QdrantClient,
        collection_name: str,
        embedding_service,
        alpha: float = 0.5
    ):
        """
        Initialize hybrid retriever
        
        Args:
            qdrant_client: Qdrant client instance
            collection_name: Name of the collection
            embedding_service: Embedding service instance
            alpha: Weight for combining scores (0=BM25 only, 1=vector only)
        """
        self.client = qdrant_client
        self.collection_name = collection_name
        self.embedding_service = embedding_service
        self.alpha = alpha
        self.bm25 = None
        self.documents = []
        self.doc_ids = []
        
    def create_collection(self, vector_size: int):
        """Create Qdrant collection"""
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Collection '{self.collection_name}' created successfully")
            return True
        except Exception as e:
            logger.warning(f"Collection might already exist: {str(e)}")
            return False
    
    def index_documents(self, documents: List[Dict[str, Any]]):
        """
        Index documents into Qdrant and prepare BM25
        
        Args:
            documents: List of documents with 'id', 'question', 'answer', 'context'
        """
        logger.info(f"Indexing {len(documents)} documents...")
        
        # Prepare texts for embedding and BM25
        texts = []
        self.documents = []
        self.doc_ids = []
        
        for doc in documents:
            # Combine question, answer, and context for better retrieval
            text = f"{doc.get('question', '')} {doc.get('answer', '')} {doc.get('context', '')}".strip()
            texts.append(text)
            self.documents.append(doc)
            self.doc_ids.append(doc.get('id', str(len(self.doc_ids))))
        
        # Generate embeddings
        logger.info("Generating embeddings...")
        embeddings = self.embedding_service.encode_documents(texts)
        
        # Index into Qdrant
        logger.info("Indexing into Qdrant...")
        points = []
        for idx, (doc_id, embedding, doc) in enumerate(zip(self.doc_ids, embeddings, self.documents)):
            point = PointStruct(
                id=idx,
                vector=embedding.tolist(),
                payload={
                    "doc_id": doc_id,
                    "question": doc.get("question", ""),
                    "answer": doc.get("answer", ""),
                    "context": doc.get("context", ""),
                    "text": texts[idx]
                }
            )
            points.append(point)
        
        # Upload in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i+batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
        
        logger.info(f"Indexed {len(points)} documents into Qdrant")
        
        # Prepare BM25
        logger.info("Preparing BM25 index...")
        tokenized_texts = [text.lower().split() for text in texts]
        self.bm25 = BM25Okapi(tokenized_texts)
        logger.info("BM25 index prepared")
        
    def vector_search(self, query: str, top_k: int = 30) -> List[Tuple[Dict, float]]:
        """
        Perform vector search
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (document, score) tuples
        """
        query_embedding = self.embedding_service.encode_query(query)
        
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding.tolist(),
            limit=top_k,
            with_payload=True
        )
        
        return [(point.payload, point.score) for point in response.points]
    
    def bm25_search(self, query: str, top_k: int = 30) -> List[Tuple[Dict, float]]:
        """
        Perform BM25 search
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (document, score) tuples
        """
        if self.bm25 is None:
            logger.warning("BM25 not initialized")
            return []
        
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            doc = {
                "doc_id": self.doc_ids[idx],
                "question": self.documents[idx].get("question", ""),
                "answer": self.documents[idx].get("answer", ""),
                "context": self.documents[idx].get("context", ""),
                "text": f"{self.documents[idx].get('question', '')} {self.documents[idx].get('answer', '')}".strip()
            }
            results.append((doc, float(scores[idx])))
        
        return results
    
    def hybrid_search(self, query: str, top_k: int = 30) -> List[Dict]:
        """
        Perform hybrid search combining vector and BM25
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of documents with combined scores
        """
        # Get results from both methods
        vector_results = self.vector_search(query, top_k=top_k)
        bm25_results = self.bm25_search(query, top_k=top_k)
        
        # Normalize scores
        def normalize_scores(results):
            if not results:
                return {}
            scores = [score for _, score in results]
            min_score = min(scores) if scores else 0
            max_score = max(scores) if scores else 1
            range_score = max_score - min_score if max_score != min_score else 1
            
            normalized = {}
            for doc, score in results:
                doc_id = doc['doc_id']
                normalized[doc_id] = (score - min_score) / range_score
            return normalized
        
        vector_scores = normalize_scores(vector_results)
        bm25_scores = normalize_scores(bm25_results)
        
        # Combine scores
        all_doc_ids = set(vector_scores.keys()) | set(bm25_scores.keys())
        combined_results = {}
        
        for doc_id in all_doc_ids:
            v_score = vector_scores.get(doc_id, 0)
            b_score = bm25_scores.get(doc_id, 0)
            combined_score = self.alpha * v_score + (1 - self.alpha) * b_score
            
            # Get document from either source
            doc = None
            for d, _ in vector_results:
                if d['doc_id'] == doc_id:
                    doc = d
                    break
            if doc is None:
                for d, _ in bm25_results:
                    if d['doc_id'] == doc_id:
                        doc = d
                        break
            
            if doc:
                combined_results[doc_id] = {
                    'document': doc,
                    'score': combined_score,
                    'vector_score': v_score,
                    'bm25_score': b_score
                }
        
        # Sort by combined score
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x['score'],
            reverse=True
        )[:top_k]
        
        # Return documents with scores
        return [
            {
                **result['document'],
                'score': result['score'],
                'vector_score': result['vector_score'],
                'bm25_score': result['bm25_score']
            }
            for result in sorted_results
        ]
