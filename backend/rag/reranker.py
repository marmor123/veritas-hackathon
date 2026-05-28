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
RELEVANCE_THRESHOLD = -3.0  # Threshold for fallback mode (negative scores expected without LLM rewriter)
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
    always_return_top_k: bool = True,
) -> list[dict]:
    """
    Re-rank retrieved chunks using the cross-encoder.

    Args:
        query: The rewritten clinical query from Stage 1
        chunks: List of chunk dicts from Stage 2 (hybrid search)
        threshold: Score below which a chunk is marked as low-confidence (default -3.0)
        top_k: Maximum number of chunks to return (default 5)
        always_return_top_k: If True (default), always return top_k chunks regardless of
                            threshold — threshold is just a confidence indicator.
                            The LLM should always get the best-available context;
                            denying it ALL context is worse than giving low-confidence context.
                            Set to False for strict filtering.

    Returns:
        List of top-k chunks sorted by cross-encoder score descending.
        Each chunk gets:
          - 'relevance_score': raw cross-encoder score
          - 'confidence': 'high' (>0.3), 'moderate' (>threshold), or 'low' (<=threshold)
    """
    if not chunks:
        return []

    reranker = get_reranker()

    # Create (query, chunk_text) pairs for scoring
    pairs = [(query, chunk.get("text", "")) for chunk in chunks]

    # Batch predict relevance scores
    scores = reranker.predict(pairs, batch_size=8)

    # Attach scores + confidence labels
    scored_chunks = []
    for chunk, score in zip(chunks, scores):
        chunk_copy = dict(chunk)
        chunk_copy["relevance_score"] = float(score)

        if score > 0.3:
            chunk_copy["confidence"] = "high"
        elif score > threshold:
            chunk_copy["confidence"] = "moderate"
        else:
            chunk_copy["confidence"] = "low"

        scored_chunks.append(chunk_copy)

    # Sort by score descending
    scored_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)

    if always_return_top_k:
        # Always return top_k — threshold is informational
        return scored_chunks[:top_k]
    else:
        # Strict mode: filter by threshold
        filtered = [c for c in scored_chunks if c["relevance_score"] >= threshold]
        return filtered[:top_k]
