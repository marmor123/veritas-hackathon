"""
RAG Pipeline — Full 5-stage retrieval pipeline.

Orchestrates:
  Stage 1: Query Rewriting (LLM Pass 1)
  Stage 2: Metadata-Filtered Hybrid Search
  Stage 3: Cross-Encoder Re-Ranking
  Stage 4: Citation Tracking
  Stage 5: (Delegated to LLM Synthesis module)

Plus: Graphify integration for knowledge graph construction.

Total latency budget: ~16 seconds
  - Query rewriting: ~3 sec
  - Hybrid search: ~0.1 sec
  - Cross-encoder: ~1 sec
  - LLM synthesis: ~12 sec (handled by Module E)
"""

import time
from typing import Optional

from backend.api.models.schemas import (
    VerifiedResult,
    RetrievedChunk,
    RAGOutput,
    ClinicalGraph,
)
from backend.rag.query_rewriter import rewrite_query
from backend.rag.retriever import hybrid_search
from backend.rag.reranker import rerank
from backend.rag.citation import extract_citations, format_citations_for_prompt
from backend.graph.graph_builder import build_clinical_graph


class RAGPipeline:
    """
    Full RAG pipeline for clinical pattern retrieval.

    Usage:
        pipeline = RAGPipeline()
        result = pipeline.run(verified_results, medications)
    """

    def __init__(
        self,
        llm_model: str = "qvac-medpsy:1.7b",
        rerank_threshold: float = 0.3,
        rerank_top_k: int = 5,
        search_top_k: int = 15,
    ):
        self.llm_model = llm_model
        self.rerank_threshold = rerank_threshold
        self.rerank_top_k = rerank_top_k
        self.search_top_k = search_top_k

    def run(
        self,
        verified_results: list[VerifiedResult],
        medications: list[str] | None = None,
        wearable_data: dict | None = None,
    ) -> dict:
        """
        Execute the full RAG pipeline.

        Args:
            verified_results: Verified biomarker results from Module 3
            medications: Optional list of medication names
            wearable_data: Optional wearable data dict

        Returns:
            Dict with keys:
              - rag_output: RAGOutput with matched patterns
              - citations: List of RetrievedChunk objects
              - citations_formatted: String for LLM prompt
              - clinical_graph: ClinicalGraph for frontend visualization
              - timings: Dict of stage latencies
              - rewritten_query: The clinical query from Stage 1
        """
        timings = {}

        # ── Fast path check ──────────────────────────────────────────────
        abnormal = [r for r in verified_results if r.flagged]
        if not abnormal:
            return {
                "rag_output": RAGOutput(
                    matched_patterns=[],
                    unmatched_abnormal_biomarkers=[],
                ),
                "citations": [],
                "citations_formatted": "",
                "clinical_graph": ClinicalGraph(nodes=[], edges=[]),
                "timings": {"fast_path": True},
                "rewritten_query": "",
            }

        abnormal_names = [r.biomarker for r in abnormal]

        # ── Stage 1: Query Rewriting ─────────────────────────────────────
        t0 = time.time()
        rewritten_query = rewrite_query(
            verified_results=verified_results,
            medications=medications,
            model=self.llm_model,
        )
        timings["query_rewriting"] = time.time() - t0
        print(f"[RAG] Stage 1 (Query Rewriting): {timings['query_rewriting']:.2f}s")
        print(f"[RAG] Rewritten query: {rewritten_query[:200]}...")

        # ── Stage 2: Metadata-Filtered Hybrid Search ─────────────────────
        t0 = time.time()
        search_results = hybrid_search(
            query_text=rewritten_query,
            abnormal_biomarker_names=abnormal_names,
            top_k=self.search_top_k,
        )
        timings["hybrid_search"] = time.time() - t0
        print(f"[RAG] Stage 2 (Hybrid Search): {timings['hybrid_search']:.2f}s, "
              f"{len(search_results)} results")

        # ── Stage 3: Cross-Encoder Re-Ranking ────────────────────────────
        t0 = time.time()
        ranked_chunks = rerank(
            query=rewritten_query,
            chunks=search_results,
            threshold=self.rerank_threshold,
            top_k=self.rerank_top_k,
        )
        timings["reranking"] = time.time() - t0
        print(f"[RAG] Stage 3 (Re-Ranking): {timings['reranking']:.2f}s, "
              f"{len(ranked_chunks)} chunks passed threshold")

        # ── Stage 4: Citation Tracking ───────────────────────────────────
        t0 = time.time()
        citations = extract_citations(ranked_chunks)
        citations_formatted = format_citations_for_prompt(citations)
        timings["citation_tracking"] = time.time() - t0

        # ── Graphify: Build Knowledge Graph ──────────────────────────────
        t0 = time.time()
        clinical_graph = build_clinical_graph(
            verified_results=verified_results,
            retrieved_chunks=citations,
            wearable_data=wearable_data,
        )
        timings["graph_building"] = time.time() - t0
        print(f"[RAG] Graphify: {timings['graph_building']:.2f}s, "
              f"{len(clinical_graph.nodes)} nodes, {len(clinical_graph.edges)} edges")

        # ── Build RAG Output ─────────────────────────────────────────────
        matched_patterns = []
        if ranked_chunks:
            # Group chunks by pattern (section_title as proxy)
            pattern_groups: dict[str, list[dict]] = {}
            for chunk in ranked_chunks:
                pattern_name = chunk.get("section_title", "Unknown Pattern")
                if pattern_name not in pattern_groups:
                    pattern_groups[pattern_name] = []
                pattern_groups[pattern_name].append(chunk)

            for pattern_name, chunks in pattern_groups.items():
                # Determine which biomarkers this pattern covers
                covered_biomarkers = set()
                for chunk in chunks:
                    for bm in chunk.get("biomarkers_mentioned", []):
                        if bm.lower() in {n.lower() for n in abnormal_names}:
                            covered_biomarkers.add(bm)

                matched_patterns.append({
                    "pattern_name": pattern_name,
                    "confidence": _infer_confidence(chunks),
                    "supporting_biomarkers": list(covered_biomarkers),
                    "retrieved_chunks": [c.get("chunk_id") for c in chunks],
                    "differential": [],  # Populated by LLM in Stage 5
                })

        # Find unmatched biomarkers
        matched_biomarkers = set()
        for p in matched_patterns:
            matched_biomarkers.update(p["supporting_biomarkers"])
        unmatched = [
            n for n in abnormal_names
            if n.lower() not in {m.lower() for m in matched_biomarkers}
        ]

        rag_output = RAGOutput(
            matched_patterns=matched_patterns,
            unmatched_abnormal_biomarkers=unmatched,
        )

        total_time = sum(v for v in timings.values() if isinstance(v, float))
        print(f"[RAG] Total pipeline time (excl. LLM synthesis): {total_time:.2f}s")

        return {
            "rag_output": rag_output,
            "citations": citations,
            "citations_formatted": citations_formatted,
            "clinical_graph": clinical_graph,
            "timings": timings,
            "rewritten_query": rewritten_query,
        }


def _infer_confidence(chunks: list[dict]) -> str:
    """Infer confidence level from chunk relevance scores."""
    if not chunks:
        return "LOW"
    avg_score = sum(c.get("relevance_score", 0) for c in chunks) / len(chunks)
    if avg_score > 0.7:
        return "HIGH"
    elif avg_score > 0.5:
        return "MODERATE"
    return "LOW"
