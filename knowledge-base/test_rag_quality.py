"""
RAG Quality Test — compares Fallback vs LLM query rewriting.

For each scenario, runs the pipeline twice: once with the deterministic
fallback query, once with the LLM-generated query (qwen3.5:0.8b via Ollama).
Shows comparison of cross-encoder scores and top citations.

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
from backend.rag.query_rewriter import rewrite_query, _fallback_query
from backend.rag.retriever import hybrid_search
from backend.rag.reranker import rerank
from backend.rag.citation import extract_citations
from backend.graph.graph_builder import build_clinical_graph


def header(text, char="="):
    line = char * 78
    print(f"\n{line}\n  {text}\n{line}")


def subheader(text):
    print(f"\n--- {text} " + "-" * (74 - len(text)))


def _wrap(text, indent="    ", width=76):
    """Word-wrap text to fit in terminal."""
    words = text.split()
    lines = []
    line = indent
    for w in words:
        if len(line) + len(w) > width:
            lines.append(line)
            line = indent
        line += w + " "
    if line.strip():
        lines.append(line.rstrip())
    return lines


def run_pipeline(query, abnormal_names, top_k=5):
    """Run stages 2-3 of the RAG pipeline with a given query.

    Returns: (search_results, ranked_chunks, citations, timing_dict)
    """
    # Stage 2: Hybrid search
    t0 = time.time()
    search_results = hybrid_search(query, abnormal_names, top_k=15)
    t_search = time.time() - t0

    # Stage 3: Cross-encoder re-rank
    t0 = time.time()
    ranked = rerank(query, search_results, top_k=top_k)
    t_rerank = time.time() - t0

    # Stage 4: Citations
    citations = extract_citations(ranked)

    return search_results, ranked, citations, {"search": t_search, "rerank": t_rerank}


def run_scenario(name, biomarkers, medications=None, wearable_data=None, expected_keywords=None):
    """Run a single scenario, comparing fallback vs LLM query rewriting."""
    header(f"SCENARIO: {name}")

    # ── INPUT ──────────────────────────────────────────────────────────────
    print(f"\n  {len(biomarkers)} biomarkers:")
    for b in biomarkers:
        flag = ""
        if b.ref_low and b.value < b.ref_low:
            flag = f"  LOW (ref >= {b.ref_low})"
        elif b.ref_high and b.value > b.ref_high:
            flag = f"  HIGH (ref <= {b.ref_high})"
        print(f"    - {b.name:18} {b.value:>8} {b.unit:10}{flag}")
    if medications:
        print(f"  Medications: {', '.join(medications)}")
    if wearable_data:
        print(f"  Wearable: HR={wearable_data.get('resting_hr_avg')}bpm "
              f"trend={wearable_data.get('resting_hr_trend')}")

    # Run verification
    verified = verify_results(biomarkers, medications=medications)
    abnormal_names = [r.biomarker for r in verified.verified_results if r.flagged]

    # ── Generate both queries ──────────────────────────────────────────────
    print(f"\n{'='*78}")
    print(f"  QUERY COMPARISON")
    print(f"{'='*78}")

    # Fallback query
    t0 = time.time()
    fallback_query = _fallback_query(verified.verified_results)
    t_fallback = (time.time() - t0) * 1000

    print(f"\n  [FALLBACK] ({t_fallback:.1f}ms)")
    for line in _wrap(fallback_query):
        print(line)

    # LLM query
    t0 = time.time()
    llm_query = rewrite_query(
        verified.verified_results,
        medications=medications,
    )
    t_llm = (time.time() - t0) * 1000

    print(f"\n  [LLM — qwen3.5:0.8b] ({t_llm:.1f}ms)")
    for line in _wrap(llm_query):
        print(line)

    # ── Run pipeline with BOTH queries ─────────────────────────────────────
    print(f"\n{'='*78}")
    print(f"  RETRIEVAL RESULTS")
    print(f"{'='*78}")

    fb_search, fb_ranked, fb_citations, fb_time = run_pipeline(fallback_query, abnormal_names)
    llm_search, llm_ranked, llm_citations, llm_time = run_pipeline(llm_query, abnormal_names)

    # ── Side-by-side comparison ────────────────────────────────────────────
    print(f"\n  {'':30} {'FALLBACK':>22} {'LLM':>22}")
    print(f"  {'-'*74}")
    print(f"  {'Cross-encoder latency':30} {fb_time['rerank']*1000:>19.1f}ms {llm_time['rerank']*1000:>19.1f}ms")

    for i in range(5):
        fb_label = fb_ranked[i].get("section_title", "?")[:40] if i < len(fb_ranked) else "(none)"
        fb_score = fb_ranked[i].get("relevance_score", 0) if i < len(fb_ranked) else 0
        fb_conf = fb_ranked[i].get("confidence", "?") if i < len(fb_ranked) else "?"
        llm_label = llm_ranked[i].get("section_title", "?")[:40] if i < len(llm_ranked) else "(none)"
        llm_score = llm_ranked[i].get("relevance_score", 0) if i < len(llm_ranked) else 0
        llm_conf = llm_ranked[i].get("confidence", "?") if i < len(llm_ranked) else "?"
        diff = llm_score - fb_score
        marker = ">" if diff > 0.1 else ("<" if diff < -0.1 else "=")
        print(f"  #{i+1} {marker} "
              f"[{fb_conf[0].upper():1}{fb_score:+6.3f}] {fb_label:42} | "
              f"[{llm_conf[0].upper():1}{llm_score:+6.3f}] {llm_label:42}")

    # ── Confidence breakdown ───────────────────────────────────���──────────
    for label, ranked in [("FALLBACK", fb_ranked), ("LLM", llm_ranked)]:
        high = sum(1 for c in ranked if c.get("confidence") == "high")
        mod = sum(1 for c in ranked if c.get("confidence") == "moderate")
        low = sum(1 for c in ranked if c.get("confidence") == "low")
        top_score = ranked[0].get("relevance_score", -99) if ranked else -99
        print(f"\n  {label} — {high} high, {mod} moderate, {low} low | "
              f"Top score: {top_score:+.3f}")

    # ── Top citation comparison ────────────────────────────────────────────
    print(f"\n  TOP CITATION TEXT COMPARISON:")
    for label, ranked, citations in [("FALLBACK", fb_ranked, fb_citations),
                                      ("LLM", llm_ranked, llm_citations)]:
        if not citations:
            print(f"\n  {label}: No citations")
            continue
        top = citations[0]
        source = top.source.split(",")[0].strip() if top.source else "?"
        section = ranked[0].get("section_title", "?") if ranked else "?"
        print(f"\n  [{label}] {section}")
        print(f"    Source: {source}")
        print(f"    Score:  {top.relevance_score:+.3f}  "
              f"(confidence: {ranked[0].get('confidence', '?')})")
        # First 80 chars of text
        text_preview = top.text.replace("\n", " ").strip()[:200]
        print(f"    Text:   {text_preview}...")

    # ── Validation ─────────────────────────────────────────────────────────
    print(f"\n  VALIDATION:")
    if expected_keywords:
        for label, citations in [("FALLBACK", fb_citations), ("LLM", llm_citations)]:
            all_text = " ".join(c.text.lower() for c in citations)
            found = [kw for kw in expected_keywords if kw.lower() in all_text]
            missing = [kw for kw in expected_keywords if kw.lower() not in all_text]
            f_str = ", ".join(f"[+] {k}" for k in found) if found else "(none found)"
            m_str = ", ".join(f"[-] {k}" for k in missing) if missing else ""
            print(f"    {label:10} {f_str}  {m_str}")

    # ── Score delta ────────────────────────────────────────────────────────
    fb_top = fb_ranked[0].get("relevance_score", -99) if fb_ranked else -99
    llm_top = llm_ranked[0].get("relevance_score", -99) if llm_ranked else -99
    delta = llm_top - fb_top
    if delta > 0:
        print(f"\n  RESULT: LLM query improved top relevance by {delta:+.3f}")
    elif delta < 0:
        print(f"\n  RESULT: Fallback query was better by {abs(delta):.3f}")
    else:
        print(f"\n  RESULT: No difference in top relevance")

    return {
        "name": name,
        "fallback_top_score": fb_top,
        "llm_top_score": llm_top,
        "delta": delta,
    }


def main():
    header("VERITAS RAG Quality Test — Fallback vs LLM Query Rewriting")

    results = []

    # SCENARIO 1: Iron Deficiency
    results.append(run_scenario(
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
        expected_keywords=["microcytic", "iron", "ferritin", "anemia"],
    ))

    # SCENARIO 2: B12 Deficiency
    results.append(run_scenario(
        name="B12 Deficiency (Macrocytic Anemia)",
        biomarkers=[
            BiomarkerResult(name="Vitamin B12", value=180, unit="pg/mL",
                            ref_low=200, ref_high=900, flag="L"),
            BiomarkerResult(name="MCV", value=108, unit="fL",
                            ref_low=80, ref_high=100, flag="H"),
            BiomarkerResult(name="Hemoglobin", value=10.8, unit="g/dL",
                            ref_low=12, ref_high=16, flag="L"),
        ],
        expected_keywords=["macrocytic", "b12", "folate", "anemia"],
    ))

    # SCENARIO 3: Hypothyroidism
    results.append(run_scenario(
        name="Primary Hypothyroidism",
        biomarkers=[
            BiomarkerResult(name="TSH", value=12.5, unit="mIU/L",
                            ref_low=0.4, ref_high=4.0, flag="H"),
            BiomarkerResult(name="Free T4", value=0.6, unit="ng/dL",
                            ref_low=0.8, ref_high=1.8, flag="L"),
            BiomarkerResult(name="Cholesterol", value=265, unit="mg/dL",
                            ref_low=0, ref_high=200, flag="H"),
        ],
        expected_keywords=["thyroid", "hypothyroid", "tsh"],
    ))

    # SCENARIO 4: Kidney Dysfunction
    results.append(run_scenario(
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
        expected_keywords=["renal", "kidney", "creatinine"],
    ))

    # ── FINAL SUMMARY ──────────────────────────────────────────────────────
    header("SUMMARY: LLM vs Fallback Query Rewriting")
    print(f"\n  {'Scenario':35} {'Fallback':>8} {'LLM':>8} {'Delta':>8}")
    print(f"  {'-'*60}")
    for r in results:
        print(f"  {r['name']:35} {r['fallback_top_score']:>+8.3f} "
              f"{r['llm_top_score']:>+8.3f} {r['delta']:>+8.3f}")

    avg_delta = sum(r["delta"] for r in results) / len(results)
    print(f"\n  Average delta: {avg_delta:+.3f}")
    if avg_delta > 0:
        print(f"  LLM query rewriting improves cross-encoder relevance scores.")
    else:
        print(f"  Fallback query performs comparably or better.")
    print(f"\n  Note: Scores > 0 = high confidence, > -3 = moderate, < -3 = low")

    header("ALL SCENARIOS COMPLETE")


if __name__ == "__main__":
    main()
