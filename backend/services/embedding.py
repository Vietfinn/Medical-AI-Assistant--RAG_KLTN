import logging
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
import torch

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating text embeddings using Vietnamese models"""
    
    def __init__(self, model_name: str = "keepitreal/vietnamese-sbert"):
        """
        Initialize embedding service
        
        Args:
            model_name: Name of the SentenceTransformer model
        """
        self.model_name = model_name
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Embedding service will use device: {self.device}")
        
    def load_model(self):
        """Load the embedding model"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info("Embedding model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load embedding model: {str(e)}")
            # Fallback to a more common model
            try:
                logger.info("Attempting to load fallback model: all-MiniLM-L6-v2")
                self.model = SentenceTransformer("all-MiniLM-L6-v2", device=self.device)
                logger.info("Fallback model loaded successfully")
                return True
            except Exception as e2:
                logger.error(f"Failed to load fallback model: {str(e2)}")
                return False
    
    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Encode texts into embeddings
        
        Args:
            texts: Single text or list of texts
            batch_size: Batch size for encoding
            normalize: Whether to normalize embeddings
            
        Returns:
            Numpy array of embeddings
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        if isinstance(texts, str):
            texts = [texts]
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            return embeddings
        except Exception as e:
            logger.error(f"Error encoding texts: {str(e)}")
            raise
    
    def encode_query(self, query: str, normalize: bool = True) -> np.ndarray:
        """
        Encode a single query
        
        Args:
            query: Query text
            normalize: Whether to normalize embedding
            
        Returns:
            Numpy array of embedding
        """
        return self.encode(query, normalize=normalize)[0]
    
    def encode_documents(
        self,
        documents: List[str],
        batch_size: int = 32,
        normalize: bool = True
    ) -> np.ndarray:
        """
        Encode multiple documents
        
        Args:
            documents: List of document texts
            batch_size: Batch size for encoding
            normalize: Whether to normalize embeddings
            
        Returns:
            Numpy array of embeddings
        """
        return self.encode(documents, batch_size=batch_size, normalize=normalize)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        if self.model is None:
            raise RuntimeError("Model not loaded")
        return self.model.get_sentence_embedding_dimension()
    
    def is_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None
