# Raw HTML Source Files

The Wallach 11th Edition HTML files are placed directly in `knowledge-base/`
(not in this `raw/` subfolder). The parser auto-discovers them.

## How to Get the HTML Files

1. Go to https://apn.lwwhealthlibrary.com/book.aspx?bookid=2839
2. Log in with Hebrew University credentials
3. Navigate to a clinical chapter (e.g., Hematologic Disorders)
4. Press `Ctrl+S` (Save Page As) — saves as "Web Page, Complete"
5. Save to `knowledge-base/` directory

## Important Chapters

The parser automatically classifies chapters as clinical or reference:

**Clinical pattern chapters (used for RAG):**
- Hematologic Disorders
- Endocrine Diseases
- Cardiovascular Disorders
- Renal Disorders
- Digestive Diseases
- Respiratory, Metabolic, and Acid-Base Disorders
- Gynecologic and Obstetric Disorders
- Central Nervous System Disorders
- Hereditary and Genetic Diseases
- Genitourinary System Disorders

**Reference chapters (auto-skipped — they pollute retrieval):**
- Laboratory Tests (A-Z encyclopedia of individual tests)
- Abbreviations and Acronyms
- FALTs (Factors Affecting Laboratory Tests)
- Toxicology and Therapeutic Drug Monitoring
- Transfusion Medicine
- Infectious Disease Assays / Infectious Diseases

## After Saving HTML Files

```bash
# Parse all HTML files (auto-skips reference chapters):
python knowledge-base/parse_wallach.py

# Rebuild the vector database:
python knowledge-base/build_kb.py

# Run tests:
python knowledge-base/test_pipeline.py
```
