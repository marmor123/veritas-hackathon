"""
Build the final clinical knowledge base — ONLY pattern-focused chapters.

This script:
1. Loads chunks from both PDF and HTML parsers
2. EXCLUDES non-clinical chapters (Laboratory Tests A-Z, Abbreviations, Toxicology, etc.)
3. Keeps ONLY clinical pattern chapters that relate multiple biomarkers
4. Splits large chunks, re-embeds, and builds LanceDB

The "Laboratory Tests" chapter is an A-Z encyclopedia of individual tests (reference ranges,
methodology, drug interferences). These are NOT clinical patterns. When the RAG query is
"low ferritin + low MCV," these test-reference chunks compete with the actual "Microcytic
Anemias" pattern chunk and pollute retrieval.

Clinical pattern chapters to KEEP:
  - Hematologic Disorders (iron deficiency, anemias, etc.)
  - Endocrine Diseases (thyroid, diabetes, etc.)
  - Cardiovascular Disorders (metabolic syndrome, dyslipidemia, etc.)
  - Renal Disorders (kidney disease, electrolyte imbalances)
  - Digestive Diseases (liver disease, GI disorders)
  - Respiratory, Metabolic, and Acid-Base Disorders
  - Gynecologic and Obstetric Disorders
  - Central Nervous System Disorders
  - Hereditary and Genetic Diseases
  - Genitourinary System Disorders

Chapters to EXCLUDE:
  - Laboratory Tests (A-Z test reference cards — not patterns)
  - Abbreviations and Acronyms
  - FALTs (Factors Affecting Laboratory Tests — useful for verification, not RAG)
  - Toxicology and Therapeutic Drug Monitoring
  - Transfusion Medicine
  - Infectious Disease Assays (methodology, not patterns)
  - Infectious Diseases (too broad, not blood-test focused)

Usage:
    python build_clinical_kb.py
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_wallach import detect_biomarkers, detect_organ_systems


# Chapters to EXCLUDE (non-clinical pattern content)
EXCLUDE_SOURCES = [
    "laboratory_tests",
    "laboratory tests",
    "abbreviations",
    "acronyms",
    "falts",
    "factors affecting",
    "toxicology",
    "therapeutic drug",
    "transfusion",
    "infectious disease assays",
    "infectious diseases",
]

# For PDF chunks: chapters to exclude by number
EXCLUDE_PDF_CHAPTERS = [
    "chapter2",   # Laboratory Tests (A-Z encyclopedia)
    "chapter3",   # Infectious Diseases Assays
    "chapter13",  # Infectious Diseases
    "chapter15",  # Toxicology
]


def should_exclude(chunk: dict) -> bool:
    """Check if a chunk should be excluded from the clinical KB."""
    source_name = chunk.get("chunk_id", "").lower()
    chapter = chunk.get("chapter", "").lower()
    section_title = chunk.get("section_title", "").lower()

    # Exclude by PDF chapter number
    if any(ch in chapter for ch in EXCLUDE_PDF_CHAPTERS):
        return True

    # Exclude by source name keywords
    for excl in EXCLUDE_SOURCES:
        if excl in source_name or excl in chapter:
            return True

    # Exclude chunks that look like single-test reference cards
    # (short title that's just a test name, no clinical context)
    if "normal range" in section_title and chunk.get("word_count", 0) < 100:
        return True

    return False


def is_clinical_pattern(chunk: dict) -> bool:
    """
    Check if a chunk describes a clinical pattern (relates multiple biomarkers).
    A good clinical chunk has:
    - Multiple biomarkers mentioned (>=2)
    - Clinical context keywords
    - Reasonable length (>=50 words)
    """
    biomarkers = chunk.get("biomarkers_mentioned", [])
    text = chunk.get("text", "").lower()
    word_count = chunk.get("word_count", 0)

    # Must have at least 50 words
    if word_count < 50:
        return False

    # Strong signal: multiple biomarkers
    if len(biomarkers) >= 2:
        return True

    # Clinical pattern keywords
    pattern_keywords = [
        "anemia", "deficiency", "syndrome", "disorder", "disease",
        "increased in", "decreased in", "laboratory findings",
        "differential diagnosis", "who should be suspected",
        "clinical significance", "interpretation",
        "causes", "associated with", "pattern",
    ]
    if any(kw in text for kw in pattern_keywords):
        return True

    return False


def split_large_chunk(chunk: dict, max_words: int = 450) -> list[dict]:
    """Split a chunk that's too large into smaller pieces."""
    text = chunk["text"]
    words = text.split()

    if len(words) <= max_words:
        return [chunk]

    # Split by sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = []
    current = []
    current_words = 0
    sub_idx = 0

    for sent in sentences:
        sent_words = len(sent.split())
        if current_words + sent_words > max_words and current:
            merged = ' '.join(current)
            if len(merged.split()) >= 30:
                new_chunk = dict(chunk)
                new_chunk["text"] = merged
                new_chunk["word_count"] = len(merged.split())
                new_chunk["chunk_id"] = f"{chunk['chunk_id']}_p{sub_idx}"
                new_chunk["biomarkers_mentioned"] = detect_biomarkers(merged)
                new_chunk["organ_system"] = detect_organ_systems(merged)
                result.append(new_chunk)
                sub_idx += 1
            current = [sent]
            current_words = sent_words
        else:
            current.append(sent)
            current_words += sent_words

    # Flush remaining
    if current:
        merged = ' '.join(current)
        if len(merged.split()) >= 30:
            new_chunk = dict(chunk)
            new_chunk["text"] = merged
            new_chunk["word_count"] = len(merged.split())
            if sub_idx > 0:
                new_chunk["chunk_id"] = f"{chunk['chunk_id']}_p{sub_idx}"
                new_chunk["biomarkers_mentioned"] = detect_biomarkers(merged)
                new_chunk["organ_system"] = detect_organ_systems(merged)
            result.append(new_chunk)

    return result if result else [chunk]


def main():
    kb_dir = Path(__file__).parent

    # Load all available chunks
    all_chunks = []

    # Load HTML chunks (11th Edition — preferred)
    html_path = kb_dir / "chunks_html.json"
    if html_path.exists():
        html_chunks = json.load(open(html_path, "r", encoding="utf-8"))
        print(f"Loaded {len(html_chunks)} HTML chunks (11th Edition)")
        all_chunks.extend(html_chunks)

    # Load PDF chunks (9th Edition — fallback)
    # Try the dedicated PDF file first, then the main chunks.json
    pdf_path = kb_dir / "chunks_pdf.json"
    if not pdf_path.exists():
        # Check if current chunks.json has PDF chunks
        main_path = kb_dir / "chunks.json"
        if main_path.exists():
            main_chunks = json.load(open(main_path, "r", encoding="utf-8"))
            pdf_chunks = [c for c in main_chunks if "9th" in c.get("source", "")]
            if pdf_chunks:
                print(f"Loaded {len(pdf_chunks)} PDF chunks from chunks.json (9th Edition)")
                all_chunks.extend(pdf_chunks)
    else:
        pdf_chunks = json.load(open(pdf_path, "r", encoding="utf-8"))
        print(f"Loaded {len(pdf_chunks)} PDF chunks (9th Edition)")
        all_chunks.extend(pdf_chunks)

    if not all_chunks:
        print("ERROR: No chunks found. Run the parsers first.")
        sys.exit(1)

    print(f"\nTotal chunks loaded: {len(all_chunks)}")

    # Step 1: Exclude non-clinical chapters
    clinical = [c for c in all_chunks if not should_exclude(c)]
    excluded_count = len(all_chunks) - len(clinical)
    print(f"After excluding non-clinical chapters: {len(clinical)} (removed {excluded_count})")

    # Step 2: Filter for clinical pattern relevance
    patterns = [c for c in clinical if is_clinical_pattern(c)]
    print(f"After filtering for clinical patterns: {len(patterns)}")

    # Step 3: Split large chunks
    final = []
    for chunk in patterns:
        final.extend(split_large_chunk(chunk, max_words=450))
    print(f"After splitting large chunks: {len(final)}")

    # Step 4: Deduplicate by text similarity (simple: exact chunk_id dedup)
    seen_ids = set()
    deduped = []
    for chunk in final:
        cid = chunk.get("chunk_id", "")
        if cid not in seen_ids:
            seen_ids.add(cid)
            deduped.append(chunk)
    print(f"After deduplication: {len(deduped)}")

    # Write output
    output_path = kb_dir / "chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)

    # Stats
    print(f"\n{'=' * 60}")
    print(f"CLINICAL KNOWLEDGE BASE BUILT")
    print(f"{'=' * 60}")
    print(f"  Final chunks: {len(deduped)}")
    print(f"  Output: {output_path}")

    wc = [c["word_count"] for c in deduped]
    print(f"\n  Chunk sizes: min={min(wc)}, max={max(wc)}, avg={sum(wc)//len(wc)}")
    print(f"  Total words: {sum(wc):,}")

    all_bm = set()
    for c in deduped:
        all_bm.update(c.get("biomarkers_mentioned", []))
    print(f"  Unique biomarkers: {len(all_bm)}")

    systems = {}
    for c in deduped:
        for s in c.get("organ_system", []):
            systems[s] = systems.get(s, 0) + 1
    print(f"\n  Organ systems:")
    for s, count in sorted(systems.items(), key=lambda x: -x[1]):
        print(f"    {s}: {count}")

    # Source breakdown
    html_count = len([c for c in deduped if "11th" in c.get("source", "")])
    pdf_count = len([c for c in deduped if "9th" in c.get("source", "")])
    print(f"\n  Sources: {html_count} from HTML (11th), {pdf_count} from PDF (9th)")
    print(f"{'=' * 60}")
    print(f"\n  Next: python build_kb.py  (to embed and build LanceDB)")


if __name__ == "__main__":
    main()
