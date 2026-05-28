"""
Stage 3: Cross-Encoder Re-Ranking

Uses ms-marco-MiniLM-L-6-v2 (~90MB) to score each (query, chunk) pair directly.
Much more accurate than embedding similarity alone because it reads the full
text pair together rather than comparing compressed representations.

Latency target: < 1 second for 15 chunks.
"""

from sentence_transformers import CrossEncoder

# Singleton cross-encoder model
_reranker: CrossEncoder | None = None

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RELEVANCE_THRESHOLD = -2.0  # Threshold for fallback mode (negative scores expected without LLM rewriter)
TOP_K = 5  # Keep top-5 after re-ranking


def get_reranker() -> CrossEncoder:
    """Get or initialize the cross-encoder model (singleton)."""
    global _reranker
    if _reranker is None:
        print(f"Loading cross-encoder: {MODEL_NAME}...")
        _reranker = CrossEncoder(MODEL_NAME)
        print("Cross-encoder loaded.")
    return _reranker


def rerank(
    query: str,
    chunks: list[dict],
    threshold: float = RELEVANCE_THRESHOLD,
    top_k: int = TOP_K,
) -> list[dict]:
    """
    Re-rank retrieved chunks using the cross-encoder.

    Args:
        query: The rewritten clinical query from Stage 1
        chunks: List of chunk dicts from Stage 2 (hybrid search)
        threshold: Minimum relevance score to keep a chunk (default 0.3)
        top_k: Maximum number of chunks to return (default 5)

    Returns:
        List of top-k chunks that pass the relevance threshold,
        sorted by cross-encoder score descending.
        Each chunk gets a 'relevance_score' field added.
    """
    if not chunks:
        return []

    reranker = get_reranker()

    # Create (query, chunk_text) pairs for scoring
    pairs = [(query, chunk.get("text", "")) for chunk in chunks]

    # Batch predict relevance scores
    scores = reranker.predict(pairs, batch_size=8)

    # Attach scores to chunks
    scored_chunks = []
    for chunk, score in zip(chunks, scores):
        chunk_copy = dict(chunk)
        chunk_copy["relevance_score"] = float(score)
        scored_chunks.append(chunk_copy)

    # Filter by threshold
    filtered = [c for c in scored_chunks if c["relevance_score"] >= threshold]

    # Sort by score descending
    filtered.sort(key=lambda x: x["relevance_score"], reverse=True)

    # Return top-k
    return filtered[:top_k]
