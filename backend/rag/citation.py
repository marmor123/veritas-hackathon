"""
Stage 4: Citation Tracking

Each retrieved chunk carries immutable metadata: chunk_id, source, chapter,
section_title, relevance_score. These are passed to the LLM synthesis prompt.
The LLM MUST cite chunk_id for every clinical claim.
The frontend resolves chunk_ids to human-readable citations.
"""

from backend.api.models.schemas import RetrievedChunk


def extract_citations(ranked_chunks: list[dict]) -> list[RetrievedChunk]:
    """
    Convert ranked chunk dicts into RetrievedChunk objects with citation metadata.

    Args:
        ranked_chunks: Top-k chunks from the reranker (Stage 3)

    Returns:
        List of RetrievedChunk objects ready for LLM synthesis.
        The full text of each chunk is preserved — no truncation.
    """
    import json

    citations = []
    for chunk in ranked_chunks:
        # biomarkers_mentioned may be a JSON string (from LanceDB) or a list
        biomarkers = chunk.get("biomarkers_mentioned", [])
        if isinstance(biomarkers, str):
            try:
                biomarkers = json.loads(biomarkers)
            except (json.JSONDecodeError, TypeError):
                biomarkers = biomarkers.split() if biomarkers else []

        citation = RetrievedChunk(
            chunk_id=chunk.get("chunk_id", "unknown"),
            source=_format_source(chunk),
            text=chunk.get("text", ""),
            relevance_score=chunk.get("relevance_score", 0.0),
            biomarkers_involved=biomarkers,
        )
        citations.append(citation)
    return citations


def format_citations_for_prompt(citations: list[RetrievedChunk]) -> str:
    """
    Format citations into a string for the LLM synthesis prompt.
    Each chunk is labeled with its citation ID for the LLM to reference.
    """
    if not citations:
        return "No relevant clinical knowledge found."

    parts = []
    for i, c in enumerate(citations, 1):
        parts.append(
            f"[CITATION {c.chunk_id}] (Source: {c.source}, "
            f"Relevance: {c.relevance_score:.2f})\n{c.text}"
        )
    return "\n\n---\n\n".join(parts)


def resolve_citation_id(chunk_id: str, all_chunks: list[dict]) -> str:
    """
    Resolve a chunk_id to a human-readable citation string.
    Used by the frontend to display source references.
    """
    for chunk in all_chunks:
        if chunk.get("chunk_id") == chunk_id:
            return _format_source(chunk)
    return f"Source: {chunk_id}"


def _format_source(chunk: dict) -> str:
    """Format a chunk's metadata into a human-readable source string."""
    source = chunk.get("source", "Wallach's Interpretation of Diagnostic Tests")
    chapter = chunk.get("chapter", "")
    section = chunk.get("section_title", "")

    parts = [source]
    if chapter:
        # Format chapter name nicely
        ch_name = chapter.replace("_", " ").replace("chapter", "Ch.").title()
        parts.append(ch_name)
    if section:
        parts.append(section)

    return ", ".join(parts)
