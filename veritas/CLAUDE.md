# VERITAS — Hackathon Project

## What We're Building

A privacy-first, on-device blood test analyzer that transforms raw lab results into verified clinical intelligence. Instead of explaining 40 biomarkers individually (like every existing app), we:

1. **Verify before explaining** — detect pre-analytical errors (hemolysis, drug interference, physiological impossibilities) so users know if results are trustworthy
2. **Recognize clinical patterns** — group related biomarkers using SIEM-style event correlation (parent-child suppression from SCADA)
3. **Assign real urgency** — Aviation-style Warning/Caution/Advisory hierarchy instead of marking everything red
4. **Cite every claim** — RAG against Wallach's Interpretation of Diagnostic Tests so assertions trace back to medical literature
5. **Generate doctor questions** — for each pattern, generate specific questions the user should ask their doctor. This bridges "I see something" to "I know what to do about it." Oracle is adding this to hospital portals in 2026; no consumer app has it.
6. **Run entirely on-device** — local LLM (QVAC MedPsy 1.7B via Ollama), embedded vector DB (LanceDB), no cloud
7. **Guarantee valid JSON** — GBNF grammar-constrained generation eliminates LLM parse failures. Output is always valid.
8. **Degrade gracefully** — if any stage fails, show partial results rather than nothing. Pre-cached demo outputs as ultimate fallback.
9. **Respect the user's time** — progressive rendering: biomarkers appear after OCR, flags after verification, patterns after RAG. No 22-second spinner.

**Mobile path:** Ollama for hackathon laptop demo. Production: same GGUF models run via llama.cpp (no HTTP server) on iOS/Android.

The core metaphor: a blood test is a sensor network from an industrial system. Current apps treat it like a report card. We treat it like a control room.

## Team & Constraints

- 6 CS students (end of degree, broad skills) + 1 medical student
- All AI processing on-device (privacy as a feature)
- Single blood test snapshot must be useful (can't rely on longitudinal data)
- Demo target: laptop-grade hardware, 36-hour build window
- Medical student handles clinical validation; CS team doesn't need medical knowledge

## Key Files

| File | Purpose | Read When |
|---|---|---|
| `docs/FOR_TEAMMATES.md` | Medical concepts explained for CS people | New to the project |
| `docs/ARCHITECTURE.md` | Full system design, API contracts, data flow | Need the big picture |
| `docs/AGENT_PLAN.md` | Module specs, implementation prompts, dependency graph | Starting to code |
| `docs/DESIGN_SPEC.md` | Page requirements, elements, states, data shapes | Designing the UI |
| `README.md` | Quick overview and setup commands | Setting up environment |

## Project Structure

```
veritas/
├── frontend/           # React + TypeScript + Tailwind + D3.js
│   └── src/
│       ├── components/ # Dashboard, Upload, PatternDetail, NetworkGraph, etc.
│       ├── pages/      # Upload.tsx, Dashboard.tsx
│       ├── hooks/      # API hooks, state management
│       └── types/      # TypeScript interfaces
├── backend/            # Python FastAPI
│   ├── api/routes/     # /api/ocr, /api/verify, /api/analyze
│   ├── api/models/     # Pydantic schemas (shared types)
│   ├── ocr/            # Tesseract pipeline + regex extraction
│   ├── verification/   # Hemolysis, drug interference, plausibility, corrected values
│   ├── rag/            # Query rewriting, metadata-filtered hybrid search,
│   │   │                 # cross-encoder re-rank, organ system map, citation tracking
│   │   ├── query_rewriter.py
│   │   ├── organ_system_map.py
│   │   ├── embeddings.py
│   │   ├── retriever.py
│   │   ├── reranker.py
│   │   └── citation.py
│   ├── llm/            # Prompts, Ollama synthesis, output parsing
│   └── wearable/       # Apple Health / Google Fit connectors
├── knowledge-base/     # Build scripts + raw source texts
│   ├── raw/            # Wallach excerpts, guideline PDFs
│   └── build_kb.py     # Chunk → embed → LanceDB
└── docs/               # Planning documents (read these first)
```

## Architecture (6 Modules)

```
[Blood Test PDF]
    → Module 1: OCR Pipeline (1 CS)        — Tesseract + regex → structured JSON
    → Module 2: Context Collector (1 CS)   — Meds/supplements UI + wearable API
    → Module 3: Verification Layer (Med + 1 CS) — Rules engine for error detection
    → Module 4: RAG Engine (2 CS)          — Query rewrite → multi-label metadata filter → hybrid search → cross-encoder → relevance threshold → top-5
    → Module 5: LLM Synthesis (1 CS)       — GBNF grammar → local LLM → guaranteed valid JSON with citations + pre-cached demo outputs
    → Module 6: Dashboard (2 CS)           — Progressive rendering, two-step upload, pattern cards, network graph Plan A, demo mode, clear data
```

## Day 0 Prep (Before the Clock)

- Medical student: write original pattern summaries for ~30 conditions (not verbatim Wallach)
- Find/scan 5 test blood test PDFs (all 4 demo scenarios + one all-normal)
- Set up dev environments, pre-download all models (QVAC MedPsy, MiniLM, ms-marco)
- Write demo scripts (30s per scenario), prepare "before" mockups

## Implementation Order

### Phase 0 — Walking Skeleton (Hours 0-2): EVERYONE
- Hardcode one test case end-to-end FIRST — get the full pipeline working with fake data
- Define 3 integration test cases: iron deficiency, metabolic syndrome, all normal

### Phase 1 (Hours 2-12): Real modules, replace hardcoded pieces
- Module 1: `backend/ocr/` (with biomarker validation)
- Module 2: `frontend/src/components/Upload/` (two-step flow) + `backend/wearable/`
- Module 3: `backend/verification/` — run integration tests after each module

### Phase 2 (Hours 12-22): RAG, LLM, Dashboard
- Module 4: `knowledge-base/build_kb.py` + `backend/rag/` (multi-label, relevance threshold)
- Module 5: `backend/llm/` (GBNF grammar, token budget, pre-cached outputs)
- Module 6: Dashboard components (progressive rendering, demo mode, clear data, network Plan A)

### Phase 3 (Hours 22-36): Integration + Polish + Demo prep

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Tailwind CSS + D3.js + Framer Motion |
| Backend | Python FastAPI + Pydantic |
| OCR | Tesseract (pytesseract + pdf2image) |
| Vector DB | LanceDB (embedded, in-process) |
| Embeddings | all-MiniLM-L6-v2 (sentence-transformers) |
| Cross-Encoder | ms-marco-MiniLM-L-6-v2 (~90MB) |
| LLM | QVAC MedPsy 1.7B GGUF via Ollama (fallback: Gemma 2B) |
| Storage | SQLite |
| Wearable | Apple HealthKit / Google Health Connect (mock fallback) |

## Setup Commands

```bash
# Backend
cd backend && pip install fastapi uvicorn python-multipart pytesseract pdf2image pillow sentence-transformers lancedb ollama

# Frontend
cd frontend && npm install react react-dom typescript tailwindcss @types/react d3 @types/d3 framer-motion

# Knowledge base (run once)
cd knowledge-base && python build_kb.py

# LLM
ollama pull qvac-medpsy:1.7b
```

## API Contracts

All endpoints accept/return JSON matching Pydantic models in `backend/api/models/schemas.py`.

```
POST /api/ocr        → {biomarkers: [{name, value, unit, ref_low, ref_high, flag}], raw_text, parse_confidence}
POST /api/verify     → {verified_results, drug_interferences, corrected_values, quality_flags}
POST /api/analyze    → {summary, patterns: [{name, severity, confidence, explanation, citations, doctor_questions}], verification_alerts, disclaimer}
```

## Severity Color System

```
WARNING  #DC2626 — Needs urgent attention (hours–days)
CAUTION  #D97706 — Needs follow-up (days–weeks)
ADVISORY #2563EB — Lifestyle awareness (weeks–months)
NORMAL   #16A34A — In range
```

Rule: if everything is red, nothing is. Reserve red for genuinely dangerous values.

## Demo Scenarios

1. **Metabolic syndrome** — 6 abnormal markers → 1 pattern card (parent-child suppression)
2. **Iron deficiency + wearable** — Low ferritin/MCV/Hb + elevated resting HR → "potentially symptomatic"
3. **Biotin interference** — Abnormal TSH + normal FT4 + user on biotin → flagged as possible drug interference
4. **Hemolysis artifact** — High K+ + normal renal function → flagged as possible collection error

## Current State

- [x] Architecture designed (with state-of-the-art RAG, GBNF grammar, progressive UI)
- [x] Documentation: FOR_TEAMMATES (.md + .html), ARCHITECTURE.md, AGENT_PLAN.md, DESIGN_SPEC.md
- [x] Project directory structure created
- [ ] Day 0 prep: pattern summaries, test PDFs, model downloads, demo scripts
- [ ] Shared Pydantic schemas (`backend/api/models/schemas.py`)
- [ ] Integration test suite (3 reference cases)
- [ ] Walking skeleton (hardcoded end-to-end pipeline)
- [ ] Module 1: OCR Pipeline (with biomarker validation)
- [ ] Module 2: Context Collector (two-step flow, mock wearable scenarios)
- [ ] Module 3: Verification Layer (4 sub-modules)
- [ ] Module 4: RAG Engine (multi-label, relevance threshold, cross-encoder)
- [ ] Module 5: LLM Synthesis (GBNF grammar, token budget, pre-cached demos)
- [ ] Module 6: Dashboard UI (progressive rendering, demo mode, clear data)
- [ ] Pre-cached JSON outputs for 4 demo scenarios
- [ ] Demo walkthrough script + before/after slides

## Working with This Project

- Read `docs/FOR_TEAMMATES.md` first if you're new to the medical domain
- Read `docs/ARCHITECTURE.md` for the full technical design
- Read `docs/AGENT_PLAN.md` for detailed implementation instructions per module
- Read `docs/DESIGN_SPEC.md` for page requirements, UI states, and data shapes
- The medical student is the clinical authority — validate medical logic with them
- When implementing, start with `backend/api/models/schemas.py` (shared types everyone depends on)
- Frontend can develop against mock JSON while backend is being built
- Every LLM output must cite its sources and include a disclaimer
