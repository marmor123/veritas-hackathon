"""
RAG Quality Test — shows EXACTLY what goes in and what comes out at every stage.

For each scenario, prints:
  1. INPUT: biomarker data
  2. Stage 1: Rewritten clinical query
  3. Stage 2: Top hybrid search candidates with scores
  4. Stage 3: Top 5 after cross-encoder re-ranking
  5. Stage 4: Citations - FULL TEXT excerpt (not just titles)
  6. Output: clinical_graph
  7. Validation: did retrieval find the medically correct content?

Run: python knowledge-base/test_rag_quality.py
"""

import io
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.models.schemas import BiomarkerResult
from backend.verification.verifier import verify_results
from backend.rag.query_rewriter import _fallback_query
from backend.rag.retriever import hybrid_search
from backend.rag.reranker import rerank
from backend.rag.citation import extract_citations
from backend.graph.graph_builder import build_clinical_graph


def header(text, char="="):
    line = char * 78
    print(f"\n{line}\n  {text}\n{line}")


def subheader(text):
    print(f"\n--- {text} " + "-" * (74 - len(text)))


def print_chunk_short(chunk, idx, score_label="combined_score"):
    title = chunk.get("section_title", "Unknown")
    score = chunk.get(score_label, 0)
    biomarkers = chunk.get("biomarkers_text", "")
    print(f"  #{idx}  [score={score:+.3f}]  {title}")
    if biomarkers:
        print(f"        biomarkers: {biomarkers[:75]}")


def print_chunk_full(chunk, idx):
    title = chunk.get("section_title", "Unknown")
    score = chunk.get("relevance_score", 0)
    text = chunk.get("text", "").replace("\n", " ").strip()
    biomarkers = chunk.get("biomarkers_text", "")
    print(f"  #{idx}  [relevance={score:+.3f}]  {title}")
    if biomarkers:
        print(f"        biomarkers: {biomarkers[:75]}")
    # Show first 200 chars of text
    print(f"        text: {text[:220]}...")


def test_query(name, biomarkers, medications=None, wearable_data=None, expected_keywords=None):
    header(f"QUERY: {name}")

    # Stage 0: INPUT
    subheader("INPUT (OCR output)")
    print(f"  {len(biomarkers)} biomarkers from blood test:")
    for b in biomarkers:
        flag = ""
        if b.ref_low and b.value < b.ref_low:
            flag = f"  LOW (ref >= {b.ref_low})"
        elif b.ref_high and b.value > b.ref_high:
            flag = f"  HIGH (ref <= {b.ref_high})"
        print(f"    - {b.name:20} {b.value:>8} {b.unit:10}{flag}")
    if medications:
        print(f"  Medications: {', '.join(medications)}")
    if wearable_data:
        print(f"  Wearable: HR={wearable_data.get('resting_hr_avg')}bpm "
              f"trend={wearable_data.get('resting_hr_trend')}")

    # Verification (Module 3)
    verified = verify_results(biomarkers, medications=medications)
    abnormal_names = [r.biomarker for r in verified.verified_results if r.flagged]

    # Stage 1: Query Rewriting
    subheader("STAGE 1: Query Rewriting")
    print("  HOW IT WORKS:")
    print("    Rule-based pattern detection (deterministic, no LLM in fallback mode):")
    print("      1. Filter to abnormal biomarkers only (flagged=True)")
    print("      2. Categorize by direction (low/high)")
    print("      3. Match against pattern priority list:")
    print("         Ferritin+MCV/Hb -> microcytic anemia")
    print("         B12/Folate+MCV  -> macrocytic anemia")
    print("         TSH             -> hypo/hyperthyroid (uses direction)")
    print("         3+ metabolic    -> metabolic syndrome")
    print("         Creatinine/BUN  -> kidney disease")
    print("         ALT/AST/Bili    -> liver dysfunction")
    print("         K+ high         -> hyperkalemia")
    print("      4. Generate question-shaped query (optimized for cross-encoder)")
    print("      5. Append actual values for semantic specificity")
    print()
    t0 = time.time()
    query = _fallback_query(verified.verified_results)
    t1 = time.time()
    print(f"  Time: {(t1-t0)*1000:.1f}ms")
    print(f"  Output query (this is what Stage 2 will search with):")
    # word wrap
    words = query.split()
    line = "    "
    for w in words:
        if len(line) + len(w) > 76:
            print(line)
            line = "    "
        line += w + " "
    if line.strip():
        print(line.rstrip())

    # Stage 2: Hybrid Search
    subheader("STAGE 2: Hybrid Search (top 10 candidates)")
    print("  HOW IT WORKS:")
    print("    Two parallel searches in LanceDB, then merge with weighted scores:")
    print("      a) Semantic search: embed query (all-MiniLM-L6-v2 -> 384-dim vector),")
    print("         find chunks with closest cosine similarity")
    print("      b) Keyword search: full-text search for biomarker names in 'biomarkers_text'")
    print("      c) Merge with normalized scores: 0.7 * semantic + 0.3 * keyword")
    print("      d) Pre-filter by organ system (e.g., hematologic) when possible")
    print()
    t0 = time.time()
    search_results = hybrid_search(query, abnormal_names, top_k=15)
    t1 = time.time()
    print(f"  Time: {(t1-t0)*1000:.1f}ms")
    print(f"  Retrieved: {len(search_results)} candidates (showing top 10)")
    for i, c in enumerate(search_results[:10], 1):
        print_chunk_short(c, i, "combined_score")

    # Stage 3: Cross-Encoder Re-Rank
    subheader("STAGE 3: Cross-Encoder Re-Rank (top 10 by relevance)")
    t0 = time.time()
    # Top 10 to see how the cross-encoder distributes confidence across more chunks
    ranked = rerank(query, search_results, top_k=10)
    t1 = time.time()
    print(f"  Time: {(t1-t0)*1000:.1f}ms")
    print(f"  Returned: {len(ranked)} chunks (top-10 by relevance)")
    if ranked:
        # Show confidence breakdown
        high = sum(1 for c in ranked if c.get("confidence") == "high")
        mod = sum(1 for c in ranked if c.get("confidence") == "moderate")
        low = sum(1 for c in ranked if c.get("confidence") == "low")
        print(f"  Confidence: {high} high, {mod} moderate, {low} low")
    for i, c in enumerate(ranked, 1):
        print_chunk_full(c, i)

    # Stage 4: Top Citation FULL TEXT (always show — this is what the LLM sees)
    subheader("STAGE 4: TOP CITATION - FULL TEXT (what the LLM will see)")
    citations = extract_citations(ranked)
    if not citations:
        print("  [!] No citations available - search returned 0 chunks")
    else:
        top = citations[0]
        confidence = ranked[0].get("confidence", "unknown") if ranked else "unknown"
        print(f"  Chunk ID:   {top.chunk_id}")
        print(f"  Source:     {top.source}")
        print(f"  Biomarkers: {top.biomarkers_involved}")
        print(f"  Relevance:  {top.relevance_score:+.3f}  (confidence: {confidence})")
        print(f"\n  FULL TEXT (this is what gets sent to the LLM synthesis prompt):")
        print(f"  " + "-" * 74)
        for line in top.text.split("\n"):
            line = line.strip()
            if not line:
                continue
            words = line.split()
            buf = "  | "
            for w in words:
                if len(buf) + len(w) > 76:
                    print(buf)
                    buf = "  | "
                buf += w + " "
            if buf.strip() != "|":
                print(buf.rstrip())
        print(f"  " + "-" * 74)

    # Graph
    subheader("Graph (Graphify)")
    graph = build_clinical_graph(verified.verified_results, citations, wearable_data)
    print(f"  {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    for node in graph.nodes:
        print(f"    [{node.type:9}] {node.label}")

    # Validation
    subheader("VALIDATION")
    if expected_keywords:
        all_text = " ".join(c.text.lower() for c in citations) + " " + \
                   " ".join(r.get("section_title", "").lower() for r in ranked)
        for kw in expected_keywords:
            mark = "[+]" if kw.lower() in all_text else "[-]"
            print(f"  {mark} expected keyword: '{kw}'")
    if not citations:
        print("  [-] FAIL: No citations available")
    else:
        top_score = citations[0].relevance_score
        top_conf = ranked[0].get("confidence", "unknown")
        if top_score > 0:
            print(f"  [+] PASS: Top citation relevance {top_score:+.3f} (high confidence)")
        elif top_conf == "moderate":
            print(f"  [~] OK:   Top citation relevance {top_score:+.3f} (moderate confidence)")
            print(f"           LLM still gets useful clinical context")
        else:
            print(f"  [-] WARN: Top citation relevance {top_score:+.3f} (low confidence)")


def main():
    header("VERITAS RAG Quality Test - Detailed Input/Output Verification", "=")
    print("\nThis test runs realistic blood-test queries and shows exactly what")
    print("the RAG pipeline retrieves at each stage. Verify retrieval quality below.\n")

    # SCENARIO 1: Iron Deficiency
    test_query(
        name="Iron Deficiency Anemia",
        biomarkers=[
            BiomarkerResult(name="Ferritin", value=12, unit="ng/mL",
                            ref_low=15, ref_high=150, flag="L"),
            BiomarkerResult(name="Iron", value=35, unit="ug/dL",
                            ref_low=60, ref_high=170, flag="L"),
            BiomarkerResult(name="MCV", value=78, unit="fL",
                            ref_low=80, ref_high=100, flag="L"),
            BiomarkerResult(name="Hemoglobin", value=11.2, unit="g/dL",
                            ref_low=12, ref_high=16, flag="L"),
        ],
        wearable_data={"resting_hr_avg": 76, "resting_hr_trend": "rising"},
        expected_keywords=["microcytic", "iron", "ferritin"],
    )

    # SCENARIO 2: B12 Deficiency
    test_query(
        name="B12 Deficiency (Macrocytic Anemia)",
        biomarkers=[
            BiomarkerResult(name="Vitamin B12", value=180, unit="pg/mL",
                            ref_low=200, ref_high=900, flag="L"),
            BiomarkerResult(name="MCV", value=108, unit="fL",
                            ref_low=80, ref_high=100, flag="H"),
            BiomarkerResult(name="Hemoglobin", value=10.8, unit="g/dL",
                            ref_low=12, ref_high=16, flag="L"),
        ],
        expected_keywords=["macrocytic", "b12", "folate"],
    )

    # SCENARIO 3: Hypothyroidism
    test_query(
        name="Primary Hypothyroidism",
        biomarkers=[
            BiomarkerResult(name="TSH", value=12.5, unit="mIU/L",
                            ref_low=0.4, ref_high=4.0, flag="H"),
            BiomarkerResult(name="Free T4", value=0.6, unit="ng/dL",
                            ref_low=0.8, ref_high=1.8, flag="L"),
            BiomarkerResult(name="Cholesterol", value=265, unit="mg/dL",
                            ref_low=0, ref_high=200, flag="H"),
        ],
        expected_keywords=["thyroid", "hypothyroid"],
    )

    # SCENARIO 4: Kidney Dysfunction
    test_query(
        name="Kidney Dysfunction",
        biomarkers=[
            BiomarkerResult(name="Creatinine", value=2.4, unit="mg/dL",
                            ref_low=0.6, ref_high=1.3, flag="H"),
            BiomarkerResult(name="BUN", value=45, unit="mg/dL",
                            ref_low=8, ref_high=20, flag="H"),
            BiomarkerResult(name="eGFR", value=32, unit="mL/min",
                            ref_low=60, flag="L"),
            BiomarkerResult(name="Potassium", value=5.4, unit="mmol/L",
                            ref_low=3.5, ref_high=5.0, flag="H"),
        ],
        expected_keywords=["renal", "kidney"],
    )

    header("ALL QUERIES COMPLETE", "=")


if __name__ == "__main__":
    main()
