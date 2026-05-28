"""
Merge knowledge from multiple sources (PDF + HTML) into the best possible knowledge base.

This script:
1. Loads chunks from the PDF parser (parse_wallach_pdf.py → chunks.json)
2. Loads chunks from the HTML parser (parse_wallach.py → html_chunks.json)
3. Compares quality metrics (biomarker coverage, word count, clinical relevance)
4. Merges the best chunks from both sources, deduplicating by content similarity
5. Outputs the final merged chunks.json and rebuilds the LanceDB

Usage:
    # First, generate both chunk sources:
    python parse_wallach_pdf.py                          # → chunks_pdf.json
    python parse_wallach.py raw/chapter2.html ...        # → chunks_html.json (rename output)

    # Then merge:
    python merge_sources.py
    python merge_sources.py --pdf-chunks chunks_pdf.json --html-chunks chunks_html.json
    python merge_sources.py --prefer html   # prefer HTML when duplicates found
    python merge_sources.py --prefer pdf    # prefer PDF when duplicates found

The HTML source (11th Edition from lwwhealthlibrary.com) is generally BETTER because:
- It's the newer edition (11th vs 9th)
- HTML structure gives cleaner section boundaries
- Content is more up-to-date with current clinical guidelines
- The parser was specifically designed for that platform's structure

The PDF source (9th Edition) is useful as:
- A fallback when HTML chapters aren't available
- Additional coverage for chapters not yet copied from the website
- Cross-reference validation
"""

import json
import re
import sys
import argparse
from pathlib import Path
from difflib import SequenceMatcher


def load_chunks(filepath: Path) -> list[dict]:
    """Load chunks from a JSON file."""
    if not filepath.exists():
        print(f"  Warning: {filepath} not found")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"  Loaded {len(chunks)} chunks from {filepath.name}")
    return chunks


def compute_similarity(text_a: str, text_b: str) -> float:
    """Compute text similarity ratio between two chunks."""
    # Use first 200 chars for speed
    a = text_a[:200].lower()
    b = text_b[:200].lower()
    return SequenceMatcher(None, a, b).ratio()


def compute_quality_score(chunk: dict) -> float:
    """
    Score a chunk's quality for RAG retrieval.
    Higher = better for our use case.
    """
    score = 0.0

    # Biomarker coverage (most important)
    biomarkers = chunk.get("biomarkers_mentioned", [])
    score += len(biomarkers) * 3.0

    # Word count (sweet spot: 100-400 words)
    wc = chunk.get("word_count", 0)
    if 100 <= wc <= 400:
        score += 5.0
    elif 50 <= wc <= 500:
        score += 3.0
    elif wc > 500:
        score += 1.0  # Too long, less focused

    # Clinical relevance keywords
    text = chunk.get("text", "").lower()
    clinical_keywords = [
        "increased in", "decreased in", "elevated", "reduced",
        "diagnosis", "interpretation", "clinical significance",
        "causes", "associated with", "differential",
        "normal range", "reference range",
    ]
    for kw in clinical_keywords:
        if kw in text:
            score += 1.0

    # Organ system specificity (more specific = better)
    systems = chunk.get("organ_system", [])
    if 1 <= len(systems) <= 2:
        score += 2.0  # Focused
    elif len(systems) > 4:
        score -= 1.0  # Too broad

    # Has a clear section title
    title = chunk.get("section_title", "")
    if title and len(title) > 5:
        score += 1.0

    return score


def find_duplicates(chunks_a: list[dict], chunks_b: list[dict],
                    similarity_threshold: float = 0.6) -> list[tuple[int, int, float]]:
    """
    Find duplicate/overlapping chunks between two sources.
    Returns list of (idx_a, idx_b, similarity_score) tuples.
    """
    duplicates = []

    for i, chunk_a in enumerate(chunks_a):
        title_a = chunk_a.get("section_title", "").lower()
        biomarkers_a = set(chunk_a.get("biomarkers_mentioned", []))

        for j, chunk_b in enumerate(chunks_b):
            # Quick filter: must share at least one biomarker or similar title
            title_b = chunk_b.get("section_title", "").lower()
            biomarkers_b = set(chunk_b.get("biomarkers_mentioned", []))

            # Title similarity check (fast)
            title_sim = SequenceMatcher(None, title_a, title_b).ratio()
            biomarker_overlap = len(biomarkers_a & biomarkers_b)

            if title_sim < 0.4 and biomarker_overlap < 2:
                continue  # Skip — clearly different topics

            # Full text similarity (slower, only for candidates)
            sim = compute_similarity(chunk_a.get("text", ""), chunk_b.get("text", ""))
            if sim >= similarity_threshold:
                duplicates.append((i, j, sim))

    return duplicates


def merge_chunks(
    pdf_chunks: list[dict],
    html_chunks: list[dict],
    prefer: str = "html",
    similarity_threshold: float = 0.5,
) -> list[dict]:
    """
    Merge chunks from PDF and HTML sources.

    Strategy:
    - For duplicates: keep the preferred source (or the higher-quality one)
    - For unique chunks: keep all of them
    - Normalize chunk_ids to avoid collisions
    """
    print(f"\n  Finding duplicates (threshold: {similarity_threshold})...")
    duplicates = find_duplicates(pdf_chunks, html_chunks, similarity_threshold)
    print(f"  Found {len(duplicates)} potential duplicates")

    # Track which chunks are duplicated
    pdf_duplicated = set()
    html_duplicated = set()
    kept_from_preferred = 0
    kept_from_quality = 0

    for idx_pdf, idx_html, sim in duplicates:
        pdf_duplicated.add(idx_pdf)
        html_duplicated.add(idx_html)

    # For duplicates: choose the better version
    merged = []
    processed_pdf = set()
    processed_html = set()

    for idx_pdf, idx_html, sim in duplicates:
        if idx_pdf in processed_pdf or idx_html in processed_html:
            continue

        pdf_chunk = pdf_chunks[idx_pdf]
        html_chunk = html_chunks[idx_html]

        pdf_score = compute_quality_score(pdf_chunk)
        html_score = compute_quality_score(html_chunk)

        if prefer == "html":
            chosen = html_chunk if html_score >= pdf_score * 0.8 else pdf_chunk
        elif prefer == "pdf":
            chosen = pdf_chunk if pdf_score >= html_score * 0.8 else html_chunk
        else:  # "quality"
            chosen = html_chunk if html_score >= pdf_score else pdf_chunk

        if chosen == html_chunk:
            kept_from_preferred += 1
        else:
            kept_from_quality += 1

        merged.append(chosen)
        processed_pdf.add(idx_pdf)
        processed_html.add(idx_html)

    # Add unique PDF chunks (not duplicated)
    for i, chunk in enumerate(pdf_chunks):
        if i not in pdf_duplicated:
            merged.append(chunk)

    # Add unique HTML chunks (not duplicated)
    for i, chunk in enumerate(html_chunks):
        if i not in html_duplicated:
            merged.append(chunk)

    print(f"  Duplicates resolved: {kept_from_preferred} from preferred, "
          f"{kept_from_quality} from quality override")
    print(f"  Unique PDF chunks added: {len(pdf_chunks) - len(pdf_duplicated)}")
    print(f"  Unique HTML chunks added: {len(html_chunks) - len(html_duplicated)}")

    # Re-assign chunk_ids to avoid collisions
    for i, chunk in enumerate(merged):
        if not chunk.get("chunk_id", "").startswith("merged_"):
            # Keep original ID but prefix with source
            original_id = chunk.get("chunk_id", f"chunk_{i}")
            source_prefix = "html" if "11th" in chunk.get("source", "") else "pdf"
            chunk["chunk_id"] = f"{source_prefix}_{original_id}"

    return merged


def print_comparison(pdf_chunks: list[dict], html_chunks: list[dict]):
    """Print a quality comparison between the two sources."""
    print("\n" + "=" * 70)
    print("SOURCE COMPARISON")
    print("=" * 70)

    def stats(chunks, name):
        if not chunks:
            print(f"\n  {name}: NO DATA")
            return
        word_counts = [c["word_count"] for c in chunks]
        biomarker_counts = [len(c.get("biomarkers_mentioned", [])) for c in chunks]
        all_biomarkers = set()
        for c in chunks:
            all_biomarkers.update(c.get("biomarkers_mentioned", []))
        systems = {}
        for c in chunks:
            for s in c.get("organ_system", []):
                systems[s] = systems.get(s, 0) + 1

        print(f"\n  {name}:")
        print(f"    Chunks: {len(chunks)}")
        print(f"    Total words: {sum(word_counts):,}")
        print(f"    Avg words/chunk: {sum(word_counts)/len(chunks):.0f}")
        print(f"    Avg biomarkers/chunk: {sum(biomarker_counts)/len(chunks):.1f}")
        print(f"    Unique biomarkers: {len(all_biomarkers)}")
        print(f"    Organ systems: {len(systems)}")
        print(f"    Top systems: {', '.join(f'{k}({v})' for k, v in sorted(systems.items(), key=lambda x: -x[1])[:5])}")

        # Quality score distribution
        scores = [compute_quality_score(c) for c in chunks]
        print(f"    Quality scores: min={min(scores):.1f}, avg={sum(scores)/len(scores):.1f}, max={max(scores):.1f}")

    stats(pdf_chunks, "PDF (9th Edition)")
    stats(html_chunks, "HTML (11th Edition)")
    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Merge PDF and HTML knowledge sources")
    parser.add_argument("--pdf-chunks", type=str, default=None,
                        help="Path to PDF-parsed chunks (default: chunks.json)")
    parser.add_argument("--html-chunks", type=str, default=None,
                        help="Path to HTML-parsed chunks (default: chunks_html.json)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output path (default: chunks.json)")
    parser.add_argument("--prefer", choices=["html", "pdf", "quality"], default="html",
                        help="Which source to prefer for duplicates (default: html)")
    parser.add_argument("--compare-only", action="store_true",
                        help="Only compare sources, don't merge")
    args = parser.parse_args()

    kb_dir = Path(__file__).parent

    # Load PDF chunks
    pdf_path = Path(args.pdf_chunks) if args.pdf_chunks else kb_dir / "chunks.json"
    print("Loading PDF chunks...")
    pdf_chunks = load_chunks(pdf_path)

    # Load HTML chunks
    html_path = Path(args.html_chunks) if args.html_chunks else kb_dir / "chunks_html.json"
    print("Loading HTML chunks...")
    html_chunks = load_chunks(html_path)

    if not pdf_chunks and not html_chunks:
        print("\nERROR: No chunks found from either source.")
        print("Run parse_wallach_pdf.py and/or parse_wallach.py first.")
        sys.exit(1)

    # Compare
    print_comparison(pdf_chunks, html_chunks)

    if args.compare_only:
        return

    # If only one source available, use it directly
    if not html_chunks:
        print("\nNo HTML chunks available. Using PDF chunks only.")
        merged = pdf_chunks
    elif not pdf_chunks:
        print("\nNo PDF chunks available. Using HTML chunks only.")
        merged = html_chunks
    else:
        # Merge
        print(f"\nMerging sources (prefer: {args.prefer})...")
        merged = merge_chunks(pdf_chunks, html_chunks, prefer=args.prefer)

    # Write output
    output_path = Path(args.output) if args.output else kb_dir / "chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"MERGE COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Final chunks: {len(merged)}")
    print(f"  Output: {output_path}")
    print(f"\n  Next step: python build_kb.py")
    print(f"  This will re-embed all chunks and rebuild the LanceDB.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
