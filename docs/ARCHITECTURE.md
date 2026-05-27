# VERITAS — Architecture & Detailed Plan

## Context

**Hackathon theme:** BEYOND ALERTS — Design solutions that provide clarity and context to raw data, turning confusing alerts into verified facts.

**Problem:** Consumer blood test apps explain individual markers in plain English but fail at three things: (1) they don't verify whether results are trustworthy before explaining them, (2) they explain markers in isolation rather than recognizing clinical patterns, and (3) their AI-generated explanations lack verifiable citations, making them medically unreliable.

**Core metaphor:** A blood test is a sensor network from an industrial system (your body). Current apps treat it like a report card. We treat it like a control room — identifying patterns, suppressing false alarms, verifying signals, and escalating only what matters.

**Team:** 6 CS students (end of degree, broad skills) + 1 medical student.

**Key constraint:** All AI processing runs on-device (privacy as a feature). Target: laptop-grade device for demo.

---

## System Architecture

### Data Flow

```
[Blood Test PDF/Image]
        │
        ▼
┌──────────────────┐
│  1. OCR ENGINE   │  Tesseract (on-device)
│  Raw text →      │  Image preprocessing → OCR → regex extraction
│  structured JSON │  → structured biomarker data
│                   │  → VALIDATE against known biomarker names
└────────┬─────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│  2. CONTEXT      │     │  3. VERIFICATION │
│  COLLECTOR       │     │  LAYER           │
│  - Medications   │     │  - Hemolysis     │
│  - Supplements   │────→│  - Drug inter-   │
│  - Wearable data │     │    ference       │
│  (runs parallel  │     │  - Physiological │
│   with OCR)      │     │    plausibility  │
└──────────────────┘     │  - Corrected     │
                         │    values        │
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │  FAST PATH CHECK │
                         │  All normal? →   │
                         │  skip RAG, return│
                         │  "all clear"     │
                         └────────┬─────────┘
                                  │ (abnormal values present)
                                  ▼
┌──────────────────┐
│  4. RAG ENGINE   │
│  - Query rewriter│  LLM rewrites biomarkers → clinical query
│  - Metadata      │  Pre-filter by organ system (multi-label)
│    filter        │
│  - Hybrid search │  Semantic (0.7) + keyword (0.3) in LanceDB
│  - Cross-encoder │  ms-marco-MiniLM scores (query,chunk) pairs
│    re-ranker     │
│  - Relevance      │  Drop chunks below score threshold
│    threshold     │
│  - Citation       │  Every chunk has source metadata
│    tracker       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  5. LLM SYNTHESIS│
│  - GBNF grammar  │  Grammar-constrained → guaranteed valid JSON
│  - Token budget  │  Truncate chunks, only abnormal biomarkers
│  - System prompt │  Local LLM (QVAC MedPsy 1.7B via Ollama)
│  - Context        │  Input: verified results + RAG chunks + wearable
│    assembly      │
│  - JSON output   │  Output: patterns, severity, citations, questions
│  - Fallback       │  Pre-cached demo outputs available
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  6. DASHBOARD    │
│  - Progressive   │  Results appear as each stage completes
│    rendering     │
│  - Pattern cards │  React + TypeScript + Tailwind
│  - Network graph │  Simplified static layout (force sim as stretch)
│  - Doctor Qs     │  Aviation WARNING/CAUTION/ADVISORY hierarchy
│  - Demo mode     │  One-click pre-cached demo scenarios
│  - Clear data    │  Wipe all stored results
└──────────────────┘
```

### Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Tailwind CSS | Fast development, strong typing, utility-first CSS |
| **Visualization** | D3.js | Full control over interactive network graphs |
| **Animation** | Framer Motion | Lightweight, declarative animations |
| **OCR** | Tesseract (pytesseract + pdf2image) | On-device, no cloud, supports Hebrew |
| **Backend API** | Python FastAPI + Pydantic | Async, auto-docs, strong validation |
| **Vector DB** | LanceDB (embedded) | In-process, no server, columnar storage |
| **Embeddings** | all-MiniLM-L6-v2 / BGE-small | Small footprint, good retrieval quality |
| **Cross-Encoder** | ms-marco-MiniLM-L-6-v2 | Re-rank scoring, ~90MB, ~200ms per chunk pair |
| **Local LLM** | Ollama + QVAC MedPsy 1.7B (GGUF) | Medical-specific, ~1.2GB, outperforms 27B models |
| **LLM Fallback** | Gemma 2B | Well-tested on-device, 99.1% clinical accuracy |
| **Wearable** | Apple HealthKit / Google Health Connect | Standard APIs, optional for demo |
| **Storage** | SQLite | Embedded, no external DB needed |

### Why LanceDB

LanceDB runs in-process (no separate server), stores vectors in Lance columnar format, supports ANN search with IVF-PQ, and handles metadata filtering natively. Critical for an on-device architecture where every component must run locally.

### Why On-Device LLM

Tether's QVAC MedPsy 1.7B (released May 2026) outperforms Google's MedGemma-27B (16x larger) on HealthBench benchmarks while running in ~1.2GB Q4_K_M GGUF format — small enough for a laptop with 8GB RAM. Arm demonstrated Gemma 2B running offline on Android with 99.1% physician-validated clinical accuracy and 22 tokens/sec. On-device medical AI is no longer aspirational.

---

## Component Details

### Component 1: OCR Pipeline
**Owner:** 1 CS student
**Input:** PDF or image of blood test
**Output:** `{biomarkers: [{name, value, unit, ref_low, ref_high, flag}], raw_text, parse_confidence}`

**Processing steps:**
1. If PDF → convert page 1 to image (PyMuPDF or pdf2image)
2. Preprocess: grayscale, contrast stretch, binarization, deskew
3. Tesseract OCR with eng+heb language packs
4. Structured extraction via regex patterns matching common blood test formats
5. Handle 3 common layouts: column-aligned with flags, parenthetical ranges, tabular whitespace-delimited

**Edge cases:** Hebrew RTL reports, missing reference ranges, handwritten notes, non-standard biomarker names.

**Validation step:** After extraction, check each biomarker name against the known biomarker list (from the organ system map). Flag unrecognized names. If < 50% of extracted names are recognized, warn the user: "This report format may not be fully supported. Please verify the extracted values."

### Component 2: Context Collector
**Owner:** 1 CS student
**Input:** User interaction + wearable API (runs in parallel with OCR)
**Output:** `{medications: [...], supplements: [...], wearable: {...}}`

**Medication input:** Searchable checklist of top 20 interfering drugs/supplements + free-text input. Shown AFTER OCR completes (two-step flow: upload first → see biomarkers → optionally add context to enhance analysis).

**Wearable data:** Apple Health (export.xml parse) or Google Health Connect API. Fallback: realistic mock data with selectable scenarios (anemic_tachycardia, healthy, stressed, athlete).

### Component 3: Verification Layer
**Owner:** Medical student + 1 CS student
**Input:** Biomarker data + medications/supplements
**Output:** VerificationOutput with verified results, drug interferences, corrected values, quality flags

**Sub-modules:**
- **Hemolysis detection:** K+/eGFR mismatch, extreme K+, LDH/AST pattern, very low glucose
- **Drug interference:** Lookup table of 10 drug categories → affected biomarkers with recommendations
- **Physiological plausibility:** Ca/Albumin, BUN/Cr ratio, AST/ALT ratio, TSH/FT4 consistency, anion gap
- **Corrected values:** Corrected calcium, anion gap, LDL (Friedewald), corrected sodium for hyperglycemia

### Component 4: RAG Engine
**Owner:** 2 CS students
**Input:** Verified biomarker results
**Output:** Ranked clinical patterns with citations

**Pipeline (5 stages):**
0. **Fast path check** — If all biomarkers are within reference ranges AND no verification flags fired, skip RAG entirely. Return: `{"summary": "All results in normal range.", "patterns": [], "verification_alerts": []}` (~0ms)
1. **Query rewriting** — LLM Pass 1 transforms raw biomarker list into a retrieval-optimized clinical query with pattern name hypotheses, severity descriptors, and differential diagnoses (~3 sec)
2. **Metadata-filtered retrieval** — Pre-filter LanceDB by inferred organ system(s) using multi-label mapping (a biomarker can belong to multiple systems — e.g., albumin is both hepatic and nutritional), then hybrid search (0.7 semantic + 0.3 keyword) within the filtered set (~100ms)
3. **Cross-encoder re-ranking** — ms-marco-MiniLM-L-6-v2 (~90MB) scores each (query, chunk) pair directly. Drop chunks below minimum score threshold (0.3) to prevent returning irrelevant patterns when the knowledge base doesn't contain the user's condition (~1 sec for 15 chunks)
4. **Citation tracking** — Each chunk carries source, chapter, chunk_id metadata. If no chunks pass the relevance threshold, return: "No matching clinical pattern found. Here are your individual abnormal values to discuss with your doctor."
5. **LLM synthesis** — Pass 2 receives top-5 re-ranked chunks (max 300 words each to fit context window) and generates the final structured JSON output using grammar-constrained generation (GBNF) for guaranteed valid JSON

**Knowledge base:** Wallach's Interpretation of Diagnostic Tests + selected clinical guidelines (AHA lipids, Endocrine Society thyroid, AASLD liver, KDIGO kidney). Chunked by clinical condition, not arbitrary token count. Metadata includes organ_system for pre-filtering.

**Why this pipeline over naive retrieval:** Naive embedding search alone would miss chunks that describe the same clinical pattern using different terminology (e.g., "microcytic hypochromic anemia" vs. "low MCV, low MCH"). Query rewriting adds clinical framing. Metadata filtering eliminates irrelevant organ systems. Cross-encoder re-ranking captures semantic relevance the embedding model might miss.

### Component 5: LLM Synthesis
**Owner:** 1 CS student (prompt engineering)
**Input:** Verified results + RAG chunks + wearable context
**Output:** Structured JSON with patterns, severity, citations, doctor questions

**Key design decisions:**
- **Grammar-constrained generation:** Use GBNF (GGML BNF) grammar with Ollama to force valid JSON output. The grammar defines the exact AnalysisOutput schema. No retry-on-parse-failure needed — invalid JSON is structurally impossible (~20-line .gbnf file).
- **Token budget:** The 1.7B model has a 4K-8K context window. Truncate RAG chunks to 300 words max each. Only include abnormal biomarkers in the prompt (normal ones skipped). This guarantees the prompt fits in ~3500 tokens.
- **"No diagnosis" disclaimer:** Enforced in system prompt. Output filtered post-generation for alarming language (e.g., "liver failure" → "elevated liver enzymes").
- **Fallback:** Pre-cached demo outputs for 4 scenarios. If live LLM fails during demo, switch to cached with one click.

### Component 6: Dashboard UI
**Owner:** 2 CS students
**Input:** AnalysisOutput JSON
**Output:** Interactive React dashboard

**Views:**
- **Two-step upload flow:** Step 1 — drag-and-drop PDF → immediate OCR results shown (5s). Step 2 — optional "Add medications and wearable data to enhance your analysis." Reduces upfront friction.
- Pattern dashboard with severity-badged cards (not a table of 40 results). Populates progressively as each pipeline stage completes.
- Pattern detail with explanation, citations, doctor questions
- Simplified network visualization (static chord diagram or hive plot as Plan A; D3.js force simulation as stretch)
- Verification alerts panel
- **Demo mode:** One-click button loads a pre-analyzed sample report. Available at all times. Pre-cached JSON outputs for all 4 scenarios.
- **Clear All Data button:** Prominently placed. Wipes all uploaded reports, extracted biomarkers, and analysis results from SQLite.

**Progressive rendering:** The dashboard subscribes to pipeline stage completions. As soon as OCR finishes → biomarkers are displayed. As soon as verification finishes → flags appear. As soon as RAG+LLM finish → pattern cards populate. The user never stares at a single spinner for 20+ seconds.

**Design system:** Aviation-inspired Warning/Caution/Advisory color hierarchy. Progressive disclosure. Mobile-first, WCAG AA accessible.

---

## RAG Pipeline Detail

The retrieval pipeline uses two LLM passes: one before retrieval (query rewriting) and one after (synthesis). This is a state-of-the-art pattern adapted for on-device constraints.

### Stage 1: Query Rewriting (LLM Pass 1)

**Why:** Raw biomarker lists make poor retrieval queries. `"ferritin 12, MCV 78, hemoglobin 11.2"` doesn't capture clinical intent. Clinical patterns are described in textbooks with diagnostic framing, not as bare lists.

**What happens:** A quick LLM call transforms the raw abnormal biomarker list into a retrieval-optimized clinical query:

```
Input:  "Abnormal: ferritin 12 (low), MCV 78 (low), hemoglobin 11.2 (low)"

Output: "Microcytic anemia pattern with severely depleted iron stores
         (ferritin 12 ng/mL), microcytosis (MCV 78 fL), and mild anemia
         (hemoglobin 11.2 g/dL). Differential diagnoses to consider:
         iron deficiency anemia, anemia of chronic disease, thalassemia trait."
```

**Latency:** ~3 seconds. This is the single biggest retrieval quality improvement per unit of cost.

### Stage 2: Metadata-Filtered Hybrid Search

**Why:** Searching all chunks equally means an iron deficiency query wastes embedding similarity on thyroid, liver, and renal chunks. LanceDB supports native metadata filtering — we should use it.

**What happens:**
1. Infer relevant organ systems from abnormal biomarkers (e.g., ferritin + MCV + hemoglobin → `["hematologic"]`)
2. Pre-filter LanceDB: only search chunks where `organ_system IN ["hematologic"]`
3. Within filtered set: hybrid search (0.7 semantic similarity + 0.3 keyword match)
4. Retrieve top-15 matches

**Latency:** ~100ms. Metadata filtering is free — LanceDB pushes it to the index.

### Stage 3: Cross-Encoder Re-Ranking

**Why:** Bi-encoder (embedding) similarity is approximate — embeddings are compressed representations. A chunk about "microcytic hypochromic anemia" might score lower than one about "anemia of chronic disease" simply because of embedding noise, even though the user's pattern is iron deficiency. A cross-encoder reads the full (query, chunk) pair together.

**What happens:** `ms-marco-MiniLM-L-6-v2` (~90MB) scores each of the 15 retrieved chunks against the rewritten clinical query. Each (query, chunk) pair is fed through the model. The top-5 highest-scoring chunks proceed to synthesis.

**Latency:** ~1 second for 15 chunks. The 90MB model loads once and scores each pair in a batch.

### Stage 4: Citation Tracking

Each top-5 chunk carries immutable metadata: `chunk_id`, `source`, `chapter`, `pattern_name`, `relevance_score`. The synthesis LLM must cite `chunk_id` in every clinical claim. The frontend resolves chunk_ids to human-readable citations.

### Stage 5: LLM Synthesis (Pass 2)

The top-5 chunks are formatted into the synthesis prompt with citation IDs. The LLM groups biomarkers into patterns, assigns severity, generates doctor questions, and cites sources. Output is structured JSON.

### Total Latency Budget

| Stage | Time |
|---|---|
| Query rewriting (LLM Pass 1) | ~3 sec |
| Metadata-filtered hybrid search | ~0.1 sec |
| Cross-encoder re-rank | ~1 sec |
| LLM synthesis (Pass 2) | ~12 sec |
| **Total** | **~16 sec** |

### Design Decisions

| Decision | Rationale |
|---|---|
| Two LLM passes, not one | Query rewriting improves retrieval so much that it pays for its own latency by giving the synthesis pass better input |
| Cross-encoder, not heuristic re-rank | Heuristic biomarker-overlap counting misses semantically relevant chunks; cross-encoder reads full text |
| Metadata pre-filtering | LanceDB supports it natively; eliminates irrelevant organ systems at zero cost |
| Top-15 → top-5 | 15 gives the cross-encoder enough candidates; 5 keeps the synthesis prompt compact for a 1.7B model |
| No relevance filtering (stretch) | Could add a third LLM pass to check each chunk's relevance before synthesis, but adds ~2-3 sec |

### Stage Timing & Reliability

**Timeouts per stage:**
| Stage | Timeout |
|---|---|
| OCR | 15 sec |
| Query rewriting (LLM Pass 1) | 10 sec |
| Hybrid search | 2 sec |
| Cross-encoder re-rank | 5 sec |
| LLM synthesis (Pass 2) | 30 sec |

If any stage times out, the pipeline degrades gracefully: show whatever results are available up to that point, with a clear note about what couldn't be completed.

**LLM health check at startup:** On application start, ping Ollama, confirm the model loads, run a test inference. If the LLM is unavailable, show a clear error message (not a hung spinner).

**Degraded modes:**
- LLM unavailable → show verification results + raw biomarker list (still useful)
- RAG returns no relevant chunks → show verification results + "No matching patterns found. Discuss these individual values with your doctor."
- OCR fails → "Unable to read this report. Please try a clearer photo or enter values manually."

### What We Intentionally Skipped

- **Graph RAG** — biomarker relationship knowledge graph guiding retrieval. Powerful but complex to build. Mention as future direction.
- **ColBERT / token-level embeddings** — would improve medical term matching but models are too heavy for on-device.
- **SourceCheckup citation verification** — post-generation verification of every claim against its cited chunk. Important for production, too heavy for hackathon scope.
- **Agentic multi-hop** — "retrieve anemia → retrieve supplementation → retrieve follow-up testing." Adds latency and complexity.

---

## Mobile Deployment Path

The current architecture uses Ollama (local HTTP server) for convenience during development. For production mobile deployment, the same GGUF models run directly via:

- **llama.cpp** (C++ core, Swift/Kotlin bindings) — no HTTP server, true on-device. Same QVAC MedPsy GGUF model works without modification.
- **MLC LLM** — purpose-built for mobile GPU inference (Metal on iOS, Vulkan on Android). Better performance on mobile hardware.

The rest of the pipeline (LanceDB, sentence-transformers, FastAPI) can be packaged into a mobile app using the same embedded architecture. For the hackathon demo: Ollama on laptop is the target. Mobile is the stated production path.

---

## API Contracts

### POST /api/ocr
```
Request: multipart/form-data {file}
Response: {biomarkers: [{name, value, unit, ref_low, ref_high, flag}], raw_text, parse_confidence}
```

### POST /api/verify
```
Request: {biomarkers, medications, supplements}
Response: {verified_results, drug_interferences, corrected_values, quality_flags}
```

### POST /api/analyze
```
Request: {verified_results, wearable_context, medications}
Response: {summary, patterns: [{name, severity, confidence, explanation, citations, doctor_questions}], verification_alerts, disclaimer}
```

---

## Day 0 Prep (Before the 36-Hour Clock)

- [ ] Medical student: prepare paraphrased clinical pattern summaries for ~30 conditions (sourced from Wallach + guidelines, not verbatim copies — avoids copyright issues)
- [ ] Find/scan 5 test blood test PDFs covering all 4 demo scenarios + one all-normal
- [ ] Set up development environments on all laptops (Python, Node, Tesseract, Ollama)
- [ ] Pre-download all models: QVAC MedPsy 1.7B, all-MiniLM-L6-v2, ms-marco-MiniLM-L-6-v2
- [ ] Write the 4 demo scripts (30-second plain-English summary per scenario)
- [ ] Prepare "before" mockups — what a standard app shows for each scenario (screenshots of tables full of red alerts)

## Implementation Phases

### Phase 1 — Walking Skeleton (Hours 0-2)
**Goal:** Full pipeline working with hardcoded data. Integration from the start.
- Create shared Pydantic schemas
- Hardcode one test case (iron deficiency biomarkers)
- Hardcode verification output
- Hardcode RAG chunks
- Get LLM → Dashboard working end-to-end
- **Deliverable:** Upload a fake report → see pattern cards on screen

### Phase 2 — Real Modules, One at a Time (Hours 2-16)
Replace each hardcoded piece with real implementation:
- Build OCR pipeline (Tesseract + regex + biomarker validation)
- Build Context Collector (medication UI, wearable connector, mock fallback)
- Implement Verification Layer (all 4 sub-modules)
- Build Knowledge Base (chunk + embed + LanceDB)
- **After each module:** Run integration test suite (3 reference cases). Fix regressions before moving on.
- **Deliverable:** Upload a real blood test PDF → get verified, structured data

### Phase 3 — RAG + LLM + Dashboard (Hours 16-28)
- Implement RAG pipeline (query rewriting → metadata-filtered search → cross-encoder → citations)
- Write GBNF grammar for guaranteed JSON output
- Finalize LLM prompts (iterate with medical student)
- Build dashboard components (progressive rendering, two-step upload, demo mode, clear data)
- Build simplified network visualization
- Integrate frontend ↔ backend with progressive results streaming
- **Deliverable:** Full end-to-end flow working with real blood test PDFs

### Phase 4 — Polish, Test, Demo Prep (Hours 28-36)
- Medical student validates clinical accuracy on all 4 scenarios
- Run integration test suite one final time
- Pre-cache LLM outputs for all 4 demo scenarios
- Fix OCR edge cases for different report formats
- Tune RAG relevance thresholds
- Polish UI (animations, transitions, responsive, loading states)
- Prepare "before/after" demo walkthrough
- Dry-run the full demo twice
- **Deliverable:** Demo-ready application with fallback insurance

---

## Demo Scenarios

1. **Iron deficiency + wearable correlation:** Low ferritin/iron/MCV/Hb + elevated resting HR from smartwatch. Shows parent-child grouping and "symptomatic" tag.
2. **Metabolic syndrome cluster:** Elevated glucose + low HDL + high triglycerides + borderline ALT + elevated uric acid → one pattern card, not five separate alerts.
3. **Biotin interference:** Abnormal TSH + normal FT4 + user taking biotin. System flags drug interference before clinical interpretation.
4. **Hemolysis artifact:** Very high K+ + normal kidney function. System detects inconsistency, suggests possible collection error.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| OCR fails on Hebrew reports | Focus on English reports for demo; Hebrew as stretch goal |
| LLM too slow or unavailable | 1.7B Q4 quantization; Gemma 2B fallback; health check at startup; pre-cached demo outputs as ultimate fallback |
| RAG retrieves wrong content | Medical student validates retrieval; cross-encoder re-ranking; relevance threshold drops low-confidence chunks |
| LLM produces malformed JSON | GBNF grammar-constrained generation — invalid JSON is structurally impossible |
| Context window overflow | Token budget: truncate chunks to 300 words, only include abnormal biomarkers in prompt |
| Scope creep, nothing polished | Hard priority: Pattern Cards > Verification > Doctor Questions > Network Graph |
| LLM hallucinates clinical claims | Citation requirement in prompt; medical student review; GBNF forces citation fields |
| Wearable API access issues | Mock data fallback with 4 realistic scenarios |
| Wallach copyright concerns | Medical student writes original pattern summaries (not verbatim excerpts) |
| Demo fails due to live LLM issue | Pre-cached JSON outputs for all 4 scenarios; one-click switch to cached mode |
| Integration breaks in final hours | Walking skeleton from Hour 2; integration test suite run after every module |

---

## File Structure

```
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Upload/          # File upload, medication checklist
│   │   │   ├── Dashboard/       # Pattern cards, severity badges
│   │   │   ├── PatternDetail/   # Expanded pattern view
│   │   │   ├── NetworkGraph/    # D3.js interactive graph
│   │   │   ├── VerificationAlerts/ # Error/drug warning panel
│   │   │   └── DoctorQuestions/ # Generated questions display
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── types/
│   ├── package.json
│   └── tsconfig.json
├── backend/
│   ├── api/
│   │   ├── routes/              # FastAPI route handlers
│   │   └── models/              # Pydantic schemas
│   ├── ocr/                     # Tesseract + extraction
│   ├── verification/            # Rules engine (4 sub-modules)
│   ├── rag/                     # Embeddings, retrieval, reranking
│   ├── llm/                     # Prompts, synthesis, parsing
│   └── wearable/                # Health data connectors
├── knowledge-base/
│   ├── raw/                     # Source texts
│   ├── build_kb.py              # Chunking + embedding + LanceDB load
│   └── test_queries.py          # Retrieval quality testing
├── docs/
│   ├── FOR_TEAMMATES.md         # Medical context for CS students
│   ├── FOR_TEAMMATES.html       # Designed HTML version
│   ├── ARCHITECTURE.md          # This document
│   ├── AGENT_PLAN.md            # AI agent implementation guide
│   └── DESIGN_SPEC.md           # UI requirements for designers
└── README.md
```

---

## Integration Test Suite

Three reference test cases defined at project start. Run after every module completion.

### Test Case 1: Iron Deficiency + Wearable
- **Input:** ferritin 12, iron 35, MCV 78, hemoglobin 11.2 (all other values normal)
- **Wearable:** resting HR 76 (trending up from 68 over 30 days)
- **Expected OCR:** All 4 biomarkers extracted correctly
- **Expected Verification:** No hemolysis flags, no drug interferences
- **Expected RAG:** Top chunk = iron deficiency anemia (not thalassemia, not ACD)
- **Expected LLM:** Pattern "Low Iron Pattern", severity CAUTION, "potentially symptomatic" tag, 3 doctor questions, Wallach Ch.3 citation
- **Run time:** After Modules 3, 4, 5 completed

### Test Case 2: Metabolic Syndrome Cluster
- **Input:** glucose 108, HDL 34, triglycerides 195, ALT 48, uric acid 7.8 (all other values normal)
- **Wearable:** none
- **Expected OCR:** All 5 biomarkers extracted
- **Expected Verification:** No flags (plausible pattern)
- **Expected RAG:** Top chunk = metabolic syndrome / insulin resistance
- **Expected LLM:** Single "Metabolic Pattern" card, severity CAUTION, groups all 5 biomarkers, 3 doctor questions
- **Run time:** After Modules 3, 4, 5 completed

### Test Case 3: All Normal
- **Input:** All 35 biomarkers within reference ranges
- **Wearable:** none
- **Expected:** Fast path triggers — RAG skipped entirely. Returns "All results in normal range." Dashboard shows green summary, no pattern cards.
- **Run time:** After Module 3 completed

## Verification Plan

1. **Unit:** Each verification rule has a test case (high K+ + normal Cr → flag hemolysis)
2. **RAG quality:** Integration test cases 1 & 2 — does retrieval return correct chunks?
3. **LLM output:** Medical student reviews outputs for clinical accuracy, citations, severity
4. **OCR accuracy:** 5 different blood test formats from different labs
5. **E2E:** Upload PDF → dashboard shows correct patterns with correct severity and traceable citations
6. **Edge cases:** All-normal results (Test Case 3), single isolated abnormality, extreme values (possible artifacts)
7. **Degraded modes:** Kill Ollama mid-pipeline → does dashboard show verification results + error message?
8. **Grammar:** Intentionally malformed LLM output → does GBNF prevent it? (it should)
