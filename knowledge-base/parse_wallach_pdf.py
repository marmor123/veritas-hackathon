"""
Parse Wallach's Interpretation of Diagnostic Tests (9th Edition PDF) into
embeddable chunks for LanceDB.

Input: The PDF file in knowledge-base/
Output: chunks.json — [{chunk_id, source, chapter, section_title, text, organ_system, biomarkers_mentioned, word_count}]

Usage:
    python parse_wallach_pdf.py
    python parse_wallach_pdf.py --chapters 2 10 7
    python parse_wallach_pdf.py --all

The parser extracts clinical content organized by:
- Chapter 2: Laboratory Tests (individual biomarker descriptions)
- Chapter 4: Cardiovascular Disorders
- Chapter 6: Digestive Diseases
- Chapter 7: Endocrine Diseases
- Chapter 8: Renal & Urinary Tract Diseases
- Chapter 10: Hematologic Disorders
- Chapter 14: Respiratory, Metabolic & Acid-Base Disorders
"""

import re
import json
import sys
import argparse
from pathlib import Path

import fitz  # PyMuPDF


# ── Chapter page ranges from TOC ─────────────────────────────────────────

CHAPTERS = {
    1: {"title": "Introduction to Laboratory Medicine", "start": 20, "end": 34},
    2: {"title": "Laboratory Tests", "start": 35, "end": 498},
    3: {"title": "Infectious Diseases Assays", "start": 499, "end": 703},
    4: {"title": "Cardiovascular Disorders", "start": 704, "end": 779},
    5: {"title": "Central Nervous System Disorders", "start": 780, "end": 859},
    6: {"title": "Digestive Diseases", "start": 860, "end": 964},
    7: {"title": "Endocrine Diseases", "start": 965, "end": 1031},
    8: {"title": "Renal & Urinary Tract Diseases", "start": 1032, "end": 1111},
    9: {"title": "Gynecologic & Obstetric Disorders", "start": 1112, "end": 1137},
    10: {"title": "Hematologic Disorders", "start": 1138, "end": 1261},
    11: {"title": "Hereditary & Genetic Diseases", "start": 1262, "end": 1328},
    12: {"title": "Immune & Autoimmune Diseases", "start": 1329, "end": 1348},
    13: {"title": "Infectious Diseases", "start": 1349, "end": 1513},
    14: {"title": "Respiratory, Metabolic & Acid-Base Disorders", "start": 1514, "end": 1578},
    15: {"title": "Toxicology & Therapeutic Drug Monitoring", "start": 1579, "end": 1606},
}

# Chapters most relevant for our RAG (clinical patterns + biomarker descriptions)
PRIORITY_CHAPTERS = [2, 4, 6, 7, 8, 10, 14]


# ── Organ system → biomarker mapping ─────────────────────────────────────

ORGAN_SYSTEM_MAP = {
    "hematologic": [
        "hemoglobin", "hgb", "hct", "hematocrit", "rbc", "mcv", "mch", "mchc",
        "rdw", "ferritin", "iron", "tibc", "transferrin", "transferrin saturation",
        "b12", "folate", "platelets", "wbc", "neutrophils", "lymphocytes",
        "monocytes", "eosinophils", "basophils", "esr", "crp", "reticulocyte",
        "haptoglobin", "ldh", "fibrinogen", "pt", "ptt", "inr", "d-dimer",
        "anemia", "hemolysis", "polycythemia", "pancytopenia",
    ],
    "hepatic": [
        "alt", "ast", "ggt", "alp", "alkaline phosphatase", "bilirubin",
        "total bilirubin", "direct bilirubin", "indirect bilirubin",
        "albumin", "total protein", "ammonia", "bile acids",
        "liver", "hepatic", "cirrhosis", "hepatitis",
    ],
    "renal": [
        "creatinine", "bun", "egfr", "gfr", "cystatin c", "uric acid",
        "urine", "microalbumin", "creatinine clearance",
        "kidney", "renal", "nephrotic",
    ],
    "thyroid": [
        "tsh", "t3", "t4", "ft3", "ft4", "free t3", "free t4",
        "thyroglobulin", "thyroid", "tpo",
    ],
    "cardiometabolic": [
        "glucose", "hba1c", "a1c", "insulin", "c-peptide", "cholesterol",
        "total cholesterol", "ldl", "hdl", "triglycerides",
        "diabetes", "metabolic syndrome", "insulin resistance", "dyslipidemia",
    ],
    "electrolyte": [
        "sodium", "potassium", "chloride", "co2", "bicarbonate",
        "anion gap", "calcium", "magnesium", "phosphorus", "phosphate",
    ],
    "endocrine": [
        "cortisol", "acth", "aldosterone", "renin", "dhea",
        "testosterone", "estradiol", "progesterone",
        "lh", "fsh", "prolactin", "pth", "vitamin d",
    ],
    "cardiac": [
        "troponin", "ck", "ck-mb", "bnp", "nt-probnp", "myoglobin",
        "cardiac", "heart", "myocardial",
    ],
    "nutritional": [
        "vitamin b12", "folate", "vitamin d", "25-oh vitamin d",
        "zinc", "selenium", "copper", "iron", "ferritin",
    ],
}

BIOMARKER_NAMES = set()
for names in ORGAN_SYSTEM_MAP.values():
    for name in names:
        BIOMARKER_NAMES.add(name.lower().strip())


# ── Section detection patterns ────────────────────────────────────────────

# The book uses ➤ (or similar arrow chars) to mark subsections
SECTION_MARKER = re.compile(r'[➤►▶\u27A4&U27A4;]?\s*(Definition|Interpretation|Use|Limitations|'
                            r'Normal Range|Normal Values|Causes|Clinical|Diagnosis|'
                            r'Laboratory Findings|Suggested Reading|Other Considerations)',
                            re.IGNORECASE)

# Detect major section headings (all caps or title case on their own line)
HEADING_PATTERN = re.compile(r'^([A-Z][A-Z\s,&\-/()]+)$')

# Detect test name headings in Chapter 2 (e.g., "FERRITIN", "GLUCOSE")
TEST_NAME_PATTERN = re.compile(r'^([A-Z][A-Z\s,\-/()0-9α-ωΑ-Ω]+)$')


def extract_chapter_text(doc, chapter_num: int) -> str:
    """Extract all text from a chapter's page range."""
    if chapter_num not in CHAPTERS:
        return ""
    ch = CHAPTERS[chapter_num]
    pages_text = []
    for page_idx in range(ch["start"] - 1, min(ch["end"], doc.page_count)):
        page = doc[page_idx]
        text = page.get_text()
        # Clean up common PDF artifacts
        text = text.replace('\x00', '')
        # Remove page number artifacts (standalone P or P.xxx lines)
        text = re.sub(r'^P\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^P\.?\d+\s*$', '', text, flags=re.MULTILINE)
        pages_text.append(text)
    return "\n".join(pages_text)


def chunk_chapter_2(text: str) -> list[dict]:
    """
    Parse Chapter 2 (Laboratory Tests) — organized alphabetically by test name.
    Each test has: Definition, Use, Interpretation (Increased In / Decreased In), Limitations.
    """
    chunks = []
    lines = text.split('\n')

    current_test = None
    current_content = []
    current_subsection = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect test name headings (all caps, standalone)
        if TEST_NAME_PATTERN.match(stripped) and len(stripped) > 3 and len(stripped) < 80:
            # Check it's not a subsection marker
            if not SECTION_MARKER.match(stripped):
                # Flush previous test
                if current_test and current_content:
                    chunks.append({
                        "section_title": current_test,
                        "subsection": current_subsection,
                        "text": "\n".join(current_content),
                    })
                current_test = stripped.title()
                current_content = []
                current_subsection = None
                continue

        # Detect subsection markers
        marker_match = SECTION_MARKER.match(stripped)
        if marker_match:
            current_subsection = marker_match.group(1).strip()

        if current_test:
            current_content.append(stripped)

    # Flush last test
    if current_test and current_content:
        chunks.append({
            "section_title": current_test,
            "subsection": current_subsection,
            "text": "\n".join(current_content),
        })

    return chunks


def chunk_clinical_chapter(text: str, chapter_title: str) -> list[dict]:
    """
    Parse clinical chapters (4, 6, 7, 8, 10, 14) — organized by disease/condition.
    Uses heading detection to split into sections.
    """
    chunks = []
    lines = text.split('\n')

    current_section = None
    current_subsection = None
    current_content = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect major headings (all caps, reasonable length)
        if HEADING_PATTERN.match(stripped) and 4 < len(stripped) < 100:
            # Skip common non-section headers
            skip_words = ["CHAPTER", "TABLE", "FIGURE", "PAGE", "REFERENCE",
                         "SUGGESTED READING", "BIBLIOGRAPHY"]
            if any(sw in stripped.upper() for sw in skip_words):
                current_content.append(stripped)
                continue

            # Flush previous section
            if current_section and current_content:
                chunks.append({
                    "section_title": current_section,
                    "subsection": current_subsection,
                    "text": "\n".join(current_content),
                })

            current_section = stripped.title()
            current_subsection = None
            current_content = []
            continue

        # Detect subsection markers
        marker_match = SECTION_MARKER.match(stripped)
        if marker_match:
            # If we have accumulated content, this might be a new sub-chunk
            if current_section and len(current_content) > 20:
                chunks.append({
                    "section_title": current_section,
                    "subsection": current_subsection,
                    "text": "\n".join(current_content),
                })
                current_content = []
            current_subsection = marker_match.group(1).strip()

        if current_section:
            current_content.append(stripped)
        elif stripped and len(stripped) > 20:
            # Content before first heading — use chapter title
            if not current_section:
                current_section = chapter_title
            current_content.append(stripped)

    # Flush last section
    if current_section and current_content:
        chunks.append({
            "section_title": current_section,
            "subsection": current_subsection,
            "text": "\n".join(current_content),
        })

    return chunks


def detect_biomarkers(text: str) -> list[str]:
    """Find biomarker names mentioned in text."""
    text_lower = text.lower()
    found = []
    for bm in sorted(BIOMARKER_NAMES, key=len, reverse=True):
        if bm in text_lower:
            found.append(bm)
    return list(set(found))


def detect_organ_systems(text: str) -> list[str]:
    """Return list of organ systems whose biomarkers/keywords appear in text."""
    text_lower = text.lower()
    systems = []
    for system, keywords in ORGAN_SYSTEM_MAP.items():
        if any(kw in text_lower for kw in keywords):
            systems.append(system)
    return systems if systems else ["general"]


def process_chunk(raw_chunk: dict, chapter_num: int, chunk_idx: int) -> dict:
    """Convert a raw chunk to the final LanceDB-ready format."""
    title = raw_chunk["section_title"]
    subsection = raw_chunk.get("subsection", "")
    full_title = f"{title} — {subsection}" if subsection else title
    text = raw_chunk["text"]

    biomarkers = detect_biomarkers(text)
    organ_systems = detect_organ_systems(text)

    # Also classify by chapter
    chapter_system_map = {
        4: "cardiac",
        6: "hepatic",
        7: "endocrine",
        8: "renal",
        10: "hematologic",
        14: "cardiometabolic",
    }
    if chapter_num in chapter_system_map:
        ch_system = chapter_system_map[chapter_num]
        if ch_system not in organ_systems:
            organ_systems.append(ch_system)

    return {
        "chunk_id": f"wallach_ch{chapter_num:02d}_s{chunk_idx:03d}",
        "source": "Wallach's Interpretation of Diagnostic Tests, 9th Edition",
        "chapter": f"chapter{chapter_num}",
        "section_title": full_title,
        "text": text,
        "organ_system": organ_systems,
        "biomarkers_mentioned": biomarkers,
        "word_count": len(text.split()),
    }


def split_large_chunks(chunks: list[dict], max_words: int = 500) -> list[dict]:
    """Split chunks that are too large into smaller pieces."""
    result = []
    for chunk in chunks:
        words = chunk["text"].split()
        if len(words) <= max_words:
            result.append(chunk)
        else:
            # Try splitting by double newline first, then single newline
            paragraphs = chunk["text"].split("\n\n")
            if len(paragraphs) <= 1:
                # No double newlines — split by single newlines
                paragraphs = chunk["text"].split("\n")

            current_text = []
            current_word_count = 0
            sub_idx = 0
            separator = "\n\n" if "\n\n" in chunk["text"] else "\n"

            for para in paragraphs:
                para_words = len(para.split())
                if current_word_count + para_words > max_words and current_text:
                    # Flush current sub-chunk
                    sub_chunk = dict(chunk)
                    sub_chunk["text"] = separator.join(current_text)
                    sub_chunk["word_count"] = current_word_count
                    sub_chunk["chunk_id"] = f"{chunk['chunk_id']}_{sub_idx}"
                    sub_chunk["section_title"] = f"{chunk['section_title']} (part {sub_idx + 1})"
                    # Re-detect biomarkers for sub-chunk
                    sub_chunk["biomarkers_mentioned"] = detect_biomarkers(sub_chunk["text"])
                    sub_chunk["organ_system"] = detect_organ_systems(sub_chunk["text"])
                    result.append(sub_chunk)
                    current_text = [para]
                    current_word_count = para_words
                    sub_idx += 1
                else:
                    current_text.append(para)
                    current_word_count += para_words

            # Flush remaining
            if current_text:
                sub_chunk = dict(chunk)
                sub_chunk["text"] = separator.join(current_text)
                sub_chunk["word_count"] = current_word_count
                if sub_idx > 0:
                    sub_chunk["chunk_id"] = f"{chunk['chunk_id']}_{sub_idx}"
                    sub_chunk["section_title"] = f"{chunk['section_title']} (part {sub_idx + 1})"
                    sub_chunk["biomarkers_mentioned"] = detect_biomarkers(sub_chunk["text"])
                    sub_chunk["organ_system"] = detect_organ_systems(sub_chunk["text"])
                result.append(sub_chunk)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Parse Wallach PDF into chunks for LanceDB"
    )
    parser.add_argument("--chapters", nargs="*", type=int, default=None,
                        help="Specific chapter numbers to parse (default: priority chapters)")
    parser.add_argument("--all", action="store_true",
                        help="Parse all chapters")
    parser.add_argument("--output", type=str, default=None,
                        help="Output path (default: knowledge-base/chunks.json)")
    parser.add_argument("--min-words", type=int, default=30,
                        help="Minimum words per chunk (default: 30)")
    parser.add_argument("--max-words", type=int, default=500,
                        help="Maximum words per chunk before splitting (default: 500)")
    args = parser.parse_args()

    # Determine which chapters to parse
    if args.all:
        chapters_to_parse = list(CHAPTERS.keys())
    elif args.chapters:
        chapters_to_parse = args.chapters
    else:
        chapters_to_parse = PRIORITY_CHAPTERS

    # Find PDF
    kb_dir = Path(__file__).parent
    pdf_files = list(kb_dir.glob("*.pdf"))
    if not pdf_files:
        print("ERROR: No PDF file found in knowledge-base/ directory.")
        sys.exit(1)

    pdf_path = pdf_files[0]
    print(f"Opening PDF: {pdf_path.name}")
    print(f"File size: {pdf_path.stat().st_size / 1024 / 1024:.1f} MB")

    doc = fitz.open(str(pdf_path))
    print(f"Total pages: {doc.page_count}")
    print(f"Chapters to parse: {chapters_to_parse}")
    print()

    all_chunks = []

    for ch_num in chapters_to_parse:
        if ch_num not in CHAPTERS:
            print(f"  Warning: Chapter {ch_num} not found, skipping")
            continue

        ch_info = CHAPTERS[ch_num]
        print(f"Parsing Chapter {ch_num}: {ch_info['title']} "
              f"(pages {ch_info['start']}-{ch_info['end']})...")

        # Extract text
        text = extract_chapter_text(doc, ch_num)
        if not text.strip():
            print(f"  Warning: No text extracted for chapter {ch_num}")
            continue

        # Chunk based on chapter type
        if ch_num == 2:
            raw_chunks = chunk_chapter_2(text)
        else:
            raw_chunks = chunk_clinical_chapter(text, ch_info["title"])

        # Process chunks
        chapter_chunks = []
        for i, raw in enumerate(raw_chunks):
            processed = process_chunk(raw, ch_num, i)
            if processed["word_count"] >= args.min_words:
                chapter_chunks.append(processed)

        # Split large chunks
        chapter_chunks = split_large_chunks(chapter_chunks, max_words=args.max_words)

        all_chunks.extend(chapter_chunks)
        print(f"  → {len(chapter_chunks)} chunks extracted")

    doc.close()

    # Filter for clinical relevance
    # Keep chunks that mention at least 1 biomarker OR contain clinical condition keywords
    condition_pattern = re.compile(
        r'(syndrome|disease|disorder|deficiency|anemia|failure|'
        r'itis|osis|emia|thyroid|diabetes|hepatitis|nephritis|'
        r'infarction|cirrhosis|thrombosis|embolism|'
        r'increased in|decreased in|elevated|reduced|abnormal|'
        r'diagnosis|interpretation|clinical)',
        re.IGNORECASE
    )

    kept = [
        c for c in all_chunks
        if len(c.get("biomarkers_mentioned", [])) >= 1
        or condition_pattern.search(c["text"])
    ]

    # Output
    output_path = Path(args.output) if args.output else kb_dir / "chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"PARSING COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total chunks extracted: {len(all_chunks)}")
    print(f"Clinical chunks kept: {len(kept)}")
    print(f"Dropped (non-clinical): {len(all_chunks) - len(kept)}")
    print(f"Output: {output_path}")

    # Stats
    if kept:
        word_counts = [c["word_count"] for c in kept]
        print(f"\nChunk sizes:")
        print(f"  Min: {min(word_counts)} words")
        print(f"  Max: {max(word_counts)} words")
        print(f"  Avg: {sum(word_counts) / len(word_counts):.0f} words")
        print(f"  Total: {sum(word_counts):,} words")

        # Organ system distribution
        system_counts = {}
        for c in kept:
            for s in c["organ_system"]:
                system_counts[s] = system_counts.get(s, 0) + 1
        print(f"\nOrgan system coverage:")
        for system, count in sorted(system_counts.items(), key=lambda x: -x[1]):
            print(f"  {system}: {count} chunks")

        # Biomarker coverage
        all_biomarkers = set()
        for c in kept:
            all_biomarkers.update(c.get("biomarkers_mentioned", []))
        print(f"\nUnique biomarkers mentioned: {len(all_biomarkers)}")

        # Sample
        print(f"\nSample chunk:")
        sample = kept[min(5, len(kept) - 1)]
        print(f"  ID: {sample['chunk_id']}")
        print(f"  Title: {sample['section_title']}")
        print(f"  Organ systems: {sample['organ_system']}")
        print(f"  Biomarkers: {sample['biomarkers_mentioned'][:8]}")
        print(f"  Words: {sample['word_count']}")
        print(f"  Text preview: {sample['text'][:200]}...")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
