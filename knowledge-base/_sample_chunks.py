"""Quick script to dump sample chunks from a Wallach HTML chapter."""
import json, sys, glob, os
sys.path.insert(0, os.path.dirname(__file__))
from parse_wallach import parse_file, chunk_to_json

# Find a clinical chapter
chapters = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "*Disorders*.html")))
target = None
for c in chapters:
    if "Cardiovascular" in c:
        target = c
        break
if not target:
    target = chapters[0]

print(f"Parsing: {os.path.basename(target)[:80]}...")
chunks_raw = parse_file(target)
all_chunks = []
for i, c in enumerate(chunks_raw):
    ch = chunk_to_json(c, 'sample', i)
    if ch['word_count'] >= 30:
        all_chunks.append(ch)

# Show first 5 chunks
for i, c in enumerate(all_chunks[:5]):
    print(f"\n=== CHUNK {i} ===")
    print(f"ID: {c['chunk_id']}")
    print(f"Title: {c['section_title']}")
    print(f"Organ systems: {c['organ_system']}")
    print(f"Biomarkers: {c['biomarkers_mentioned']}")
    print(f"Words: {c['word_count']}")
    print(f"Text: {c['text'][:500]}...")

print(f"\n--- Total chunks: {len(all_chunks)} ---")

# Now also show 3 chunks from a non-clinical chapter to compare
abbrev = glob.glob(os.path.join(os.path.dirname(__file__), "*Abbreviations*"))
if abbrev:
    print(f"\n\n===== NON-CLINICAL CHAPTER (Abbreviations) =====")
    chunks_raw2 = parse_file(abbrev[0])
    nc_chunks = []
    for i, c in enumerate(chunks_raw2):
        ch = chunk_to_json(c, 'abbrev', i)
        if ch['word_count'] >= 30:
            nc_chunks.append(ch)
    for i, c in enumerate(nc_chunks[:3]):
        print(f"\n=== CHUNK {i} ===")
        print(f"ID: {c['chunk_id']}")
        print(f"Title: {c['section_title']}")
        print(f"Organ systems: {c['organ_system']}")
        print(f"Biomarkers: {c['biomarkers_mentioned']}")
        print(f"Words: {c['word_count']}")
        print(f"Text: {c['text'][:400]}...")
    print(f"\n--- Total non-clinical chunks: {len(nc_chunks)} ---")

# Summary across all chapters
print(f"\n\n===== CROSS-CHAPTER SUMMARY =====")
all_html = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "*.html")))
for h in all_html[:5]:
    name = os.path.basename(h)[:70]
    chunks_raw = parse_file(h)
    count = sum(1 for c in chunks_raw if sum(len(p) for p in c.get('paragraphs', [])) > 200)
    print(f"  {name}: ~{count} substantive chunks")
