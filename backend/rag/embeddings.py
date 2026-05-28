"""
Embedding model wrapper for the RAG pipeline.

Uses all-MiniLM-L6-v2 (~80MB, fast on CPU) for semantic search.
Loads once at startup and reuses for all queries.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

# Singleton model instance
_model: SentenceTransformer | None = None

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # Output dimension for all-MiniLM-L6-v2


def get_model() -> SentenceTransformer:
    """Get or initialize the embedding model (singleton)."""
    global _model
    if _model is None:
        print(f"Loading embedding model: {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME)
        print(f"Embedding model loaded. Dimension: {EMBEDDING_DIM}")
    return _model


def embed_text(text: str) -> np.ndarray:
    """Embed a single text string. Returns a 384-dim vector."""
    model = get_model()
    return model.encode(text, normalize_embeddings=True)


def embed_texts(texts: list[str], batch_size: int = 32) -> np.ndarray:
    """Embed multiple texts. Returns array of shape (n, 384)."""
    model = get_model()
    return model.encode(texts, batch_size=batch_size, normalize_embeddings=True)


def compute_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors (already normalized)."""
    return float(np.dot(vec_a, vec_b))
