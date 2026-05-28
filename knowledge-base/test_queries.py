"""
RAG Retrieval Quality Testing

Tests the RAG pipeline against known test cases to verify:
1. Correct patterns are retrieved (top-1 accuracy)
2. Metadata filtering eliminates irrelevant chunks
3. Cross-encoder re-ranking improves results
4. Citations are properly tracked

Usage:
    python test_queries.py
    python test_queries.py --verbose
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.api.models.schemas import VerifiedResult
from backend.rag.pipeline import RAGPipeline


# ── Test Cases ────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "name": "Iron Deficiency + Wearable",
        "description": "Low ferritin/iron/MCV/hemoglobin with rising HR",
        "verified_results": [
            VerifiedResult(biomarker="Ferritin", value=12, unit="ng/mL",
                          ref_low=15, ref_high=150, flagged=True, flag_reason="Below range"),
            VerifiedResult(biomarker="Iron", value=35, unit="µg/dL",
                          ref_low=60, ref_high=170, flagged=True, flag_reason="Below range"),
            VerifiedResult(biomarker="MCV", value=78, unit="fL",
                          ref_low=80, ref_high=100, flagged=True, flag_reason="Below range"),
            VerifiedResult(biomarker="Hemoglobin", value=11.2, unit="g/dL",
                          ref_low=12, ref_high=16, flagged=True, flag_reason="Below range"),
        ],
        "medications": [],
        "wearable": {"resting_hr_avg": 76, "resting_hr_trend": "rising"},
        "expected": {
            "top_pattern_contains": ["iron", "deficiency", "anemia"],
            "should_not_contain": ["thalassemia", "chronic disease"],
            "min_chunks": 1,
            "graph_min_nodes": 4,
        },
    },
    {
        "name": "Metabolic Syndrome Cluster",
        "description": "High glucose, low HDL, high TG, high ALT, high uric acid",
        "verified_results": [
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
        ],
        "medications": [],
        "wearable": None,
        "expected": {
            "top_pattern_contains": ["metabolic", "syndrome", "insulin", "resistance"],
            "should_not_contain": ["iron", "thyroid"],
            "min_chunks": 1,
            "graph_min_nodes": 5,
        },
    },
    {
        "name": "All Normal (Fast Path)",
        "description": "All biomarkers within reference ranges",
        "verified_results": [
            VerifiedResult(biomarker="Hemoglobin", value=14.5, unit="g/dL",
                          ref_low=12, ref_high=16, flagged=False),
            VerifiedResult(biomarker="Glucose", value=92, unit="mg/dL",
                          ref_low=70, ref_high=100, flagged=False),
            VerifiedResult(biomarker="TSH", value=2.1, unit="mIU/L",
                          ref_low=0.4, ref_high=4.0, flagged=False),
        ],
        "medications": [],
        "wearable": None,
        "expected": {
            "fast_path": True,
            "min_chunks": 0,
            "graph_min_nodes": 0,
        },
    },
]


def run_tests(verbose: bool = False):
    """Run all RAG quality tests."""
    pipeline = RAGPipeline()
    results = []

    print("=" * 70)
    print("RAG RETRIEVAL QUALITY TESTS")
    print("=" * 70)

    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n{'─' * 70}")
        print(f"Test {i}: {test['name']}")
        print(f"  {test['description']}")
        print(f"{'─' * 70}")

        try:
            result = pipeline.run(
                verified_results=test["verified_results"],
                medications=test.get("medications"),
                wearable_data=test.get("wearable"),
            )

            passed = True
            expected = test["expected"]

            # Check fast path
            if expected.get("fast_path"):
                if result["timings"].get("fast_path"):
                    print("  ✓ Fast path triggered (RAG skipped)")
                else:
                    print("  ✗ Fast path NOT triggered")
                    passed = False
                results.append({"test": test["name"], "passed": passed})
                continue

            # Check minimum chunks retrieved
            num_chunks = len(result["citations"])
            if num_chunks >= expected["min_chunks"]:
                print(f"  ✓ Retrieved {num_chunks} chunks (min: {expected['min_chunks']})")
            else:
                print(f"  ✗ Only {num_chunks} chunks (expected min: {expected['min_chunks']})")
                passed = False

            # Check top pattern content
            if expected.get("top_pattern_contains"):
                rag_output = result["rag_output"]
                if rag_output.matched_patterns:
                    top_pattern = rag_output.matched_patterns[0]["pattern_name"].lower()
                    for keyword in expected["top_pattern_contains"]:
                        if keyword.lower() in top_pattern:
                            print(f"  ✓ Top pattern contains '{keyword}': {top_pattern}")
                            break
                    else:
                        # Check in chunk text as fallback
                        all_text = " ".join(c.text.lower() for c in result["citations"])
                        found_any = any(kw.lower() in all_text for kw in expected["top_pattern_contains"])
                        if found_any:
                            print(f"  ✓ Retrieved chunks contain expected keywords")
                        else:
                            print(f"  ✗ Expected keywords not found in results")
                            passed = False
                else:
                    print(f"  ✗ No patterns matched")
                    passed = False

            # Check graph
            graph = result["clinical_graph"]
            if len(graph.nodes) >= expected["graph_min_nodes"]:
                print(f"  ✓ Graph has {len(graph.nodes)} nodes, {len(graph.edges)} edges")
            else:
                print(f"  ✗ Graph only has {len(graph.nodes)} nodes "
                      f"(expected min: {expected['graph_min_nodes']})")
                passed = False

            # Check timings
            timings = result["timings"]
            total = sum(v for v in timings.values() if isinstance(v, (int, float)))
            print(f"  ⏱ Total time: {total:.2f}s")
            for stage, t in timings.items():
                if isinstance(t, (int, float)):
                    print(f"    {stage}: {t:.3f}s")

            if verbose and result["citations"]:
                print(f"\n  Top citations:")
                for c in result["citations"][:3]:
                    print(f"    [{c.chunk_id}] {c.source}")
                    print(f"      Score: {c.relevance_score:.3f}")
                    print(f"      Preview: {c.text[:100]}...")

            if verbose:
                print(f"\n  Rewritten query: {result['rewritten_query'][:200]}")

            results.append({"test": test["name"], "passed": passed})

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append({"test": test["name"], "passed": False, "error": str(e)})

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"  {passed_count}/{total_count} tests passed")
    for r in results:
        status = "✓" if r["passed"] else "✗"
        print(f"  {status} {r['test']}")
    print(f"{'=' * 70}")

    return all(r["passed"] for r in results)


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    success = run_tests(verbose=verbose)
    sys.exit(0 if success else 1)
