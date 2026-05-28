"""
Parse Wallach HTML source into embeddable chunks for LanceDB.

Input: HTML files saved from apn.lwwhealthlibrary.com (Silverchair platform)
Output: chunks.json — [{chunk_id, source, section_title, text, organ_system, biomarkers, word_count}]

Usage: python parse_wallach.py chapter2.html chapter3.html ...
       Outputs to knowledge-base/chunks.json
"""

import re
import json
import sys
from pathlib import Path
from html.parser import HTMLParser


class WallachParser(HTMLParser):
    """Extract structured content from Silverchair-hosted Wallach pages."""

    def __init__(self):
        super().__init__()
        self.chunks = []
        self.current_chunk = None
        self.current_section = None  # h2 title
        self.current_subsection = None  # h3 title
        self.in_para = False
        self.in_table = False
        self.in_thead = False
        self.para_text = []
        self.table_rows = []
        self.current_row = []
        self.current_cell = []
        self.skip_rsbtn = False
        self.heading_stack = []  # [(tag, text)]

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Track headings
        if tag in ("h1", "h2", "h3", "h4"):
            self.heading_stack.append((tag, ""))
            return

        # Main content sections
        if tag == "div" and "para" in attrs_dict.get("class", ""):
            self.in_para = True
            self.para_text = []
            return

        # Table cells
        if tag in ("td", "th"):
            self.current_cell = []
            return

        # Skip ReadSpeaker buttons
        if tag == "div" and "rs_skip" in attrs_dict.get("class", ""):
            self.skip_rsbtn = True
            return

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4"):
            if self.heading_stack and self.heading_stack[-1][0] == tag:
                _, text = self.heading_stack.pop()
                text = text.strip()
                if not text:
                    return

                if tag == "h2":
                    # Flush previous chunk
                    self._flush_chunk()
                    self.current_section = text
                    self.current_subsection = None
                elif tag == "h3":
                    self.current_subsection = text
                elif tag == "h4":
                    self.current_subsection = text  # treat h4 same as h3 for sub-sectioning
            return

        if tag == "div" and self.in_para:
            self.in_para = False
            text = " ".join(self.para_text).strip()
            if text and self.current_section:
                if self.current_chunk is None:
                    self._new_chunk()
                self.current_chunk["paragraphs"].append(text)
            return

        if tag == "div" and self.skip_rsbtn:
            self.skip_rsbtn = False
            return

        if tag in ("td", "th"):
            cell_text = " ".join(self.current_cell).strip()
            self.current_row.append(cell_text)
            return

        if tag == "tr":
            if self.current_row:
                self.table_rows.append(self.current_row)
            self.current_row = []

    def handle_data(self, data):
        if self.heading_stack:
            tag, existing = self.heading_stack.pop()
            self.heading_stack.append((tag, existing + data))
            return
        if self.in_para and not self.skip_rsbtn:
            self.para_text.append(data)
        if self.current_cell is not None:
            self.current_cell.append(data)

    def _new_chunk(self):
        self.current_chunk = {
            "section_title": self.current_section,
            "subsection": self.current_subsection,
            "paragraphs": [],
            "tables": [],
        }

    def _flush_chunk(self):
        if self.current_chunk and self.current_chunk["paragraphs"]:
            self.current_chunk["tables"] = self.table_rows
            self.chunks.append(self.current_chunk)
        self.current_chunk = None
        self.table_rows = []

    def finalize(self):
        self._flush_chunk()


# ── Organ system → biomarker mapping ──────────────────────────────────

ORGAN_SYSTEM_MAP = {
    "hematologic": [
        "hemoglobin", "hgb", "hct", "hematocrit", "rbc", "mcv", "mch", "mchc",
        "rdw", "ferritin", "iron", "tibc", "transferrin", "transferrin saturation",
        "b12", "folate", "platelets", "wbc", "neutrophils", "lymphocytes",
        "monocytes", "eosinophils", "basophils", "esr", "crp", "reticulocyte",
        "haptoglobin", "ldh", "fibrinogen", "pt", "ptt", "inr", "d-dimer",
    ],
    "hepatic": [
        "alt", "ast", "ggt", "alp", "alkaline phosphatase", "bilirubin",
        "total bilirubin", "direct bilirubin", "indirect bilirubin",
        "albumin", "total protein", "ammonia", "bile acids",
    ],
    "renal": [
        "creatinine", "bun", "egfr", "gfr", "cystatin c", "uric acid",
        "urine", "microalbumin", "creatinine clearance", "bun/creatinine ratio",
    ],
    "thyroid": [
        "tsh", "t3", "t4", "ft3", "ft4", "free t3", "free t4",
        "thyroglobulin", "thyroid peroxidase", "tpo", "trab", "tsi",
        "reverse t3", "thyroglobulin antibodies",
    ],
    "cardiometabolic": [
        "glucose", "hba1c", "a1c", "insulin", "c-peptide", "cholesterol",
        "total cholesterol", "ldl", "hdl", "triglycerides", "non-hdl",
        "apob", "apoa1", "lipoprotein(a)", "homocysteine",
    ],
    "electrolyte": [
        "sodium", "potassium", "chloride", "co2", "bicarbonate",
        "anion gap", "calcium", "corrected calcium", "magnesium",
        "phosphorus", "phosphate",
    ],
    "endocrine": [
        "cortisol", "acth", "aldosterone", "renin", "dhea-s", "dheas",
        "testosterone", "free testosterone", "shbg", "estradiol", "progesterone",
        "lh", "fsh", "prolactin", "igf-1", "gh", "parathyroid hormone", "pth",
        "vitamin d", "25-oh vitamin d", "1,25-oh vitamin d",
    ],
    "cardiac": [
        "troponin", "ck", "ck-mb", "bnp", "nt-probnp", "myoglobin",
    ],
    "pancreatic": [
        "amylase", "lipase",
    ],
    "autoimmune": [
        "ana", "rf", "anti-ccp", "c3", "c4", "iga", "igg", "igm",
        "ige", "anti-tpo", "anti-tg",
    ],
    "nutritional": [
        "vitamin b12", "folate", "vitamin d", "25-oh vitamin d",
        "zinc", "selenium", "copper", "ceruloplasmin",
    ],
}

# Normalize: lowercase, strip units/parentheticals
BIOMARKER_NAMES = set()
for names in ORGAN_SYSTEM_MAP.values():
    for name in names:
        BIOMARKER_NAMES.add(name.lower().strip())


def detect_biomarkers(text):
    """Find biomarker names mentioned in text."""
    text_lower = text.lower()
    found = []
    for bm in sorted(BIOMARKER_NAMES, key=len, reverse=True):
        if bm in text_lower:
            found.append(bm)
    return list(set(found))


def detect_organ_systems(text):
    """Return list of organ systems whose biomarkers appear in text."""
    text_lower = text.lower()
    systems = []
    for system, biomarkers in ORGAN_SYSTEM_MAP.items():
        if any(bm in text_lower for bm in biomarkers):
            systems.append(system)
    # Special case: if no biomarkers matched, try keyword-based classification
    keyword_map = {
        "hematologic": ["anemia", "iron deficiency", "thalassemia", "hemoglobinopathy",
                        "hemolysis", "polycythemia", "pancytopenia", "leukemia", "lymphoma"],
        "hepatic": ["liver", "hepatic", "cirrhosis", "hepatitis", "cholestatic",
                    "jaundice", "portal hypertension"],
        "renal": ["kidney", "renal", "nephrotic", "nephritic", "ckd", "aki",
                  "acute kidney injury"],
        "thyroid": ["thyroid", "hyperthyroid", "hypothyroid", "goiter", "graves",
                    "hashimoto"],
        "cardiometabolic": ["diabetes", "metabolic syndrome", "insulin resistance",
                            "dyslipidemia", "obesity"],
        "cardiac": ["heart failure", "myocardial infarction", "cardiac", "chest pain"],
        "endocrine": ["adrenal", "pituitary", "cushing", "addison", "pcos",
                      "menopause", "andropause"],
        "electrolyte": ["dehydration", "fluid", "acidosis", "alkalosis"],
        "autoimmune": ["lupus", "sle", "rheumatoid", "sjogren", "vasculitis",
                       "scleroderma"],
    }
    for system, keywords in keyword_map.items():
        if any(kw in text_lower for kw in keywords):
            if system not in systems:
                systems.append(system)
    return systems if systems else ["general"]


def clean_section_id(raw_id):
    """Clean Silverchair section IDs like '240112273' or URLs."""
    if not raw_id:
        return None
    # Just use the numeric ID
    match = re.search(r'(\d{8,})', str(raw_id))
    return match.group(1) if match else raw_id


def chunk_to_json(chunk, source_name, chunk_idx):
    """Convert a parsed chunk to the LanceDB-ready format."""
    title = chunk["section_title"]
    subsection = chunk.get("subsection", "")
    full_title = f"{title} — {subsection}" if subsection else title

    text = "\n\n".join(chunk["paragraphs"])

    # Add table data as structured text if present
    if chunk.get("tables"):
        table_text = "\n".join(
            " | ".join(row) for row in chunk["tables"]
        )
        text += f"\n\nTABLE DATA:\n{table_text}"

    biomarkers = detect_biomarkers(text)
    organ_systems = detect_organ_systems(text)

    return {
        "chunk_id": f"wallach_{source_name}_s{chunk_idx:03d}",
        "source": "Wallach's Interpretation of Diagnostic Tests, 11th Edition",
        "chapter": source_name,
        "section_title": full_title,
        "text": text,
        "organ_system": organ_systems,
        "biomarkers_mentioned": biomarkers,
        "word_count": len(text.split()),
    }


def parse_file(filepath):
    """Parse a single HTML file into chunks."""
    parser = WallachParser()
    with open(filepath, "r", encoding="utf-8") as f:
        parser.feed(f.read())
    parser.finalize()
    return parser.chunks


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_wallach.py <html_file> [html_file ...]")
        print("       python parse_wallach.py --output chunks_html.json raw/chapter2.html ...")
        print("Example: python parse_wallach.py raw/chapter2.html raw/chapter3.html")
        sys.exit(1)

    # Check for --output flag
    output_name = "chunks.json"
    args = sys.argv[1:]
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            output_name = args[idx + 1]
            args = args[:idx] + args[idx+2:]
        else:
            print("Error: --output requires a filename")
            sys.exit(1)

    all_chunks = []
    for filepath in args:
        path = Path(filepath)
        if not path.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue

        source_name = path.stem.replace(" ", "_").replace("-", "_")[:30]
        print(f"Parsing {path.name}...")

        raw_chunks = parse_file(filepath)
        for i, chunk in enumerate(raw_chunks):
            ch = chunk_to_json(chunk, source_name, i)
            if ch["word_count"] >= 30:  # skip tiny chunks (headers with no body)
                all_chunks.append(ch)

        print(f"  → {len(all_chunks)} chunks so far")

    # Filter for clinical pattern relevance
    pattern_chunks = [c for c in all_chunks if len(c.get("biomarkers_mentioned", [])) >= 2]

    # Also keep chunks that mention clinical conditions even if few biomarkers
    condition_pattern = re.compile(
        r'(syndrome|disease|disorder|deficiency|anemia|failure|'
        r'itis|osis|emia|thyroid|diabetes|hepatitis|nephritis|'
        r'infarction|cirrhosis|thrombosis|embolism)',
        re.IGNORECASE
    )
    clinical_chunks = [
        c for c in all_chunks
        if c not in pattern_chunks and condition_pattern.search(c["text"])
    ]

    kept = pattern_chunks + clinical_chunks

    # Write output
    output_path = Path(__file__).parent / output_name
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(kept)} clinical chunks → {output_path}")
    print(f"  (filtered from {len(all_chunks)} total, "
          f"dropped {len(all_chunks) - len(kept)} non-clinical)")

    # Print organ system distribution
    system_counts = {}
    for c in kept:
        for s in c["organ_system"]:
            system_counts[s] = system_counts.get(s, 0) + 1
    print("\nOrgan system coverage:")
    for system, count in sorted(system_counts.items(), key=lambda x: -x[1]):
        print(f"  {system}: {count} chunks")

    # Print sample chunk
    if kept:
        print(f"\nSample chunk:")
        print(f"  ID: {kept[0]['chunk_id']}")
        print(f"  Title: {kept[0]['section_title']}")
        print(f"  Organ systems: {kept[0]['organ_system']}")
        print(f"  Biomarkers: {kept[0]['biomarkers_mentioned'][:10]}")
        print(f"  Words: {kept[0]['word_count']}")
        print(f"  Text preview: {kept[0]['text'][:200]}...")


if __name__ == "__main__":
    main()
