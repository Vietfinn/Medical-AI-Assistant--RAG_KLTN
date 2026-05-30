# ============================================================
# Dockerfile for Medical AI Assistant Backend
# Deploy target: Hugging Face Spaces (Docker SDK)
# HF Spaces requires the app to listen on port 7860
# ============================================================

FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Set working directory
WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download Hugging Face dense and sparse embedding models to cache in the image
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('bkai-foundation-models/vietnamese-bi-encoder')"
RUN python -c "from fastembed import SparseTextEmbedding; SparseTextEmbedding('Qdrant/bm25')"

# Copy the entire backend source code
COPY backend/ .

# Expose the HF Spaces default port
EXPOSE 7860

# Start the FastAPI server on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
