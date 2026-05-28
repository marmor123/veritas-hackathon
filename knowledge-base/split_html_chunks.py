"""
Split the large HTML chunks into proper RAG-sized pieces (200-500 words).
The HTML parser creates very large chunks because the website's HTML structure
has fewer h2 boundaries than expected. This script re-splits them.

Usage: python split_html_chunks.py
"""
import json
import re
import sys
from pathlib import Path

# Reuse detection functions from parse_wallach.py
sys.path.insert(0, str(Path(__file__).parent))
from parse_wallach import detect_biomarkers, detect_organ_systems


def split_by_subsections(text: str, max_words: int = 450) -> list[str]:
    """
    Split text intelligently by clinical subsection markers.
    Looks for patterns like: Definition, Interpretation, Increased In, etc.
    """
    # Clinical subsection markers
    markers = re.compile(
        r'\n\s*(?:Definition|Interpretation|Use|Limitations|Normal [Rr]ange|'
        r'Normal [Vv]alues|Causes|Clinical|Diagnosis|Laboratory [Ff]indings|'
        r'Increased [Ii]n|Decreased [Ii]n|Other [Cc]onsiderations|'
        r'Suggested [Rr]eading|When to [Ss]uspect|Classification|'
        r'Treatment|Prognosis|Epidemiology|Pathophysiology|'
        r'Signs and [Ss]ymptoms|Differential [Dd]iagnosis)\b',
        re.IGNORECASE
    )

    # Try splitting by markers first
    splits = [m.start() for m in markers.finditer(text)]

    if splits:
        result = []
        prev = 0
        for pos in splits:
            segment = text[prev:pos].strip()
            if segment and len(segment.split()) >= 20:
                result.append(segment)
            prev = pos
        # Last segment
        last = text[prev:].strip()
        if last and len(last.split()) >= 20:
            result.append(last)
        if result:
            # Further split any segments that are still too large
            final = []
            for seg in result:
                if len(seg.split()) > max_words:
                    final.extend(_split_by_sentences(seg, max_words))
                else:
                    final.append(seg)
            return final

    # Fallback: split by double newlines (paragraphs)
    paragraphs = text.split('\n\n')
    if len(paragraphs) > 2:
        parts = [p.strip() for p in paragraphs if p.strip() and len(p.split()) >= 10]
        if parts:
            # Further split large paragraphs
            final = []
            for p in parts:
                if len(p.split()) > max_words:
                    final.extend(_split_by_sentences(p, max_words))
                else:
                    final.append(p)
            return final

    # Split by single newlines
    lines = text.split('\n')
    parts = [l.strip() for l in lines if l.strip() and len(l.split()) >= 5]
    if len(parts) > 2:
        return parts

    # Last resort: split by sentences
    return _split_by_sentences(text, max_words)


def _split_by_sentences(text: str, max_words: int) -> list[str]:
    """Split text into chunks of max_words by sentence boundaries."""
    # Split on sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = []
    current = []
    current_words = 0

    for sent in sentences:
        sent_words = len(sent.split())
        if current_words + sent_words > max_words and current:
            result.append(' '.join(current))
            current = [sent]
            current_words = sent_words
        else:
            current.append(sent)
            current_words += sent_words

    if current:
        result.append(' '.join(current))

    return [r for r in result if len(r.split()) >= 20]


def rechunk(chunks: list[dict], max_words: int = 450, min_words: int = 30) -> list[dict]:
    """Re-chunk large chunks into proper RAG-sized pieces."""
    result = []

    for chunk in chunks:
        text = chunk["text"]
        word_count = len(text.split())

        if word_count <= max_words:
            # Already good size
            if word_count >= min_words:
                result.append(chunk)
            continue

        # Split the large chunk
        segments = split_by_subsections(text, max_words)

        # Group segments into proper-sized chunks
        current_text = []
        current_words = 0

        for seg in segments:
            seg_words = len(seg.split())

            if current_words + seg_words > max_words and current_text:
                # Flush current chunk
                merged_text = "\n\n".join(current_text)
                if len(merged_text.split()) >= min_words:
                    new_chunk = dict(chunk)
                    new_chunk["text"] = merged_text
                    new_chunk["word_count"] = len(merged_text.split())
                    new_chunk["chunk_id"] = f"{chunk['chunk_id']}_{len(result):03d}"
                    new_chunk["section_title"] = f"{chunk['section_title']} (part {len(result) + 1})"
                    new_chunk["biomarkers_mentioned"] = detect_biomarkers(merged_text)
                    new_chunk["organ_system"] = detect_organ_systems(merged_text)
                    result.append(new_chunk)
                current_text = [seg]
                current_words = seg_words
            else:
                current_text.append(seg)
                current_words += seg_words

        # Flush remaining
        if current_text:
            merged_text = "\n\n".join(current_text)
            if len(merged_text.split()) >= min_words:
                new_chunk = dict(chunk)
                new_chunk["text"] = merged_text
                new_chunk["word_count"] = len(merged_text.split())
                new_chunk["chunk_id"] = f"{chunk['chunk_id']}_{len(result):03d}"
                new_chunk["section_title"] = f"{chunk['section_title']} (part {len(result) + 1})"
                new_chunk["biomarkers_mentioned"] = detect_biomarkers(merged_text)
                new_chunk["organ_system"] = detect_organ_systems(merged_text)
                result.append(new_chunk)

    return result


def main():
    kb_dir = Path(__file__).parent
    input_path = kb_dir / "chunks_html.json"
    output_path = kb_dir / "chunks_html.json"  # Overwrite

    if not input_path.exists():
        print("ERROR: chunks_html.json not found. Run run_html_parser.py first.")
        sys.exit(1)

    print("Loading HTML chunks...")
    with open(input_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"  Original: {len(chunks)} chunks")
    wc = [c["word_count"] for c in chunks]
    print(f"  Sizes: min={min(wc)}, max={max(wc)}, avg={sum(wc)//len(wc)}")
    print(f"  Over 500 words: {len([w for w in wc if w > 500])}")

    print("\nRe-chunking...")
    result = rechunk(chunks, max_words=450, min_words=30)

    print(f"\n  Result: {len(result)} chunks")
    wc2 = [c["word_count"] for c in result]
    print(f"  Sizes: min={min(wc2)}, max={max(wc2)}, avg={sum(wc2)//len(wc2)}")
    print(f"  Over 500 words: {len([w for w in wc2 if w > 500])}")

    # Filter for clinical relevance
    condition_pattern = re.compile(
        r'(syndrome|disease|disorder|deficiency|anemia|failure|'
        r'itis|osis|emia|thyroid|diabetes|hepatitis|nephritis|'
        r'infarction|cirrhosis|thrombosis|embolism|'
        r'increased in|decreased in|elevated|reduced|abnormal|'
        r'diagnosis|interpretation|clinical)',
        re.IGNORECASE
    )

    kept = [
        c for c in result
        if len(c.get("biomarkers_mentioned", [])) >= 1
        or condition_pattern.search(c["text"])
    ]

    print(f"  Clinical chunks kept: {len(kept)} (dropped {len(result) - len(kept)} non-clinical)")

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)

    print(f"\n  Output: {output_path}")

    # Stats
    all_biomarkers = set()
    system_counts = {}
    for c in kept:
        all_biomarkers.update(c.get("biomarkers_mentioned", []))
        for s in c.get("organ_system", []):
            system_counts[s] = system_counts.get(s, 0) + 1

    print(f"  Unique biomarkers: {len(all_biomarkers)}")
    print(f"  Organ systems: {', '.join(f'{k}({v})' for k, v in sorted(system_counts.items(), key=lambda x: -x[1])[:6])}")

    # Sample
    if kept:
        sample = kept[min(5, len(kept)-1)]
        print(f"\n  Sample chunk:")
        print(f"    ID: {sample['chunk_id']}")
        print(f"    Title: {sample['section_title'][:60]}")
        print(f"    Words: {sample['word_count']}")
        print(f"    Biomarkers: {sample['biomarkers_mentioned'][:6]}")
        print(f"    Text: {sample['text'][:150]}...")


if __name__ == "__main__":
    main()
