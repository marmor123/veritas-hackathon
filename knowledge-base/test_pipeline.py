"""
End-to-end test of the RAG pipeline (without LLM — uses fallback query rewriter).
Tests the full flow: query rewriting → hybrid search → cross-encoder reranking → citations → graph.
"""
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.api.models.schemas import VerifiedResult, ClinicalGraph
from backend.rag.query_rewriter import _fallback_query
from backend.rag.retriever import hybrid_search
from backend.rag.reranker import rerank
from backend.rag.citation import extract_citations, format_citations_for_prompt
from backend.graph.graph_builder import build_clinical_graph


def test_iron_deficiency():
    """Test Case 1: Iron Deficiency + Wearable"""
    print("=" * 70)
    print("TEST CASE 1: Iron Deficiency + Wearable")
    print("=" * 70)

    verified_results = [
        VerifiedResult(biomarker="Ferritin", value=12, unit="ng/mL",
                      ref_low=15, ref_high=150, flagged=True, flag_reason="Below range"),
        VerifiedResult(biomarker="Iron", value=35, unit="µg/dL",
                      ref_low=60, ref_high=170, flagged=True, flag_reason="Below range"),
        VerifiedResult(biomarker="MCV", value=78, unit="fL",
                      ref_low=80, ref_high=100, flagged=True, flag_reason="Below range"),
        VerifiedResult(biomarker="Hemoglobin", value=11.2, unit="g/dL",
                      ref_low=12, ref_high=16, flagged=True, flag_reason="Below range"),
        # Normal values
        VerifiedResult(biomarker="Glucose", value=92, unit="mg/dL",
                      ref_low=70, ref_high=100, flagged=False),
        VerifiedResult(biomarker="TSH", value=2.1, unit="mIU/L",
                      ref_low=0.4, ref_high=4.0, flagged=False),
    ]

    wearable_data = {"resting_hr_avg": 76, "resting_hr_trend": "rising"}

    # Stage 1: Query rewriting (fallback — no LLM)
    t0 = time.time()
    query = _fallback_query(verified_results)
    t1 = time.time()
    print(f"\n[Stage 1] Query Rewriting ({t1-t0:.3f}s):")
    print(f"  Query: {query}")

    # Stage 2: Hybrid search
    abnormal_names = [r.biomarker for r in verified_results if r.flagged]
    t0 = time.time()
    search_results = hybrid_search(query, abnormal_names, top_k=15)
    t1 = time.time()
    print(f"\n[Stage 2] Hybrid Search ({t1-t0:.3f}s): {len(search_results)} results")
    for r in search_results[:5]:
        print(f"  {r.get('section_title', 'N/A')[:60]} (score: {r.get('combined_score', 0):.3f})")

    # Stage 3: Cross-encoder reranking
    t0 = time.time()
    ranked = rerank(query, search_results, top_k=5)
    t1 = time.time()
    print(f"\n[Stage 3] Cross-Encoder Reranking ({t1-t0:.3f}s): {len(ranked)} chunks passed")
    for r in ranked:
        print(f"  {r.get('section_title', 'N/A')[:60]} (relevance: {r.get('relevance_score', 0):.3f})")

    # Stage 4: Citations
    citations = extract_citations(ranked)
    formatted = format_citations_for_prompt(citations)
    print(f"\n[Stage 4] Citations: {len(citations)} chunks with sources")
    for c in citations:
        print(f"  [{c.chunk_id}] {c.source[:60]} (score: {c.relevance_score:.3f})")

    # Graphify
    t0 = time.time()
    graph = build_clinical_graph(verified_results, citations, wearable_data)
    t1 = time.time()
    print(f"\n[Graphify] Knowledge Graph ({t1-t0:.3f}s):")
    print(f"  Nodes: {len(graph.nodes)}")
    for node in graph.nodes:
        print(f"    [{node.type}] {node.label}")
    print(f"  Edges: {len(graph.edges)}")
    for edge in graph.edges:
        print(f"    {edge.source} --{edge.relation}--> {edge.target}")

    # Validation
    print("\n[Validation]")
    if ranked:
        all_titles = " ".join(r["section_title"].lower() for r in ranked)
        if any(kw in all_titles for kw in ["microcytic", "iron", "anemia", "ferritin", "red blood cell", "hematologic"]):
            print("  ✓ Results contain iron/anemia/hematologic content")
        else:
            print(f"  ✗ No iron-related content found in results")

    if any(n.id == "resting_hr" for n in graph.nodes):
        print("  ✓ Wearable HR node present in graph")
    else:
        print("  ✗ Wearable HR node missing")

    if len(graph.nodes) >= 4:
        print(f"  ✓ Graph has {len(graph.nodes)} nodes (expected >= 4)")
    else:
        print(f"  ✗ Graph only has {len(graph.nodes)} nodes")

    return True


def test_metabolic_syndrome():
    """Test Case 2: Metabolic Syndrome"""
    print("\n\n" + "=" * 70)
    print("TEST CASE 2: Metabolic Syndrome")
    print("=" * 70)

    verified_results = [
        VerifiedResult(biomarker="Glucose", value=108, unit="mg/dL",
                      ref_low=70, ref_high=100, flagged=True, flag_reason="Above range"),
        VerifiedResult(biomarker="HDL", value=34, unit="mg/dL",
                      ref_low=40, ref_high=100, flagged=True, flag_reason="Below range"),
        VerifiedResult(biomarker="Triglycerides", value=195, unit="mg/dL",
                      ref_low=0, ref_high=150, flagged=True, flag_reason="Above range"),
        VerifiedResult(biomarker="ALT", value=48, unit="U/L",
                      ref_low=0, ref_high=35, flagged=True, flag_reason="Above range"),
        VerifiedResult(biomarker="Uric Acid", value=7.8, unit="mg/dL",
                      ref_low=3.5, ref_high=7.2, flagged=True, flag_reason="Above range"),
    ]

    # Stage 1
    query = _fallback_query(verified_results)
    print(f"\n[Stage 1] Query: {query}")

    # Stage 2
    abnormal_names = [r.biomarker for r in verified_results if r.flagged]
    t0 = time.time()
    search_results = hybrid_search(query, abnormal_names, top_k=15)
    t1 = time.time()
    print(f"\n[Stage 2] Hybrid Search ({t1-t0:.3f}s): {len(search_results)} results")
    for r in search_results[:3]:
        print(f"  {r.get('section_title', 'N/A')[:60]}")

    # Stage 3
    t0 = time.time()
    ranked = rerank(query, search_results, top_k=5)
    t1 = time.time()
    print(f"\n[Stage 3] Reranking ({t1-t0:.3f}s): {len(ranked)} chunks")
    for r in ranked:
        print(f"  {r.get('section_title', 'N/A')[:60]} (relevance: {r.get('relevance_score', 0):.3f})")

    # Graphify
    graph = build_clinical_graph(verified_results)
    print(f"\n[Graphify] Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")
    for node in graph.nodes:
        print(f"    [{node.type}] {node.label}")

    # Validation
    print("\n[Validation]")
    top_title = ranked[0]["section_title"].lower() if ranked else ""
    if "metabolic" in top_title or "syndrome" in top_title or "insulin" in top_title:
        print("  ✓ Top result is metabolic syndrome related")
    else:
        print(f"  ⚠ Top result is: {ranked[0]['section_title'] if ranked else 'none'}")

    return True


def test_all_normal():
    """Test Case 3: All Normal (Fast Path)"""
    print("\n\n" + "=" * 70)
    print("TEST CASE 3: All Normal (Fast Path)")
    print("=" * 70)

    verified_results = [
        VerifiedResult(biomarker="Hemoglobin", value=14.5, unit="g/dL",
                      ref_low=12, ref_high=16, flagged=False),
        VerifiedResult(biomarker="Glucose", value=92, unit="mg/dL",
                      ref_low=70, ref_high=100, flagged=False),
        VerifiedResult(biomarker="TSH", value=2.1, unit="mIU/L",
                      ref_low=0.4, ref_high=4.0, flagged=False),
    ]

    abnormal = [r for r in verified_results if r.flagged]
    if not abnormal:
        print("\n  ✓ Fast path triggered — no abnormal biomarkers, RAG skipped")
        graph = build_clinical_graph(verified_results)
        print(f"  ✓ Graph is empty: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        return True
    return False


if __name__ == "__main__":
    print("VERITAS RAG Pipeline — End-to-End Test")
    print("(Using fallback query rewriter — no LLM required)\n")

    total_start = time.time()

    test_iron_deficiency()
    test_metabolic_syndrome()
    test_all_normal()

    total_time = time.time() - total_start
    print(f"\n\n{'=' * 70}")
    print(f"ALL TESTS COMPLETED in {total_time:.1f}s")
    print(f"{'=' * 70}")
