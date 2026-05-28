# Raw HTML Source Files

Place HTML files saved from the Wallach 11th Edition website here.

## How to Get the HTML Files

1. Go to https://apn.lwwhealthlibrary.com/book.aspx?bookid=2839
2. Log in with Hebrew University credentials
3. Navigate to a clinical chapter (e.g., Chapter 2: Laboratory Tests)
4. Right-click → "View Page Source" (or Ctrl+U)
5. Save the HTML file here as `chapter2.html`, `chapter3.html`, etc.

## Important Chapters to Copy

| Chapter | Content | Priority |
|---------|---------|----------|
| 2 | Laboratory Tests (individual biomarker descriptions) | HIGH |
| 4 | Cardiovascular Disorders | HIGH |
| 6 | Digestive Diseases | MEDIUM |
| 7 | Endocrine Diseases | HIGH |
| 8 | Renal & Urinary Tract Diseases | HIGH |
| 10 | Hematologic Disorders | HIGH |
| 14 | Respiratory, Metabolic & Acid-Base Disorders | MEDIUM |

## After Saving HTML Files

```bash
# Parse HTML files into chunks
python parse_wallach.py raw/chapter2.html raw/chapter10.html raw/chapter7.html

# This creates chunks.json (or rename to chunks_html.json for merging)
# Then compare with PDF-based chunks:
python merge_sources.py --compare-only

# Merge both sources (HTML preferred for duplicates):
python merge_sources.py --prefer html

# Rebuild the vector database:
python build_kb.py
```

## Why HTML is Better Than PDF

The HTML source (11th Edition) is preferred because:
- **Newer edition** — more up-to-date clinical guidelines
- **Cleaner structure** — `<h2>` tags give precise section boundaries
- **Better text quality** — no OCR artifacts or PDF formatting issues
- **Richer metadata** — CSS classes indicate content type (para, table, heading)

The PDF (9th Edition) serves as fallback for chapters not yet copied from the website.
