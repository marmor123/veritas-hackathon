# AGENT PLAN — AI Agent Implementation Instructions

This document is designed to be consumed by AI coding agents. Each module is self-contained with explicit interfaces, dependencies, and acceptance criteria. Modules with no mutual dependencies can be implemented in parallel.

---

## Module Dependency Graph

```
Module A (OCR Pipeline) ────┐
                             │
Module B (Context Collector) ─┤
                             ├──→ Module D (RAG Engine) ──→ Module E (LLM Synthesis) ──→ Module F (Dashboard)
Module C (Verification) ─────┘
```

**Parallelizable groups:**
- Group 1 (start immediately, no dependencies): A, B, C can all start in parallel
- Group 2 (depends on Group 1 completing their APIs): D can start once C's output schema is stable
- Group 3 (depends on D): E can start once D's retrieval output is stable
- Group 4 (depends on E): F can start developing against E's JSON output schema immediately (use mock data)

**Module F can develop in parallel with everything** using mock JSON that matches E's output schema.

---

## Shared Type Definitions

All modules must agree on these types. Create `backend/api/models/schemas.py` first:

```python
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class Severity(str, Enum):
    WARNING = "WARNING"      # Needs urgent medical attention
    CAUTION = "CAUTION"      # Needs follow-up within weeks
    ADVISORY = "ADVISORY"    # Lifestyle/awareness

class Confidence(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"

class BiomarkerResult(BaseModel):
    name: str                 # e.g., "Ferritin"
    value: float              # e.g., 12.0
    unit: str                 # e.g., "ng/mL"
    ref_low: Optional[float]  # e.g., 15.0
    ref_high: Optional[float] # e.g., 150.0
    flag: Optional[str]       # "H", "L", or None

class Medication(BaseModel):
    name: str
    dosage: Optional[str]
    frequency: Optional[str]

class WearableData(BaseModel):
    resting_hr_avg: Optional[float]
    resting_hr_trend: Optional[str]  # "rising", "falling", "stable"
    hrv_avg: Optional[float]
    hrv_trend: Optional[str]
    sleep_avg_hours: Optional[float]
    sleep_quality: Optional[str]     # "good", "fair", "poor"
    activity_avg_steps: Optional[float]
    daily_data: Optional[List[dict]] # [{date, hr, hrv, sleep, steps}, ...]

class QualityFlag(BaseModel):
    type: str                 # "hemolysis", "plausibility", "consistency"
    severity: str             # "high", "medium", "low"
    detail: str               # Human-readable explanation
    affected_biomarkers: List[str]

class DrugInterference(BaseModel):
    biomarker: str
    drug: str
    effect: str               # e.g., "falsely elevates"
    recommendation: str       # e.g., "Stop biotin 72h before retest"

class VerifiedResult(BaseModel):
    biomarker: str
    value: float
    unit: str
    ref_low: Optional[float]
    ref_high: Optional[float]
    flagged: bool
    flag_reason: Optional[str]

class VerificationOutput(BaseModel):
    verified_results: List[VerifiedResult]
    drug_interferences: List[DrugInterference]
    corrected_values: List[dict]    # [{name, raw_value, corrected_value, formula}]
    quality_flags: List[QualityFlag]

class RetrievedChunk(BaseModel):
    chunk_id: str
    source: str               # e.g., "Wallach Ch.3"
    text: str
    relevance_score: float
    biomarkers_involved: List[str]

class RAGOutput(BaseModel):
    matched_patterns: List[dict]    # [{pattern_name, confidence, supporting_biomarkers,
                                    #   retrieved_chunks, differential}]
    unmatched_abnormal_biomarkers: List[str]

class PatternResult(BaseModel):
    name: str                  # Patient-friendly name
    severity: Severity
    confidence: Confidence
    explanation: str           # Plain-language explanation
    symptomatic_note: Optional[str]
    supporting_markers: List[str]
    citations: List[str]       # Human-readable source references
    doctor_questions: List[str]

class AnalysisOutput(BaseModel):
    summary: str
    patterns: List[PatternResult]
    verification_alerts: List[dict]
    disclaimer: str
```

---

## Module A: OCR Pipeline

**Depends on:** Nothing
**Owner skills:** Python, computer vision, regex
**Files to create:**
- `backend/ocr/processor.py` — PDF/image ingestion + Tesseract
- `backend/ocr/extractor.py` — Regex + rules for structured extraction
- `backend/api/routes/ocr.py` — POST /api/ocr endpoint

### Implementation Instructions

```
Implement an OCR pipeline that extracts biomarker data from blood test PDFs and images.

INPUT: A PDF file or image uploaded via multipart form.
OUTPUT: JSON matching the BiomarkerResult schema — a list of {name, value, unit, ref_low, ref_high, flag} objects.

PROCESS:
1. Accept PDF or image upload. If PDF, convert first page to image (use pdf2image or PyMuPDF).
2. Preprocess image: grayscale, increase contrast, binarize, deskew if needed.
3. Run Tesseract OCR with English + Hebrew language packs (eng+heb).
4. Parse OCR text to extract biomarker entries. Blood test reports typically follow this format:
   - Test Name | Result | Unit | Reference Range | Flag
   - Examples: "Hemoglobin", "Glucose", "TSH", "Ferritin"
   
   Use regex patterns to detect these formats:
   - Pattern 1: "TestName  12.5  ng/mL  15-150  L" (columns with flag)
   - Pattern 2: "TestName  12.5  ng/mL  (15-150)" (parenthetical reference range)
   - Pattern 3: Table format where columns are aligned by whitespace
   
   Known biomarker names to match against (incomplete list — be flexible):
   CBC: Hemoglobin, Hematocrit, RBC, WBC, Platelets, MCV, MCH, MCHC, RDW, Neutrophils, Lymphocytes
   CMP: Glucose, BUN, Creatinine, eGFR, Sodium, Potassium, Chloride, CO2, Calcium, Albumin, Total Protein, ALP, AST, ALT, Bilirubin
   Lipids: Cholesterol, Triglycerides, HDL, LDL, VLDL, Chol/HDL Ratio
   Thyroid: TSH, T3, Free T3, T4, Free T4
   Iron: Iron, Ferritin, Transferrin, TIBC, Transferrin Saturation
   Inflammatory: CRP, ESR
   Other: Vitamin D, Vitamin B12, Folate, Uric Acid, LDH, CK, HbA1c, GGT

5. For reference range parsing: handle formats like "15-150", "< 150", "> 15", "15.0-150.0"
6. Handle units: strip units from value, store separately
7. VALIDATE extracted biomarker names against the known list from organ_system_map.py
8. Return parse_confidence score (0-1) based on how many biomarkers were successfully parsed AND validated
9. Return raw_text alongside structured data for debugging
10. Return validation_warnings if >50% of extracted names are unrecognized

EDGE CASES:
- Reports in Hebrew (right-to-left text) — Tesseract should handle with heb language pack
- Reports with no reference ranges listed — set ref_low/ref_high to null and flag
- Handwritten notes on reports — these will produce OCR noise; filter non-biomarker lines
- Different lab formats — design regex to be flexible with whitespace and delimiters

ACCEPTANCE CRITERIA:
- Successfully extracts >90% of biomarkers from a clean printed English report
- Handles at least 2 different report layouts
- Parse time < 5 seconds for a single-page report
- Returns partial results rather than failing entirely on problematic reports
```

---

## Module B: Context Collector

**Depends on:** Nothing
**Owner skills:** Frontend (React forms), mobile health APIs
**Files to create:**
- `frontend/src/components/Upload/MedicationChecklist.tsx` — Medication/supplement input UI
- `frontend/src/components/Upload/WearableConnect.tsx` — Wearable connection UI
- `backend/wearable/apple_health.py` — Apple HealthKit data reader
- `backend/wearable/google_fit.py` — Google Health Connect data reader
- `backend/api/routes/context.py` — POST /api/context endpoint

### Implementation Instructions (Wearable Data)

```
Implement wearable data collection for Apple Health (HealthKit) and Google Health Connect.

For the hackathon demo, build TWO paths:
1. REAL PATH: Export Apple Health data as XML/JSON from the Health app, upload it.
2. MOCK PATH: If no real data, use realistic mock data that simulates a 30-day history.

Read Apple Health export (export.xml from Health app):
- Parse XML to extract: HeartRate (HKQuantityTypeIdentifierHeartRate), 
  HeartRateVariabilitySDNN, SleepAnalysis, StepCount
- Aggregate: daily averages for each metric over the last 30 days
- Calculate trends: is each metric rising, falling, or stable over the period?

Read Google Health Connect data (if available):
- Use Google Health Connect API to read: HeartRate, Steps, SleepSession
- Same aggregation as Apple Health

MOCK DATA FALLBACK:
If no real wearable data is available, generate realistic mock data:
- resting_hr: avg 65-75, with slight variations day to day
- hrv: avg 30-50 ms, lower when "stressed"  
- sleep: avg 6-8 hours
- steps: avg 5000-10000
- Allow the user to select a "scenario" mock profile: "healthy," "stressed," "athlete," "anemic_tachycardia"

OUTPUT: WearableData schema object (see shared types)
```

### Implementation Instructions (Medication Input)

```
Build a medication/supplement input UI component.

The UI presents a searchable checklist of common medications and supplements
that interfere with blood tests, plus a free-text input for others.

DRUG LIST (display these with checkboxes, grouped by category):
Supplements:
  - Biotin (hair/skin/nails) — interferes with thyroid tests, troponin
  - Iron supplements — affects iron panel, hemoglobin
  - Vitamin B12 supplements — affects B12 levels
  - Vitamin D supplements — affects Vitamin D, calcium
  - Creatine — affects creatinine

Prescription Medications:
  - Metformin — lowers B12
  - Statins (Atorvastatin, Rosuvastatin, etc.) — elevates liver enzymes, CK
  - PPIs (Omeprazole, Esomeprazole, etc.) — lowers magnesium, B12
  - Oral contraceptives — alters thyroid panel, iron, clotting
  - Levothyroxine — alters TSH, T4
  - NSAIDs (Ibuprofen, Naproxen) — can elevate creatinine
  - ACE inhibitors (Lisinopril, etc.) — can elevate potassium
  - Diuretics (HCTZ, Furosemide) — alters electrolytes

For each checked item, optionally ask dosage and how long they've been taking it.

OUTPUT: List of {name, dosage?, frequency?} objects
```

---

## Module C: Verification Layer

**Depends on:** Shared type definitions (schemas.py)
**Owner skills:** Python, clinical knowledge (work with medical student)
**Files to create:**
- `backend/verification/hemolysis.py` — Pre-analytical error detection
- `backend/verification/drug_interference.py` — Drug-lab interference lookup
- `backend/verification/plausibility.py` — Physiological consistency checks
- `backend/verification/corrected_values.py` — Calculated/corrected values
- `backend/api/routes/verification.py` — POST /api/verify endpoint

### Implementation Instructions

```
Implement a verification layer that checks blood test results for potential errors,
drug interferences, and physiological plausibility BEFORE clinical interpretation.

INPUT: List of BiomarkerResult objects + medications list + supplements list
OUTPUT: VerificationOutput (see shared types)

IMPLEMENT THESE SUB-MODULES:

1. HEMOLYSIS DETECTION (hemolysis.py):
Hemolysis is when red blood cells burst during or after blood collection,
releasing their contents into the serum and falsely elevating certain markers.

Rules to implement:
a) Potassium > 6.0 mmol/L AND eGFR > 60 (normal kidney function) → flag possible hemolysis
   Rationale: True hyperkalemia in someone with normal kidneys is uncommon; hemolysis
   releases intracellular potassium.
b) Potassium > 7.0 mmol/L in any context → strongly suspect artifact (incompatible with normal life)
c) LDH > 2x upper limit AND AST/ALT not proportionally elevated → possible hemolysis
   Rationale: LDH is very high inside red blood cells; hemolysis releases it disproportionately
d) Very low glucose (< 40 mg/dL or < 2.2 mmol/L) without other critical values → 
   possible sample aging (red cells consumed glucose during transport delay)

2. DRUG INTERFERENCE DETECTION (drug_interference.py):
Build a lookup table that maps drugs to their known effects on lab results.

IMPLEMENT THIS EXACT TABLE:
```python
DRUG_INTERFERENCE_TABLE = [
    {"drug": "Biotin", "type": "supplement", "affects": ["TSH", "Free T3", "Free T4", "Troponin"],
     "effect": "falsely_lowers", "mechanism": "Interferes with biotin-streptavidin immunoassay",
     "recommendation": "Stop biotin for 72 hours before blood draw"},
    {"drug": "Metformin", "type": "medication", "affects": ["Vitamin B12"],
     "effect": "lowers", "mechanism": "Reduces B12 absorption in ileum",
     "recommendation": "Monitor B12 levels; consider supplementation if low"},
    {"drug": "Statins", "type": "medication", "affects": ["AST", "ALT", "CK"],
     "effect": "elevates", "mechanism": "HMG-CoA reductase inhibition can cause myocyte enzyme leak",
     "recommendation": "If CK > 5x ULN or LFTs > 3x ULN, discuss with prescribing physician"},
    {"drug": "PPIs", "type": "medication", "affects": ["Magnesium", "Vitamin B12"],
     "effect": "lowers", "mechanism": "Reduced gastric acid impairs absorption",
     "recommendation": "Consider monitoring magnesium if on long-term PPI therapy"},
    {"drug": "Oral Contraceptives", "type": "medication", "affects": ["TSH", "TBG", "Iron", "Transferrin"],
     "effect": "alters", "mechanism": "Estrogen increases thyroid-binding globulin and alters iron metabolism",
     "recommendation": "Interpret thyroid and iron results in context of OC use"},
    {"drug": "NSAIDs", "type": "medication", "affects": ["Creatinine"],
     "effect": "elevates", "mechanism": "Reversible reduction in renal blood flow",
     "recommendation": "Recheck renal function after stopping NSAIDs if elevated"},
    {"drug": "Levothyroxine", "type": "medication", "affects": ["TSH", "Free T4"],
     "effect": "timing_dependent", "mechanism": "TSH suppressed shortly after taking dose; T4 spikes",
     "recommendation": "Draw blood BEFORE morning dose for accurate TSH"},
    {"drug": "ACE Inhibitors", "type": "medication", "affects": ["Potassium"],
     "effect": "elevates", "mechanism": "Reduced aldosterone → potassium retention",
     "recommendation": "Expected effect; monitor potassium regularly"},
    {"drug": "Thiazide Diuretics", "type": "medication", "affects": ["Sodium", "Potassium", "Uric Acid", "Calcium"],
     "effect": "varies", "mechanism": "HCTZ reduces potassium/sodium, elevates calcium and uric acid",
     "recommendation": "These changes are expected; interpret accordingly"},
    {"drug": "Creatine Supplement", "type": "supplement", "affects": ["Creatinine"],
     "effect": "elevates", "mechanism": "Creatine metabolized to creatinine",
     "recommendation": "Elevated creatinine may not indicate kidney dysfunction; check cystatin C if concerned"},
]
```

For each detected drug/biomarker overlap, generate a DrugInterference object.

3. PHYSIOLOGICAL PLAUSIBILITY (plausibility.py):
Check if the results make physiological sense together.

Rules to implement:
a) Calcium-Albumin relationship:
   If albumin is low, total calcium will appear falsely low.
   Calculate: Corrected Calcium = measured_Ca + 0.8 * (4.0 - albumin_g_dL)
   If corrected calcium differs significantly from measured, flag it.

b) BUN/Creatinine ratio:
   Normal ratio ~10-20:1
   Ratio > 20:1 → possible pre-renal cause (dehydration, heart failure)
   Ratio < 10:1 → possible intrinsic renal cause

c) AST/ALT ratio:
   ALT > AST → more consistent with fatty liver / metabolic (hepatocellular)
   AST > ALT (especially AST > 2x ALT) → consider alcohol or muscle origin
   If AST elevated but ALT normal → check CK to rule out muscle source

d) TSH/Free T4 consistency:
   High TSH + low FT4 → primary hypothyroidism (consistent)
   High TSH + normal FT4 → subclinical hypothyroidism (consistent)
   High TSH + high FT4 → secondary hyperthyroidism or lab error (rare — flag as unusual)
   Low TSH + normal FT4 → subclinical hyperthyroidism (consistent)
   Normal TSH + abnormal FT4 → possible binding protein issue, assay interference, or lab error

e) Anion gap:
   Anion Gap = Na - (Cl + HCO3)
   Normal: 8-12 mmol/L
   Elevated: possible metabolic acidosis (check for diabetes, renal failure, toxins)
   Note: calculate only if all three values are available

4. CORRECTED VALUES (corrected_values.py):
Calculate clinically corrected/derived values.

Implement:
a) Corrected Calcium (as above)
b) Anion Gap (as above)
c) LDL Cholesterol:
   If Triglycerides < 400 mg/dL: Friedewald: LDL = TC - HDL - (TG/5)
   If Triglycerides >= 400: mark as "cannot calculate by Friedewald, direct LDL needed"
d) Corrected Sodium (for hyperglycemia):
   If Glucose > 200 mg/dL: Corrected Na = measured_Na + 0.016 * (Glucose - 100)
   (in mg/dL; adjust constant if using mmol/L)

Each calculated value should include: {name, raw_value, corrected_value, formula}
```

---

## Module D: RAG Engine

**Depends on:** Shared type definitions (schemas.py), Verification output schema
**Owner skills:** Python, embeddings, vector databases
**Files to create:**
- `knowledge-base/build_kb.py` — Chunk Wallach + embed + load into LanceDB
- `backend/rag/embeddings.py` — Embedding model wrapper
- `backend/rag/query_rewriter.py` — LLM Pass 1: clinical query construction
- `backend/rag/retriever.py` — Metadata-filtered hybrid search against LanceDB
- `backend/rag/reranker.py` — Cross-encoder re-ranking (ms-marco-MiniLM)
- `backend/rag/citation.py` — Citation tracking utilities
- `backend/api/routes/rag.py` — POST /api/rag endpoint

### Implementation Instructions

```
Build a state-of-the-art RAG pipeline that retrieves clinical patterns from a medical
knowledge base. The pipeline uses 5 stages: query rewriting → metadata-filtered hybrid
search → cross-encoder re-ranking → citation tracking → LLM synthesis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART A: KNOWLEDGE BASE CONSTRUCTION (build_kb.py — run once)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. SOURCE MATERIAL:
   - Wallach's Interpretation of Diagnostic Tests (primary — organized by clinical pattern)
   - AHA/ACC Guidelines on Blood Cholesterol
   - AACE/ATA Thyroid Guidelines
   - AASLD Practice Guidance on NAFLD
   - KDIGO CKD Guidelines

2. CHUNKING STRATEGY:
   DO NOT chunk by fixed token count. Chunk by clinical pattern:
   - Each chunk = one complete clinical pattern description
   - Includes: condition name, biomarkers involved, typical values, differential, recommendations
   - Target: 200-500 words per pattern
   - For long patterns: split into overview/diagnosis/management sub-chunks with parent reference

3. METADATA (CRITICAL — used for pre-filtering at runtime):
   ```python
   {
       "chunk_id": "wallach_ch3_iron_deficiency",
       "source": "Wallach's Interpretation of Diagnostic Tests, 11th Edition",
       "chapter": "Chapter 3: Anemia",
       "pattern_name": "Iron Deficiency Anemia",
       "organ_system": "hematologic",
       # ^^^ MUST BE ACCURATE — used for metadata pre-filtering at runtime
       "urgency": "moderate",
       "biomarkers": ["ferritin", "iron", "transferrin", "TIBC", "saturation",
                      "MCV", "MCH", "hemoglobin"],
       "differential": ["anemia of chronic disease", "thalassemia trait",
                        "sideroblastic anemia"]
   }
   ```

   VALID organ_system values (use exactly these):
   "hematologic", "metabolic", "hepatic", "renal", "thyroid", "cardiovascular",
   "inflammatory", "electrolyte", "nutritional", "musculoskeletal"

4. EMBEDDING:
   Use sentence-transformers with 'all-MiniLM-L6-v2' (~80MB, fast on CPU).
   Alternative: 'BAAI/bge-small-en-v1.5' for better quality at similar size.
   Store in LanceDB at: knowledge-base/lancedb/

5. LANCEDB SETUP:
   ```python
   import lancedb
   db = lancedb.connect("knowledge-base/lancedb")
   table = db.create_table("clinical_patterns", data=[
       {"chunk_id": "...", "text": "...", "vector": [...], **metadata}
   ])
   # Create a full-text search index on biomarker names for hybrid search
   table.create_fts_index("biomarkers")
   ```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART B: RUNTIME RETRIEVAL PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STAGE 1: QUERY REWRITING (query_rewriter.py)
─────────────────────────────────────────────
Why: Raw biomarker lists ("ferritin 12, MCV 78, hemoglobin 11.2") make poor
retrieval queries. Clinical textbooks describe patterns with diagnostic framing.
Query rewriting transforms bare data into a retrieval-optimized clinical query.

Implementation:
1. Take the list of abnormal biomarkers from VerificationOutput
2. Call LLM (same Ollama instance, different prompt) with:

   SYSTEM: "You are a clinical query generator. Transform abnormal lab results
   into a retrieval-optimized clinical search query. Include: (1) the most likely
   pattern name, (2) severity descriptors for each abnormal biomarker, (3) 2-3
   differential diagnoses to search for. Output ONLY the query string — no JSON,
   no explanation, no markdown."

   USER: "Abnormal biomarkers: [list with values and directions].
   Patient medications: [list]. Generate a clinical retrieval query."

   Example input:
   "ferritin 12 ng/mL (low), MCV 78 fL (low), hemoglobin 11.2 g/dL (low)"

   Expected output:
   "Microcytic anemia pattern with severely depleted iron stores
   (ferritin 12 ng/mL), microcytosis (MCV 78 fL), and mild anemia
   (hemoglobin 11.2 g/dL). Differential diagnoses to consider:
   iron deficiency anemia, anemia of chronic disease, thalassemia trait."

3. Use the rewritten query for all subsequent retrieval stages.
4. Latency target: < 3 seconds.

STAGE 2: METADATA-FILTERED HYBRID SEARCH (retriever.py)
────────────────────────────────────────────────────────
Why: Without filtering, an iron deficiency query wastes similarity on thyroid,
liver, and renal chunks. LanceDB supports native metadata filtering — we filter
BEFORE vector search to eliminate irrelevant organ systems at zero cost.

Implementation:
1. INFER ORGAN SYSTEMS from abnormal biomarkers:
   ```python
   # MULTI-LABEL: biomarkers can belong to multiple organ systems.
   # E.g., albumin is both hepatic AND nutritional. CK is both musculoskeletal AND cardiovascular.
   ORGAN_SYSTEM_MAP = {
       "ferritin": ["hematologic"], "hemoglobin": ["hematologic"], "MCV": ["hematologic"],
       "MCH": ["hematologic"], "iron": ["hematologic"], "transferrin": ["hematologic"],
       "platelets": ["hematologic"], "WBC": ["hematologic", "inflammatory"],
       "RBC": ["hematologic"], "hematocrit": ["hematologic"], "RDW": ["hematologic"],
       "glucose": ["metabolic"], "HbA1c": ["metabolic"], "insulin": ["metabolic"],
       "triglycerides": ["metabolic", "cardiovascular"],
       "HDL": ["cardiovascular", "metabolic"], "LDL": ["cardiovascular"],
       "cholesterol": ["cardiovascular", "metabolic"], "uric_acid": ["metabolic", "renal"],
       "AST": ["hepatic", "musculoskeletal"], "ALT": ["hepatic"],
       "ALP": ["hepatic"], "GGT": ["hepatic"],
       "bilirubin": ["hepatic"], "albumin": ["hepatic", "nutritional"],
       "total_protein": ["hepatic", "nutritional"],
       "creatinine": ["renal"], "eGFR": ["renal"], "BUN": ["renal"],
       "TSH": ["thyroid"], "T3": ["thyroid"], "T4": ["thyroid"],
       "Free T3": ["thyroid"], "Free T4": ["thyroid"],
       "sodium": ["electrolyte"], "potassium": ["electrolyte"], "chloride": ["electrolyte"],
       "calcium": ["electrolyte", "nutritional"], "magnesium": ["electrolyte", "nutritional"],
       "CRP": ["inflammatory"], "ESR": ["inflammatory"],
       "vitamin_d": ["nutritional"], "vitamin_b12": ["nutritional"], "folate": ["nutritional"],
       "CK": ["musculoskeletal", "cardiovascular"], "LDH": ["musculoskeletal", "hematologic"],
   }
   # Collect ALL organ systems from abnormal biomarkers (flatten multi-label lists)
   systems = set()
   for b in abnormal_biomarker_names:
       if b in ORGAN_SYSTEM_MAP:
           systems.update(ORGAN_SYSTEM_MAP[b])
   # Always include "hematologic" and "metabolic" as fallback
   systems.add("hematologic")
   systems.add("metabolic")
   systems = list(systems)
   ```

2. METADATA-FILTERED HYBRID SEARCH:
   ```python
   # Embed the rewritten query
   query_vector = embedding_model.encode(rewritten_query)
   
   # Pre-filter by organ system, then hybrid search within filtered set
   results = (table
       .search(query_vector)
       .where(f"organ_system IN ({','.join(repr(s) for s in systems)})")
       .limit(15)
       .to_list())
   
   # Keyword search: find chunks whose biomarker metadata matches abnormal biomarkers
   keyword_matches = table.search(abnormal_biomarker_names_str, query_type="fts").limit(15).to_list()
   
   # Merge: 0.7 * semantic_score + 0.3 * keyword_score
   # Deduplicate by chunk_id
   ```
   
   Latency target: < 100ms for the combined search.

STAGE 3: CROSS-ENCODER RE-RANKING (reranker.py)
────────────────────────────────────────────────
Why: Bi-encoder (embedding) similarity is approximate. A chunk about "microcytic
hypochromic anemia" might score lower than "anemia of chronic disease" due to
embedding noise, even though the user has iron deficiency. A cross-encoder reads
the full (query, chunk) pair together and produces a direct relevance score.

Implementation:
1. Use 'cross-encoder/ms-marco-MiniLM-L-6-v2' (~90MB, loads once at startup):
   ```python
   from sentence_transformers import CrossEncoder
   model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
   ```

2. For each of the 15 merged chunks, create (rewritten_query, chunk_text) pairs:
   ```python
   pairs = [(rewritten_query, chunk["text"]) for chunk in merged_results]
   scores = model.predict(pairs, batch_size=8)
   ```

3. Sort by score descending. Apply RELEVANCE THRESHOLD: drop chunks with score < 0.3.
   If NO chunks pass the threshold, return empty — the pipeline will respond with
   "No matching clinical pattern found. Here are your individual abnormal values
   to discuss with your doctor."

4. Take top-5 (or fewer if some were dropped).

5. Latency target: < 1 second for 15 chunks.

STAGE 4: CITATION TRACKING (citation.py)
─────────────────────────────────────────
Each top-5 chunk carries immutable metadata: chunk_id, source, chapter, pattern_name,
relevance_score. These are passed to the LLM synthesis prompt. The LLM MUST cite
chunk_id for every clinical claim. The frontend resolves chunk_ids to human-readable
citations (e.g., "Wallach's Interpretation of Diagnostic Tests, Chapter 3: Anemia").

STAGE 5: LLM SYNTHESIS (in llm/synthesizer.py — Module E)
──────────────────────────────────────────────────────────
The top-5 chunks are formatted into the synthesis prompt. LLM Pass 2 produces the
structured JSON output with patterns, severity, doctor questions, and citations.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART C: ORGAN SYSTEM INFERENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Create backend/rag/organ_system_map.py containing the full biomarker→organ_system
mapping. This is used by Stage 2 for metadata pre-filtering. Map every biomarker
that can appear in a blood test to at least one organ system.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LATENCY BUDGET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Stage | Time |
|---|---|
| Query rewriting (LLM Pass 1) | ~3 sec |
| Metadata-filtered hybrid search | ~0.1 sec |
| Cross-encoder re-rank | ~1 sec |
| LLM synthesis (Pass 2) | ~12 sec |
| **Total** | **~16 sec** |

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACCEPTANCE CRITERIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- For iron deficiency test case (low ferritin, low MCV, low hemoglobin),
  the top retrieved chunk is about iron deficiency anemia (not thalassemia, not ACD)
- For metabolic syndrome test case (high glucose, low HDL, high TG, high ALT, high uric acid),
  the top retrieved chunk is about metabolic syndrome/insulin resistance
- Query rewriting produces clinically framed queries (contains pattern name, not just biomarker list)
- Metadata filtering eliminates >50% of irrelevant chunks before vector search
- Cross-encoder re-ranking improves top-1 accuracy vs. embedding-only retrieval
- Every retrieved chunk has traceable source citation
- Total pipeline latency < 20 seconds on laptop hardware
```

---

## Module E: LLM Synthesis

**Depends on:** RAG output schema, Verification output schema
**Owner skills:** Prompt engineering, Python
**Files to create:**
- `backend/llm/prompts.py` — System prompt, task prompt, output format spec
- `backend/llm/synthesizer.py` — Ollama call with GBNF grammar, response handling
- `backend/llm/grammar.gbnf` — GBNF grammar for guaranteed valid JSON output
- `backend/llm/wearable_context.py` — Wearable data formatting + token budget management
- `backend/llm/demo_outputs.py` — Pre-cached JSON outputs for 4 demo scenarios
- `backend/api/routes/analysis.py` — POST /api/analyze endpoint

### Implementation Instructions

```
Implement the LLM synthesis layer. CRITICAL: use GBNF grammar-constrained generation
to GUARANTEE valid JSON — no retry-on-parse-failure needed.

MODEL: Use Ollama with either:
- 'qvac-medpsy:1.7b' (medical-specific, best quality if available)
- 'gemma2:2b' (general purpose, good fallback, well-tested on-device)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GBNF GRAMMAR (grammar.gbnf) — CREATE THIS FIRST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GBNF (GGML BNF) grammars force the LLM to output tokens that match a specified
schema. This makes JSON parse failures structurally impossible.

Create backend/llm/grammar.gbnf:

```gbnf
root ::= "{" ws "\"summary\":" ws string "," ws "\"patterns\":" ws "[" ws pattern-list ws "]" "," ws "\"verification_alerts\":" ws "[" ws alert-list ws "]" "," ws "\"disclaimer\":" ws string "}"

pattern-list ::= pattern | pattern "," ws pattern-list
pattern ::= "{" ws "\"name\":" ws string "," ws "\"severity\":" ws severity "," ws "\"confidence\":" ws confidence "," ws "\"explanation\":" ws string "," ws "\"symptomatic_note\":" ws nullable-string "," ws "\"supporting_markers\":" ws "[" ws string-list ws "]" "," ws "\"citations\":" ws "[" ws string-list ws "]" "," ws "\"doctor_questions\":" ws "[" ws string-list ws "]" "}"

alert-list ::= alert | alert "," ws alert-list
alert ::= "{" ws "\"biomarker\":" ws string "," ws "\"issue\":" ws string "," ws "\"recommendation\":" ws string "}"

severity ::= "\"WARNING\"" | "\"CAUTION\"" | "\"ADVISORY\""
confidence ::= "\"HIGH\"" | "\"MODERATE\"" | "\"LOW\""
nullable-string ::= "null" | string
string ::= "\"" [a-zA-Z0-9 .,!?():;'/\-–—\n\r\t\[\]%°µαβγδε]+ "\""
string-list ::= string | string "," ws string-list
ws ::= " " | "\n" | "\t"
```

Call Ollama with the grammar:
```python
response = ollama.generate(
    model="qvac-medpsy:1.7b",
    prompt=full_prompt,
    grammar=open("backend/llm/grammar.gbnf").read(),
    options={"temperature": 0.3, "num_predict": 1024}
)
output = json.loads(response["response"])  # GUARANTEED valid JSON
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOKEN BUDGET MANAGEMENT (wearable_context.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The 1.7B model has a ~4K token context window. We must fit within it:

1. Truncate each RAG chunk to 300 words max before formatting into prompt
2. Only include ABNORMAL biomarkers in the prompt (skip normal ones)
3. Limit wearable daily_data to summary statistics only (no daily breakdown)
4. Limit medications list to only those with detected interferences
5. Target: ~3500 tokens for the full prompt (leaves 500 for generation)

PROMPT DESIGN (prompts.py):

The LLM prompt has a SYSTEM section (constant) and a USER section (dynamic per request).

SYSTEM PROMPT (static):
"""
You are a clinical information synthesizer. Your role is to:
1. Group abnormal laboratory results into clinical patterns using the provided medical knowledge
2. Assign appropriate clinical severity to each pattern
3. Generate clear, patient-friendly explanations
4. Create specific questions for the patient to ask their doctor
5. Cite your sources for every clinical claim

CRITICAL RULES:
- NEVER diagnose a disease. You identify PATTERNS CONSISTENT WITH established clinical descriptions.
- ALWAYS cite the source for every clinical claim using the citation IDs provided.
- ALWAYS include the disclaimer that this is not a medical diagnosis.
- If wearable data is provided, note whether the pattern is potentially symptomatic.
- Use plain language a high-school graduate can understand (Flesch-Kincaid < grade 10).
- If verification flags suggest unreliable results, prominently note this.

SEVERITY GUIDELINES:
- WARNING: Potentially life-threatening or requires immediate medical evaluation 
  (e.g., critically low potassium, severely elevated calcium, acute kidney injury pattern)
- CAUTION: Needs medical follow-up within days to weeks 
  (e.g., new iron deficiency, subclinical hypothyroidism, elevated liver enzymes)
- ADVISORY: Lifestyle awareness or long-term monitoring 
  (e.g., suboptimal Vitamin D, mildly elevated LDL, borderline glucose)
"""

USER PROMPT TEMPLATE (dynamic — fill per request):
"""
PATIENT CONTEXT:
Medications: {medications_list}
Supplements: {supplements_list}
Wearable Data (30-day): {wearable_summary}

VERIFICATION FLAGS:
{quality_flags_summary}

DRUG INTERFERENCES DETECTED:
{drug_interference_summary}

CORRECTED VALUES:
{corrected_values_summary}

ALL BIOMARKER RESULTS:
{biomarker_table}

RETRIEVED CLINICAL KNOWLEDGE:
{retrieved_chunks_formatted}

TASK:
Based on the above, identify clinical patterns in the biomarker results.
For each pattern:
1. Name it in patient-friendly language (e.g., "Low Iron Pattern" not "Iron Deficiency Anemia")
2. Assign a severity: WARNING, CAUTION, or ADVISORY (see guidelines above)
3. Assign a confidence: HIGH (biomarkers clearly match), MODERATE (some match), LOW (weak match)
4. Write a 2-3 sentence explanation in plain language
5. If wearable data provides relevant context, add a symptomatic_note
6. List 2-3 specific questions for the patient to ask their doctor
7. List the source citations that support this pattern identification

IMPORTANT: Do NOT invent patterns not supported by the retrieved knowledge.
If biomarkers don't clearly fit a pattern, note them as "isolated finding — discuss with your doctor."
If medication interferences could explain an abnormal result, mention this prominently.

OUTPUT AS VALID JSON matching this exact structure:
{json_schema}
"""
```

LLM SYNTHESIS IMPLEMENTATION (synthesizer.py):

1. Apply token budget: truncate RAG chunks to 300 words, only include abnormal biomarkers
2. Build the full prompt by filling the template with real data (target < 3500 tokens)
3. Call Ollama WITH GBNF GRAMMAR: guaranteed valid JSON output
   ```python
   response = ollama.generate(
       model="qvac-medpsy:1.7b",
       prompt=full_prompt,
       grammar=open("backend/llm/grammar.gbnf").read(),
       options={"temperature": 0.3, "num_predict": 1024}
   )
   output = json.loads(response["response"])
   ```
4. Validate against Pydantic AnalysisOutput schema (catches semantic errors grammar can't catch)
5. If Pydantic validation fails (e.g., severity is not one of WARNING/CAUTION/ADVISORY),
   map to nearest valid value rather than rejecting the output
6. Post-filter: scan generated text for alarming language patterns and replace with calibrated terms
   (e.g., "liver failure" → "elevated liver enzymes", "kidney damage" → "reduced kidney function")

DEMO FALLBACK (demo_outputs.py):

Pre-generate and store JSON outputs for all 4 demo scenarios. These are loaded at
startup and available via a ?demo=scenario_a query parameter or a "Demo Mode"
button in the UI. If the live LLM fails during the demo, switch to cached output.

```python
DEMO_OUTPUTS = {
    "iron_deficiency": {...},     # Scenario B
    "metabolic_syndrome": {...},  # Scenario A
    "biotin_interference": {...}, # Scenario C
    "hemolysis_artifact": {...},  # Scenario D
}
```

WEARABLE CONTEXT FORMATTER (wearable_context.py):

Format wearable data for the prompt, respecting token budget:
- If no wearable data: "No wearable data connected." (6 tokens)
- If data available: summary stats only, no daily breakdown
  "Resting HR: {avg} bpm ({trend}), Sleep: {avg_h}h ({quality})"

Flag patterns with wearable relevance:
- Iron deficiency + elevated resting HR → "potentially symptomatic (compensatory tachycardia)"
- Hypothyroid pattern + low HRV + bradycardia → "potentially symptomatic"
- Metabolic pattern + poor sleep + low activity → "lifestyle factors may be contributing"

ACCEPTANCE CRITERIA:
- LLM output is valid JSON 100% of the time (GBNF grammar guarantees it)
- All clinical claims in output cite at least one source
- Full prompt fits within 4000 tokens (verify with tokenizer)
- Severity assignments are clinically appropriate (validated by medical student)
- Pre-cached demo outputs are loaded and available at startup
- Demo mode switch takes < 1 second (no LLM call — serves cached JSON)
- LLM call completes in < 15 seconds on laptop hardware
```

---

## Module F: Dashboard UI

**Depends on:** AnalysisOutput JSON schema (can start with mock data immediately)
**Owner skills:** React, TypeScript, Tailwind CSS, D3.js
**Files to create:**
- `frontend/src/types/index.ts` — TypeScript interfaces matching backend schemas
- `frontend/src/pages/Upload.tsx` — Two-step upload (file first, context second)
- `frontend/src/pages/Dashboard.tsx` — Main results dashboard with progressive rendering
- `frontend/src/components/Dashboard/PatternCard.tsx` — Individual pattern card
- `frontend/src/components/Dashboard/SeverityBadge.tsx` — Warning/Caution/Advisory badge
- `frontend/src/components/Dashboard/ProgressIndicator.tsx` — Pipeline stage progress
- `frontend/src/components/PatternDetail/PatternDetail.tsx` — Expanded pattern view
- `frontend/src/components/NetworkGraph/NetworkGraph.tsx` — Simplified network vis (static layout Plan A, D3 force Plan B)
- `frontend/src/components/VerificationAlerts/VerificationAlerts.tsx` — Error/drug warnings
- `frontend/src/components/DoctorQuestions/DoctorQuestions.tsx` — Generated questions
- `frontend/src/components/DemoMode/DemoMode.tsx` — One-click demo scenario loader
- `frontend/src/components/ClearData/ClearData.tsx` — Wipe all stored data
- `frontend/src/hooks/useApi.ts` — API hooks with progressive stage subscription
- `frontend/src/hooks/useDemo.ts` — Pre-cached demo output loader
- `frontend/package.json`

### Implementation Instructions

```
Build a mobile-first React dashboard for blood test analysis results.

KEY UX PRINCIPLES:
- TWO-STEP UPLOAD: Step 1 = upload PDF → immediate OCR results (5s). Step 2 = optional
  "Add medications and wearable to enhance your analysis." Never block the user.
- PROGRESSIVE RENDERING: Dashboard populates as each pipeline stage completes.
  Biomarkers appear after OCR. Flags appear after verification. Patterns appear
  after RAG+LLM. The user never stares at a single spinner for 20+ seconds.
- DEMO MODE: Prominent "View Example" button on the upload page. Loads a pre-cached
  scenario instantly. Available at all times — critical for judges.
- CLEAR DATA: "Clear All Data" button in the header. Wipes everything from SQLite
  and resets the UI. Essential for privacy demonstration.

TECH STACK:
- React 18+ with TypeScript
- Tailwind CSS for styling
- D3.js (or vis.js) for network visualization
- Framer Motion for subtle animations/transitions

MOCK DATA FOR DEVELOPMENT:
Start developing with this mock AnalysisOutput JSON while the backend is being built:

{
  "summary": "Your blood test shows a pattern consistent with low iron stores, possibly affecting your blood count. Your smartwatch data suggests your body may be compensating for this.",
  "patterns": [
    {
      "name": "Low Iron Pattern",
      "severity": "CAUTION",
      "confidence": "HIGH",
      "explanation": "Your ferritin (iron stores) is very low at 12 ng/mL, which has led to smaller red blood cells (low MCV) and mildly reduced hemoglobin. This pattern is consistent with iron deficiency.",
      "symptomatic_note": "Your resting heart rate has been trending upward over the past month (from 68 to 76 bpm), which may be your heart working harder to deliver oxygen with fewer red blood cells.",
      "supporting_markers": ["Ferritin: 12 ng/mL (Low)", "MCV: 78 fL (Low)", "Hemoglobin: 11.2 g/dL (Low)", "Iron: 35 µg/dL (Low)"],
      "citations": ["Wallach's Interpretation of Diagnostic Tests, Ch. 3: Iron Deficiency Anemia"],
      "doctor_questions": [
        "Based on my ferritin of 12, what is the best iron supplementation strategy for me?",
        "Should we investigate the cause of my iron deficiency (diet, absorption, blood loss)?",
        "How soon should I re-test to check if treatment is working?"
      ]
    },
    {
      "name": "Vitamin D Below Optimal",
      "severity": "ADVISORY",
      "confidence": "HIGH",
      "explanation": "Your Vitamin D is 18 ng/mL, which is below the optimal range of 30-100. While not critically low, this level is associated with reduced calcium absorption and may affect bone health over time.",
      "symptomatic_note": null,
      "supporting_markers": ["Vitamin D: 18 ng/mL (Low)"],
      "citations": ["Wallach's Interpretation of Diagnostic Tests, Ch. 15: Vitamin D"],
      "doctor_questions": [
        "What Vitamin D supplementation dose would you recommend for my level of 18 ng/mL?",
        "Should I also have my calcium and PTH levels checked?"
      ]
    }
  ],
  "verification_alerts": [],
  "disclaimer": "This is not a medical diagnosis. All identified patterns should be discussed with your healthcare provider."
}

DESIGN REQUIREMENTS:

COLOR PALETTE (Aviation-inspired):
- WARNING: #DC2626 (red-600) — needs urgent attention
- CAUTION: #D97706 (amber-600) — needs follow-up
- ADVISORY: #2563EB (blue-600) — awareness/lifestyle
- Normal/In-Range: #16A34A (green-600)
- Background: White or very light gray (#F9FAFB)
- Text: #111827 (gray-900) for primary, #6B7280 (gray-500) for secondary

PAGES TO BUILD:

1. UPLOAD PAGE (Upload.tsx) — TWO-STEP FLOW:
   - STEP 1: Large drag-and-drop zone for PDF/image upload. "Or take a photo" (mobile).
     Upload triggers OCR immediately. Results appear below within ~5 seconds.
   - STEP 2 (optional, shown after OCR completes): "Enhance your analysis" panel with:
     a) Medication/supplement checklist
     b) Wearable connect button
     c) "Analyze" button (runs verification + RAG + LLM)
   - Demo Mode button: "View Example" — loads a pre-cached scenario instantly.
     Always visible in the header. Critical for judge demos.
   - Clear Data button: in header. Wipes all stored data, resets UI.
   - ProgressIndicator component: shows pipeline stages as they complete.
     "Reading report... ✓" → "Checking for errors... ◌" → etc.

2. DASHBOARD PAGE (Dashboard.tsx) — PROGRESSIVE RENDERING:
   - Subscribes to pipeline stage events via API (or polling).
   - As each stage completes, the relevant section appears:
     - After OCR: show extracted biomarkers table
     - After Verification: show verification flags
     - After RAG+LLM: show pattern cards + doctor questions
   - This is the main results view — NOT a table of 40 biomarkers.
   - Top: Summary statement (1-2 sentences). Appears after LLM completes.
   - Main area: Pattern cards, sorted by severity (WARNINGs first).
   - After patterns: Verification alerts panel (if any flags).
   - Bottom: "View All Biomarkers" expandable section.
   - Disclaimer footer always visible.

3. PATTERN CARD (PatternCard.tsx):
   - Collapsed state:
     - SeverityBadge on the left
     - Pattern name (large, patient-friendly)
     - Confidence indicator (small pill: "High Confidence" / "Moderate" / "Low")
     - "Symptomatic" tag (with heart/pulse icon) if wearable data correlates
     - Expand chevron
   - Expanded state:
     - Explanation text
     - Supporting biomarkers list (with values and reference ranges — mini bar charts)
     - Source citations (expandable accordion — shows full source reference)
     - Doctor questions (numbered list, copy button for each)
     - "What affects this" — medication/lifestyle notes if relevant

4. SEVERITY BADGE (SeverityBadge.tsx):
   - WARNING: Red circle with "!" icon, pulsing subtle animation
   - CAUTION: Amber triangle with "!" icon
   - ADVISORY: Blue circle with "i" icon
   - Each has a text label
   - Accessible: uses aria-label and role="status"

5. NETWORK GRAPH (NetworkGraph.tsx) — TWO APPROACHES:
   - PLAN A (build first): Simplified chord diagram or hive plot. Static layout showing
     organ system clusters with biomarker nodes. No force simulation. Works reliably
     on mobile. Use vis.js or a simple SVG chart.
   - PLAN B (stretch): Interactive D3.js force-directed graph as originally specified.
     Only if time permits and Plan A is complete.
   - Regardless of approach: nodes = biomarkers, color = severity, size = deviation.
   - Accessible: always provide a table alternative view (toggle button).

6. DEMO MODE (DemoMode.tsx):
   - "View Example" button in the header, visible at all times.
   - Dropdown or tabs: "Iron Deficiency", "Metabolic Syndrome", "Biotin Interference",
     "Hemolysis Artifact", "All Normal".
   - Selecting a scenario instantly loads the pre-cached JSON (no API calls,
     no waiting). Renders exactly like a real analysis result.
   - Banner: "This is a demonstration scenario" to distinguish from real uploads.

7. CLEAR DATA (ClearData.tsx):
   - Button in the header (trash/wipe icon).
   - Confirmation dialog: "Delete all uploaded reports and analysis results?"
   - On confirm: POST /api/clear → wipes SQLite. Resets all UI state.
   - Demonstrates the privacy-first architecture.

8. VERIFICATION ALERTS (VerificationAlerts.tsx):
   - Only shown if there are quality_flags or drug_interferences
   - Yellow/amber warning-style box
   - Lists each flag with:
     - Type icon (hemolysis = blood drop, drug = pill, plausibility = scale)
     - Human-readable description
     - Recommendation (e.g., "Consider repeat testing")
   - "These flags suggest some results may be unreliable. Review before acting."

7. DOCTOR QUESTIONS (DoctorQuestions.tsx):
   - "Questions for Your Doctor" heading
   - Numbered list of generated questions
   - Each question has a copy button (clipboard icon)
   - "Copy All Questions" button at bottom
   - "Share Summary" button (generates a shareable text summary)

RESPONSIVE BREAKPOINTS:
- Mobile: 375px+ (single column, cards full width, graph simplified)
- Tablet: 768px+ (cards 2-column grid, full graph)
- Desktop: 1024px+ (sidebar layout: graph on left, patterns on right)

ACCESSIBILITY:
- All interactive elements are keyboard-navigable
- Severity is communicated by icon + text, not color alone
- Screen reader announcements for dynamic content (use aria-live)
- Focus management: focus moves to results after analysis completes
- All images/ icons have alt text

ACCEPTANCE CRITERIA:
- Dashboard renders correctly on mobile (375px), tablet (768px), and desktop (1440px)
- All pattern cards expand/collapse smoothly
- Network graph renders 40 nodes interactively without jank
- Colorblind users can distinguish severity levels (verify with grayscale mode)
- Keyboard users can navigate the entire dashboard
- Mock data displays correctly with all components
```

---

## Day 0 Prep (Before the 36-Hour Clock)

- [ ] Medical student: write original clinical pattern summaries (~30 conditions, paraphrased from Wallach + guidelines — not verbatim)
- [ ] Find/scan 5 test blood test PDFs (all 4 demo scenarios + one all-normal)
- [ ] Set up dev environments on all laptops
- [ ] Pre-download models: QVAC MedPsy 1.7B, all-MiniLM-L6-v2, ms-marco-MiniLM-L-6-v2
- [ ] Write 4 demo scripts (30-second plain-English summary per scenario)
- [ ] Prepare "before" mockups — what standard apps show (tables of red alerts)

## Implementation Order

### Phase 0 — Walking Skeleton (Hours 0-2)
**ALL AGENTS:** Hardcode one test case end-to-end before building ANY real module.
- Create shared Pydantic schemas
- Hardcode iron deficiency biomarkers → hardcode verification → hardcode RAG chunks
- Get LLM (with GBNF grammar) → Dashboard working with fake data
- **Deliverable:** Upload triggers pipeline → pattern cards appear on screen
- **Integration test cases defined and documented**

### Phase 1 (Parallel — Hours 2-12):
- **Agent 1:** Replace hardcoded OCR with real Tesseract pipeline + biomarker validation (Module A)
- **Agent 2:** Build two-step Upload page + medication checklist + wearable connect + DemoMode + ClearData (Module B + Module F frontend)
- **Agent 3:** Build Verification Layer + wearable backend (Module C + Module B backend)
- **After each module:** Run integration test suite. Fix regressions before proceeding.

### Phase 2 (Parallel — Hours 12-22):
- **Agent 4:** Build knowledge base + full RAG pipeline (Module D)
- **Agent 5:** Continue Dashboard components — PatternCard, PatternDetail, NetworkGraph Plan A, VerificationAlerts, DoctorQuestions (Module F)
- **Agent 6:** Finalize GBNF grammar + LLM prompts + pre-cached demo outputs (Module E)

### Phase 3 (Integration — Hours 22-28):
- Wire frontend to real backend API with progressive results streaming
- Replace hardcoded data with real pipeline outputs
- Run integration test suite fully
- Medical student validates clinical accuracy

### Phase 4 (Polish & Demo — Hours 28-36):
- Pre-cache all 4 demo scenario outputs
- Fix OCR edge cases
- Tune RAG relevance thresholds
- Polish UI (animations, transitions, responsive, loading states)
- Prepare "before/after" walkthrough for each scenario
- Dry-run full demo twice

---

## Integration Test Suite

Three reference cases defined at project start in Phase 0. Run after every module completion.

### Test Case 1: Iron Deficiency + Wearable (Priority: HIGH)
```python
INPUT = {
    "biomarkers": [
        {"name": "Ferritin", "value": 12, "unit": "ng/mL", "ref_low": 15, "ref_high": 150, "flag": "L"},
        {"name": "Iron", "value": 35, "unit": "µg/dL", "ref_low": 60, "ref_high": 170, "flag": "L"},
        {"name": "MCV", "value": 78, "unit": "fL", "ref_low": 80, "ref_high": 100, "flag": "L"},
        {"name": "Hemoglobin", "value": 11.2, "unit": "g/dL", "ref_low": 12, "ref_high": 16, "flag": "L"},
        # + 30 normal biomarkers
    ],
    "medications": [],
    "wearable": {"resting_hr_avg": 76, "resting_hr_trend": "rising_from_68"}
}
EXPECTED = {
    "rag_top_chunk": "iron_deficiency_anemia",  # NOT thalassemia, NOT ACD
    "pattern_count": 1,
    "severity": "CAUTION",
    "symptomatic_tag": True,  # elevated HR detected
    "doctor_questions_count": 3,
    "citations_present": True
}
```

### Test Case 2: Metabolic Syndrome Cluster (Priority: HIGH)
```python
INPUT = {
    "biomarkers": [
        {"name": "Glucose", "value": 108, "flag": "H"},
        {"name": "HDL", "value": 34, "flag": "L"},
        {"name": "Triglycerides", "value": 195, "flag": "H"},
        {"name": "ALT", "value": 48, "flag": "H"},
        {"name": "Uric Acid", "value": 7.8, "flag": "H"},
    ],
    "medications": [],
    "wearable": None
}
EXPECTED = {
    "rag_top_chunk": "metabolic_syndrome",  # groups all 5 together
    "pattern_count": 1,  # ONE pattern card, not 5 separate
    "severity": "CAUTION",
    "grouped_biomarkers": ["Glucose", "HDL", "Triglycerides", "ALT", "Uric Acid"]
}
```

### Test Case 3: All Normal (Priority: MEDIUM)
```python
INPUT = {"biomarkers": [/* all 35 biomarkers within reference ranges */]}
EXPECTED = {
    "fast_path_triggered": True,  # RAG skipped entirely
    "patterns": [],
    "summary_contains": "normal range"
}
```

---

## Environment Setup

```bash
# Backend dependencies
pip install fastapi uvicorn python-multipart pytesseract pdf2image pillow sentence-transformers lancedb ollama
# sentence-transformers includes the cross-encoder module for ms-marco-MiniLM-L-6-v2

# Frontend dependencies  
cd frontend && npm install react react-dom typescript tailwindcss @types/react d3 @types/d3 framer-motion

# Install Tesseract OCR
# Windows: download from https://github.com/UB-Mannheim/tesseract/wiki
# Mac: brew install tesseract tesseract-lang
# Linux: sudo apt install tesseract-ocr tesseract-ocr-heb

# Pull the local LLM model
ollama pull qvac-medpsy:1.7b  # or gemma2:2b as fallback
```

---

## Validation Checklist (Before Demo)

### Integration Tests
- [ ] Test Case 1 (Iron Deficiency): correct pattern retrieved, CAUTION severity, symptomatic tag, 3 doctor questions
- [ ] Test Case 2 (Metabolic Syndrome): 5 biomarkers grouped into 1 pattern card, not 5 separate alerts
- [ ] Test Case 3 (All Normal): fast path triggers, RAG skipped, "normal range" summary shown

### Feature Validation
- [ ] OCR correctly extracts >90% of biomarkers from a real blood test PDF
- [ ] OCR validation catches unrecognized biomarker names
- [ ] Drug interference detection catches biotin → abnormal TSH
- [ ] Hemolysis detection catches high K+ + normal kidney function
- [ ] RAG relevance threshold drops low-confidence chunks (test with out-of-knowledge-base pattern)
- [ ] Multi-label organ system filtering works (e.g., albumin searches both hepatic + nutritional)
- [ ] LLM output is valid JSON 100% of the time (GBNF grammar verified)
- [ ] LLM prompt fits within 4000 tokens (verified with tokenizer)
- [ ] LLM cites sources for all clinical claims
- [ ] Pre-cached demo outputs match expected schema and are served correctly

### UX Validation
- [ ] Two-step upload flow: OCR results appear before context input requested
- [ ] Progressive rendering: biomarkers → flags → patterns appear incrementally
- [ ] Demo mode: all 4 scenarios load instantly (<1 second)
- [ ] Clear Data: wipes everything and resets UI
- [ ] Severity hierarchy is visually obvious (WARNING red > CAUTION amber > ADVISORY blue)
- [ ] Network graph (Plan A) renders without jank on mobile
- [ ] All doctor questions are copyable
- [ ] Disclaimer appears on every screen with clinical content
- [ ] Mobile-responsive: 375px through 1440px

### Clinical Validation
- [ ] Medical student has validated clinical accuracy on all 4 scenarios + all-normal case
- [ ] Severity assignments match clinical reality
- [ ] Doctor questions are specific, actionable, and medically appropriate
- [ ] No alarming language in any output (post-filter verified)

### Demo Readiness
- [ ] Demo walkthrough script is prepared (30s per scenario)
- [ ] "Before/after" comparison slides ready (standard app vs. VERITAS)
- [ ] Pre-cached outputs verified for all 4 scenarios
- [ ] Live pipeline tested end-to-end with real blood test PDFs
- [ ] Fallback to cached mode tested (kill Ollama mid-demo, verify demo still works)
- [ ] Network monitor visible during demo (proving nothing leaves the device)
- [ ] Dry-run completed twice
