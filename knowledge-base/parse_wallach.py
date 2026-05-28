"""
Parse Wallach's Interpretation of Diagnostic Tests, 11th Edition (HTML source) into
clinical pattern chunks for the RAG knowledge base.

Each chunk represents ONE clinical condition (h3 boundary) with all its subsections
(Definition, Laboratory Findings, etc. — h4 labels kept inline).

Chunking strategy:
  - h2 = chapter section (e.g., "Red Blood Cell Disorders") — flush + update section
  - h3 = clinical condition (e.g., "Microcytic Anemias") — primary chunk boundary
  - h4 = subsection (e.g., "Definition") — kept inline as label
  - Body text accumulated between h3 boundaries

Clinical pattern chapters (KEEP):
  - Hematologic Disorders, Endocrine Diseases, Cardiovascular Disorders
  - Renal Disorders, Digestive Diseases, Respiratory/Metabolic/Acid-Base
  - Gynecologic and Obstetric, Central Nervous System, Hereditary and Genetic
  - Genitourinary System Disorders

Reference/non-pattern chapters (SKIP):
  - Laboratory Tests, Abbreviations, FALTs, Toxicology, Transfusion
  - Infectious Disease Assays, Infectious Diseases

Usage:
    python parse_wallach.py
    python parse_wallach.py --output custom.json
    python parse_wallach.py --include-all  # include reference chapters
"""

import re
import json
import sys
import argparse
from pathlib import Path
from html.parser import HTMLParser


# ── Chapter classification ──────────────────────────────────────────────

EXCLUDE_PATTERNS = [
    "Laboratory Tests",
    "Abbreviations",
    "FALTs",
    "Toxicology",
    "Transfusion",
    "Infectious Disease Assays",
    "Infectious Diseases",
]


def should_skip_file(filename: str) -> bool:
    return any(pattern in filename for pattern in EXCLUDE_PATTERNS)


# ── HTML Parser ─────────────────────────────────────────────────────────

class WallachParser(HTMLParser):
    """
    Extract clinical condition chunks from Wallach 11e HTML.

    Key insight: Only headings with class="content-section-header" (h2) and
    headings inside <div id="section_NNNNN"> blocks are chapter content.
    Other headings are navigation/sidebar widgets to skip.
    """

    def __init__(self, max_words_before_subsplit: int = 600):
        super().__init__()
        self.chunks = []
        self.current_section = None      # h2 (chapter section)
        self.current_condition = None    # h3 (clinical condition — chunk boundary)
        self.current_paragraphs = []     # text accumulated for current h3
        self.current_subsection_label = None  # h4 currently being collected (when subsplit active)

        # Threshold: if a condition exceeds this, start flushing on h4 boundaries
        self.max_words_before_subsplit = max_words_before_subsplit

        # Heading state
        self.heading_stack = []          # [(tag, attrs_dict, text)]

        # Body content state
        self.in_para = False
        self.in_li = False
        self.in_table = False
        self.text_buffer = []
        self.table_rows = []
        self.current_row = []
        self.current_cell = []

        # Content area tracking
        self.content_depth = 0           # nesting depth inside section_NNNNN divs
        self.in_skip_block = 0           # nesting depth inside skipped widgets

        # Track if first content heading found (skip pre-content garbage)
        self.first_content_heading = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        elem_id = attrs_dict.get("id", "")

        # Track entering a "section_NNNNN" content block
        if tag == "div" and elem_id.startswith("section_"):
            self.content_depth += 1

        # Skip navigation / widgets / login forms
        if (tag == "div" and (
            "rs_skip" in cls or
            "subscription" in cls.lower() or
            "navigation" in cls.lower() or
            "sidebar" in cls.lower() or
            "header" in cls.lower() or
            "footer" in cls.lower() or
            "menu" in cls.lower() or
            "login" in cls.lower()
        )) or tag in ("nav", "header", "footer", "form", "script", "style", "aside"):
            self.in_skip_block += 1
            return

        if self.in_skip_block:
            return

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5"):
            self.heading_stack.append((tag, attrs_dict, ""))
            return

        # Paragraphs (only meaningful in content area)
        if tag == "div" and "para" in cls:
            self.in_para = True
            self.text_buffer = []
            return
        if tag == "p" and self.content_depth > 0:
            self.in_para = True
            self.text_buffer = []
            return

        # List items (only in content area)
        if tag == "li" and self.content_depth > 0:
            self.in_li = True
            self.text_buffer = []
            return

        # Tables (only in content area)
        if tag == "table" and self.content_depth > 0:
            self.in_table = True
            self.table_rows = []
            return
        if self.in_table:
            if tag == "tr":
                self.current_row = []
            elif tag in ("td", "th"):
                self.current_cell = []

    def handle_endtag(self, tag):
        # Skip block exit
        if (tag == "div" and self.in_skip_block > 0) or tag in ("nav", "header", "footer", "form", "script", "style", "aside"):
            if self.in_skip_block > 0:
                self.in_skip_block -= 1
            return

        if self.in_skip_block:
            return

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5"):
            if not self.heading_stack or self.heading_stack[-1][0] != tag:
                return
            _, attrs, text = self.heading_stack.pop()
            text = re.sub(r'\s+', ' ', text).strip()
            if not text:
                return

            cls = attrs.get("class", "")

            # h2: only honor "content-section-header" or inside content div
            if tag == "h2":
                is_content = ("content-section-header" in cls) or (self.content_depth > 0)
                if not is_content:
                    return  # skip nav/sidebar h2s
                self._flush_chunk()
                self.current_section = text
                self.current_condition = None
                self.current_subsection_label = None
                self.first_content_heading = True
                return

            # h3: only honor inside content area, or after first content header
            if tag == "h3":
                if not self.first_content_heading and self.content_depth == 0:
                    return  # skip pre-content sidebar h3s like "Sign In"
                # Skip subscription / navigation patterns
                if any(skip in text.lower() for skip in [
                    "sign in", "subscription", "log in", "register",
                    "table of contents", "you have no active",
                ]):
                    return
                self._flush_chunk()
                self.current_condition = text
                self.current_subsection_label = None
                return

            # h4/h5: subsection label kept inline
            if tag in ("h4", "h5"):
                if self.current_condition and (self.content_depth > 0 or self.first_content_heading):
                    # If current chunk is already large, flush it now using the
                    # PREVIOUSLY-SEEN h4 label (which describes the content
                    # that was just collected). Then start fresh with the new h4.
                    current_size = sum(len(p.split()) for p in self.current_paragraphs)
                    if current_size >= self.max_words_before_subsplit:
                        # Flush with the previously-active subsection label
                        self._flush_chunk()
                        # Start tracking the new h4 as the next subsection
                        self.current_subsection_label = text
                        # Add the new label as a marker for the next chunk
                        self.current_paragraphs.append(f"\n## {text}\n")
                    else:
                        self.current_paragraphs.append(f"\n## {text}\n")
                return

        # Paragraph end
        if (tag in ("div", "p")) and self.in_para:
            self.in_para = False
            text = " ".join(self.text_buffer).strip()
            text = re.sub(r'\s+', ' ', text)
            if text and self.current_condition:
                self.current_paragraphs.append(text)
            self.text_buffer = []

        # List item end
        if tag == "li" and self.in_li:
            self.in_li = False
            text = " ".join(self.text_buffer).strip()
            text = re.sub(r'\s+', ' ', text)
            if text and self.current_condition:
                self.current_paragraphs.append(f"• {text}")
            self.text_buffer = []

        # Table cells/rows
        if self.in_table:
            if tag in ("td", "th"):
                cell_text = re.sub(r'\s+', ' ', " ".join(self.current_cell).strip())
                self.current_row.append(cell_text)
                self.current_cell = []
            elif tag == "tr":
                if self.current_row:
                    self.table_rows.append(self.current_row)
            elif tag == "table":
                self.in_table = False
                if self.table_rows and self.current_condition:
                    table_text = "\n".join(" | ".join(row) for row in self.table_rows)
                    self.current_paragraphs.append(f"[Table]\n{table_text}")
                self.table_rows = []

        # Exit content area
        if tag == "div" and self.content_depth > 0:
            self.content_depth -= 1

    def handle_data(self, data):
        if self.in_skip_block:
            return

        # Heading text
        if self.heading_stack:
            tag, attrs, existing = self.heading_stack.pop()
            self.heading_stack.append((tag, attrs, existing + data))
            return

        # Body text
        if self.in_para or self.in_li:
            self.text_buffer.append(data)

        if self.in_table and self.current_cell is not None:
            self.current_cell.append(data)

    def _flush_chunk(self, suffix: str = ""):
        """
        Flush the current accumulated text as a chunk.

        suffix: optional addition to the condition title (used when sub-splitting
                a large condition by h4 — e.g., "Diabetes Mellitus — Definition")
        """
        if not self.current_condition or not self.current_paragraphs:
            self.current_paragraphs = []
            self.current_subsection_label = None
            return

        text = "\n\n".join(p for p in self.current_paragraphs if p.strip())
        text = re.sub(r'\n{3,}', '\n\n', text).strip()

        if len(text.split()) < 30:
            self.current_paragraphs = []
            self.current_subsection_label = None
            return

        # Title is just the h3 condition (no h4 suffix in title — h4 labels
        # are kept inline in the text via "## Subsection")
        condition_title = self.current_condition
        if suffix:
            condition_title = f"{condition_title}{suffix}"

        self.chunks.append({
            "section": self.current_section,
            "condition": condition_title,
            "text": text,
        })
        self.current_paragraphs = []
        # Don't reset subsection_label here — let the caller manage it

    def finalize(self):
        self._flush_chunk()


# ── Biomarker / organ system detection ──────────────────────────────────

ORGAN_SYSTEM_MAP = {
    "hematologic": [
        "hemoglobin", "hgb", "hct", "hematocrit", "rbc", "mcv", "mch", "mchc",
        "rdw", "ferritin", "iron", "tibc", "transferrin", "transferrin saturation",
        "platelets", "wbc", "neutrophils", "lymphocytes", "monocytes",
        "eosinophils", "basophils", "esr", "reticulocyte", "haptoglobin",
        "ldh", "fibrinogen", "pt", "ptt", "inr", "d-dimer",
    ],
    "hepatic": [
        "alt", "ast", "ggt", "alp", "alkaline phosphatase", "bilirubin",
        "total bilirubin", "direct bilirubin", "indirect bilirubin",
        "albumin", "total protein", "ammonia", "bile acids",
    ],
    "renal": [
        "creatinine", "bun", "egfr", "gfr", "cystatin c", "uric acid",
        "microalbumin", "creatinine clearance",
    ],
    "thyroid": [
        "tsh", "t3", "t4", "ft3", "ft4", "free t3", "free t4",
        "thyroglobulin", "thyroid peroxidase", "tpo", "reverse t3",
    ],
    "cardiometabolic": [
        "glucose", "hba1c", "a1c", "insulin", "c-peptide",
        "cholesterol", "total cholesterol", "ldl", "hdl", "triglycerides",
        "non-hdl", "apob", "lipoprotein(a)", "homocysteine",
    ],
    "electrolyte": [
        "sodium", "potassium", "chloride", "co2", "bicarbonate",
        "anion gap", "calcium", "corrected calcium", "magnesium",
        "phosphorus", "phosphate",
    ],
    "endocrine": [
        "cortisol", "acth", "aldosterone", "renin", "dhea-s",
        "testosterone", "estradiol", "progesterone", "lh", "fsh", "prolactin",
        "igf-1", "parathyroid hormone", "pth", "vitamin d", "25-oh vitamin d",
    ],
    "cardiac": [
        "troponin", "ck", "ck-mb", "bnp", "nt-probnp", "myoglobin",
    ],
    "pancreatic": [
        "amylase", "lipase",
    ],
    "nutritional": [
        "vitamin b12", "b12", "folate", "vitamin d", "zinc", "selenium", "copper",
    ],
    "inflammatory": [
        "crp", "esr",
    ],
}

BIOMARKER_NAMES = {bm.lower() for names in ORGAN_SYSTEM_MAP.values() for bm in names}


def detect_biomarkers(text: str) -> list[str]:
    text_lower = text.lower()
    found = set()
    for bm in sorted(BIOMARKER_NAMES, key=len, reverse=True):
        if re.search(rf'\b{re.escape(bm)}\b', text_lower):
            found.add(bm)
    return sorted(found)


def detect_organ_systems(text: str, condition: str = "") -> list[str]:
    text_lower = (text + " " + condition).lower()
    systems = set()

    for system, biomarkers in ORGAN_SYSTEM_MAP.items():
        if any(re.search(rf'\b{re.escape(bm)}\b', text_lower) for bm in biomarkers):
            systems.add(system)

    keyword_map = {
        "hematologic": ["anemia", "iron deficiency", "thalassemia", "hemoglobinopathy",
                        "hemolysis", "polycythemia", "pancytopenia", "leukemia", "lymphoma",
                        "myelodysplas", "thrombocyt", "neutropen"],
        "hepatic": ["liver", "hepatic", "cirrhosis", "hepatitis", "cholestatic",
                    "jaundice", "portal hypertension", "wilson"],
        "renal": ["kidney", "renal", "nephrotic", "nephritic", "ckd", "aki",
                  "acute kidney injury", "glomerul"],
        "thyroid": ["thyroid", "hyperthyroid", "hypothyroid", "goiter", "graves", "hashimoto"],
        "cardiometabolic": ["diabetes", "metabolic syndrome", "insulin resistance",
                            "dyslipidemia", "obesity", "hyperlipidemia"],
        "cardiac": ["heart failure", "myocardial infarction", "myocardial",
                    "chest pain", "atherosclero", "coronary"],
        "endocrine": ["adrenal", "pituitary", "cushing", "addison", "pcos",
                      "hyperparathyroid", "hypoparathyroid"],
        "electrolyte": ["dehydration", "acidosis", "alkalosis", "hyperkalem",
                        "hypokalem", "hypernatrem", "hyponatrem"],
    }
    for system, keywords in keyword_map.items():
        if any(kw in text_lower for kw in keywords):
            systems.add(system)

    return sorted(systems) if systems else ["general"]


# ── Clinical relevance filter ───────────────────────────────────────────

def is_clinical_pattern(chunk: dict) -> bool:
    biomarkers = chunk.get("biomarkers_mentioned", [])
    text = chunk.get("text", "").lower()
    title = chunk.get("section_title", "").lower()
    word_count = chunk.get("word_count", 0)

    if word_count < 50:
        return False

    # Skip bibliography/reference sections — they pollute retrieval
    skip_titles = [
        "suggested reading", "references", "bibliography",
        "further reading", "additional resources",
    ]
    if any(skip in title for skip in skip_titles):
        return False

    # Skip chunks that are mostly citations (lots of numeric years, "et al.", etc.)
    citation_density = (
        text.count("et al.") +
        text.count("et al,") +
        len([y for y in text.split() if y.startswith(("19", "20")) and len(y) <= 5 and y[2:].isdigit()])
    )
    if citation_density > 5 and word_count < 300:
        return False

    if len(biomarkers) >= 2:
        return True

    pattern_keywords = [
        "anemia", "deficiency", "syndrome", "disorder", "disease",
        "increased in", "decreased in", "laboratory findings",
        "differential diagnosis", "who should be suspected",
        "clinical findings", "interpretation",
        "associated with", "indicates",
    ]
    return any(kw in text for kw in pattern_keywords)


# ── Main ────────────────────────────────────────────────────────────────

def parse_html_file(filepath: Path, source_label: str) -> list[dict]:
    parser = WallachParser()
    parser.feed(filepath.read_text(encoding="utf-8"))
    parser.finalize()

    results = []
    for i, raw in enumerate(parser.chunks):
        text = raw["text"]
        biomarkers = detect_biomarkers(text + " " + raw["condition"])
        systems = detect_organ_systems(text, raw["condition"])

        if raw["section"] and raw["section"] != raw["condition"]:
            full_title = f"{raw['section']} — {raw['condition']}"
        else:
            full_title = raw["condition"]

        results.append({
            "chunk_id": f"wallach_{source_label}_{i:03d}",
            "source": "Wallach's Interpretation of Diagnostic Tests, 11th Edition",
            "chapter": source_label,
            "section_title": full_title,
            "text": text,
            "organ_system": systems,
            "biomarkers_mentioned": biomarkers,
            "word_count": len(text.split()),
        })
    return results


def filename_to_label(filename: str) -> str:
    base = filename.split(" _ Wallach")[0].strip()
    label = re.sub(r'[^a-zA-Z0-9]+', '_', base).strip('_').lower()
    return label[:40]


def main():
    parser = argparse.ArgumentParser(description="Parse Wallach 11e HTML into RAG chunks")
    parser.add_argument("--include-all", action="store_true",
                        help="Include reference chapters (Laboratory Tests, etc.)")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--input-dir", type=str, default=None)
    parser.add_argument("--no-filter", action="store_true",
                        help="Skip the clinical pattern filter")
    args = parser.parse_args()

    kb_dir = Path(args.input_dir) if args.input_dir else Path(__file__).parent
    html_files = sorted(kb_dir.glob("*.html"))

    if not html_files:
        print(f"ERROR: No HTML files found in {kb_dir}")
        sys.exit(1)

    print(f"Found {len(html_files)} HTML files\n")

    all_chunks = []
    skipped = []

    for html_path in html_files:
        if not args.include_all and should_skip_file(html_path.name):
            skipped.append(html_path.name.split(" _ ")[0])
            continue

        label = filename_to_label(html_path.name)
        chapter_name = html_path.name.split(" _ ")[0]
        print(f"Parsing: {chapter_name[:60]}")
        chunks = parse_html_file(html_path, label)
        print(f"  → {len(chunks)} condition chunks")
        all_chunks.extend(chunks)

    if skipped:
        print(f"\nSkipped {len(skipped)} non-clinical chapter(s):")
        for s in skipped:
            print(f"  - {s}")

    print(f"\nTotal chunks before filter: {len(all_chunks)}")

    if not args.no_filter:
        filtered = [c for c in all_chunks if is_clinical_pattern(c)]
        print(f"After clinical pattern filter: {len(filtered)} (removed {len(all_chunks) - len(filtered)})")
    else:
        filtered = all_chunks

    output_path = Path(args.output) if args.output else kb_dir / "chunks.json"
    output_path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n{'=' * 60}")
    print(f"OUTPUT: {output_path}")
    print(f"{'=' * 60}")
    print(f"  Final chunks: {len(filtered)}")

    if filtered:
        wc = [c["word_count"] for c in filtered]
        print(f"  Words: min={min(wc)}, max={max(wc)}, avg={sum(wc)//len(wc)}, total={sum(wc):,}")

        all_bm = set()
        for c in filtered:
            all_bm.update(c.get("biomarkers_mentioned", []))
        print(f"  Unique biomarkers: {len(all_bm)}")

        systems = {}
        for c in filtered:
            for s in c.get("organ_system", []):
                systems[s] = systems.get(s, 0) + 1
        print("\n  Organ system coverage:")
        for s, count in sorted(systems.items(), key=lambda x: -x[1]):
            print(f"    {s}: {count}")

        # Find Microcytic Anemias chunk specifically
        for c in filtered:
            if "microcytic" in c["section_title"].lower():
                print(f"\n  Sample (Microcytic Anemias chunk):")
                print(f"    ID: {c['chunk_id']}")
                print(f"    Title: {c['section_title']}")
                print(f"    Words: {c['word_count']}")
                print(f"    Biomarkers: {c['biomarkers_mentioned']}")
                print(f"    Text preview:\n      {c['text'][:400]}...")
                break

    print("\nNext: python knowledge-base/build_kb.py")


if __name__ == "__main__":
    main()
