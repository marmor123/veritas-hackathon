"""
Stage 2: Metadata-Filtered Hybrid Search

Pre-filters LanceDB by organ system, then performs hybrid search
(0.7 semantic + 0.3 keyword) within the filtered set.

Latency target: < 100ms.
"""

import lancedb
import numpy as np
from pathlib import Path

from backend.rag.embeddings import embed_text
from backend.rag.organ_system_map import get_organ_systems_for_biomarkers

# Default path to the LanceDB database
DB_PATH = Path(__file__).parent.parent.parent / "knowledge-base" / "lancedb"

# Singleton DB connection
_db = None
_table = None


def get_db():
    """Get or initialize the LanceDB connection."""
    global _db, _table
    if _db is None:
        _db = lancedb.connect(str(DB_PATH))
        try:
            _table = _db.open_table("clinical_patterns")
        except Exception as e:
            print(f"[Retriever] Could not open table 'clinical_patterns': {e}")
            _table = None
    return _db, _table


def hybrid_search(
    query_text: str,
    abnormal_biomarker_names: list[str],
    top_k: int = 15,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[dict]:
    """
    Perform metadata-filtered hybrid search.

    1. Infer organ systems from abnormal biomarkers
    2. Pre-filter LanceDB by organ system
    3. Semantic search (embedding similarity)
    4. Keyword search (biomarker name matching)
    5. Merge with weighted scoring

    Args:
        query_text: The rewritten clinical query from Stage 1
        abnormal_biomarker_names: List of abnormal biomarker names
        top_k: Number of results to return
        semantic_weight: Weight for semantic similarity (default 0.7)
        keyword_weight: Weight for keyword matching (default 0.3)

    Returns:
        List of chunk dicts sorted by combined score, up to top_k results.
    """
    _, table = get_db()
    if table is None:
        print("[Retriever] No table available. Returning empty results.")
        return []

    # Step 1: Infer relevant organ systems
    relevant_systems = get_organ_systems_for_biomarkers(abnormal_biomarker_names)

    # Step 2: Embed the query
    query_vector = embed_text(query_text)

    # Step 3: Semantic search with metadata filter
    try:
        # Build the organ system filter
        # LanceDB filter syntax for array containment
        system_filter = _build_organ_system_filter(relevant_systems)

        semantic_results = (
            table.search(query_vector.tolist())
            .where(system_filter, prefilter=True)
            .limit(top_k)
            .to_list()
        )
    except Exception as e:
        print(f"[Retriever] Semantic search with filter failed: {e}. Trying without filter.")
        try:
            semantic_results = (
                table.search(query_vector.tolist())
                .limit(top_k)
                .to_list()
            )
        except Exception as e2:
            print(f"[Retriever] Unfiltered search also failed: {e2}")
            semantic_results = []

    # Also do an unfiltered search and merge — ensures we don't miss
    # relevant chunks that have unexpected organ system tags
    try:
        unfiltered_results = (
            table.search(query_vector.tolist())
            .limit(top_k)
            .to_list()
        )
        # Add unfiltered results to semantic_results (will be deduped in merge)
        seen_ids = {r.get("chunk_id") for r in semantic_results}
        for r in unfiltered_results:
            if r.get("chunk_id") not in seen_ids:
                semantic_results.append(r)
                seen_ids.add(r.get("chunk_id"))
    except Exception:
        pass

    # Step 4: Keyword search (biomarker name matching in text)
    keyword_results = _keyword_search(table, abnormal_biomarker_names, top_k)

    # Step 5: Merge results with weighted scoring
    merged = _merge_results(
        semantic_results,
        keyword_results,
        semantic_weight=semantic_weight,
        keyword_weight=keyword_weight,
        top_k=top_k,
    )

    return merged


def _build_organ_system_filter(systems: list[str]) -> str:
    """
    Build a LanceDB WHERE filter for organ systems.
    Since organ_system is stored as a JSON string, we use LIKE on organ_system_text.
    """
    conditions = []
    for system in systems:
        conditions.append(f"organ_system_text LIKE '%{system}%'")
    return " OR ".join(conditions) if conditions else "1=1"


def _keyword_search(table, biomarker_names: list[str], top_k: int) -> list[dict]:
    """
    Search for chunks that mention the abnormal biomarkers by name.
    Uses full-text search if available, otherwise falls back to filtering.
    """
    if not biomarker_names:
        return []

    try:
        # Try FTS search on biomarkers_text field
        search_str = " ".join(biomarker_names)
        results = (
            table.search(search_str, query_type="fts")
            .limit(top_k)
            .to_list()
        )
        return results
    except Exception:
        # FTS not available — fall back to filtering by biomarker mentions
        try:
            conditions = []
            for name in biomarker_names[:5]:  # Limit to avoid overly complex queries
                conditions.append(f"biomarkers_text LIKE '%{name.lower()}%'")
            filter_str = " OR ".join(conditions)
            results = (
                table.search(embed_text(" ".join(biomarker_names)).tolist())
                .where(filter_str, prefilter=True)
                .limit(top_k)
                .to_list()
            )
            return results
        except Exception:
            return []


def _merge_results(
    semantic_results: list[dict],
    keyword_results: list[dict],
    semantic_weight: float,
    keyword_weight: float,
    top_k: int,
) -> list[dict]:
    """
    Merge semantic and keyword results with weighted scoring.
    Deduplicates by chunk_id. Normalizes scores to [0, 1] range before weighting.
    """
    scored: dict[str, dict] = {}

    # Score semantic results (distance-based: lower = better)
    if semantic_results:
        distances = [r.get("_distance", 1.0) for r in semantic_results]
        min_dist = min(distances) if distances else 0
        max_dist = max(distances) if distances else 1
        dist_range = max_dist - min_dist if max_dist > min_dist else 1.0

        for r in semantic_results:
            chunk_id = r.get("chunk_id", "")
            if not chunk_id:
                continue
            distance = r.get("_distance", 1.0)
            # Normalize: 0 distance = 1.0 similarity, max distance = 0.0
            similarity = 1.0 - ((distance - min_dist) / dist_range)
            semantic_score = similarity * semantic_weight

            if chunk_id not in scored:
                scored[chunk_id] = {**r, "combined_score": 0.0}
            scored[chunk_id]["combined_score"] += semantic_score

    # Score keyword results (score-based: higher = better)
    if keyword_results:
        scores = [r.get("_score", 0) for r in keyword_results]
        max_score = max(scores) if scores else 1.0
        if max_score == 0:
            max_score = 1.0

        for r in keyword_results:
            chunk_id = r.get("chunk_id", "")
            if not chunk_id:
                continue
            score = r.get("_score", 0)
            # Normalize to [0, 1]
            normalized = score / max_score
            keyword_score = normalized * keyword_weight

            if chunk_id not in scored:
                scored[chunk_id] = {**r, "combined_score": 0.0}
            scored[chunk_id]["combined_score"] += keyword_score

    # Sort by combined score descending
    sorted_results = sorted(
        scored.values(),
        key=lambda x: x.get("combined_score", 0),
        reverse=True,
    )

    return sorted_results[:top_k]
