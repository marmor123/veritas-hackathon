# VERITAS Code Review — Issues to Fix

This document is a thorough code review of the VERITAS backend, intended to be
fed to an AI coding assistant for cleanup. Each issue lists severity, location,
and recommended fix.

**Severity legend:**
- 🔴 **Critical** — bugs, security issues, or things that block the MVP
- 🟡 **Important** — quality issues affecting reliability or maintainability
- 🔵 **Nice-to-have** — improvements that aren't blockers

---

## 🔴 Critical Issues

### 1. Duplicate analyze endpoint and synthesizer files

**Location:** `backend/api/routes/`, `backend/llm/`

There are two parallel implementations of the same module that conflict:

- `backend/api/routes/analyze.py` (created during MVP planning)
- `backend/api/routes/analysis.py` (existing, more complete with demo support)

Both register `POST /api/analyze`. Only `analysis.py` is currently registered in
`main.py`, so `analyze.py` is dead code.

Two synthesizer implementations also exist:
- The `synthesize()` in `backend/llm/synthesizer.py` (existing — uses `prompts.py`,
  `context_formatter.py`, `demo_outputs.py`, has fallback chain)
- A simpler `synthesize()` I wrote inline in `backend/llm/synthesizer.py` during
  MVP planning that was overwritten

**The kept one (existing) is better.** It has:
- Pre-built prompts in `prompts.py`
- Demo output fallbacks
- Multi-model fallback chain
- JSON extraction with brace-matching
- Severity/Confidence safe enum mapping

**Action:**
1. Delete `backend/api/routes/analyze.py` (the duplicate I created)
2. Verify `backend/llm/synthesizer.py` is the existing detailed version (not my
   simpler stub)
3. Confirm `main.py` only registers `analysis.py`, not `analyze.py`

---

### 2. main.py has stale module documentation

**Location:** `backend/main.py:5-13`

The docstring says:
```
POST /api/ocr       — OCR pipeline (Module 1)
POST /api/verify    — Verification layer (Module 3)
POST /api/rag       — RAG engine (Module 4)
POST /api/analyze   — Full LLM synthesis (Module 5)
```

But the routers registered include `analyze_router` (which doesn't exist
anymore after fixing #1) and the `/api/analyze/demos` endpoint exists too.

**Action:** Update docstring to match actual routes; remove any orphan
references.

---

### 3. PDF binary files committed to backend/

**Location:** `backend/report1.pdf`, `backend/report4.pdf`, `backend/report5.pdf`,
`backend/output.json`

These are test artifacts, not source code. They should not live in the backend
package (and probably not in git at all).

**Action:**
- Move to a `backend/test_data/` folder OR delete
- Add `*.pdf` and `output.json` to `.gitignore` if they should not be tracked
- Document where test PDFs should live (e.g., `tests/fixtures/`)

---

### 4. Hard-coded Tesseract path is Windows-only and fragile

**Location:** `backend/ocr/extractor.py:21-24`

```python
if os.name == "nt":
    _tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = _tesseract_path
```

This breaks on:
- Windows machines that installed Tesseract elsewhere
- macOS / Linux teammates (the path doesn't exist, but the code silently doesn't
  configure pytesseract — so it will try to find `tesseract` on PATH)

**Action:**
- Read from environment variable `TESSERACT_CMD` first
- Fall back to PATH on Linux/macOS
- Only use the hardcoded Windows path as a last resort
- Document required Tesseract installation in `README.md` or `INTEGRATION_GUIDE.md`

---

### 5. The OCR module is incomplete

**Location:** `backend/ocr/extractor.py`

The file has `LAB_TEST_MAPPING`, `EXPLANATION_BLACKLIST`, and reference range
constants, but the actual processing functions referenced in `routes/ocr.py`:

- `process_pdf_to_spatial_text`
- `process_image_to_text`
- `parse_text_to_json`

These need to be verified to actually exist and work. From the line count
(216 lines) it appears at least partially implemented, but a full review of the
extraction logic, regex patterns, and unit detection is needed.

**Action:**
- Confirm all three functions exist and are tested against the demo PDFs
- Add unit tests for each report format
- Document which lab report formats are supported

---

## 🟡 Important Issues

### 6. Schema mismatch — backend uses "H"/"L", frontend uses "high"/"low"

**Location:** `backend/api/models/schemas.py`

The `BiomarkerResult.flag` field comment says it accepts both formats:
```python
flag: Optional[str] = None       # "H"/"L"/"high"/"low"/"normal" or None
```

But the verifier uses string matching that handles both. This is fragile —
someone will eventually pass `"HIGH"` (uppercase) or `"hi"` and it won't be
flagged.

**Action:**
- Convert `flag` to a proper enum with strict mapping
- Add a Pydantic validator that normalizes incoming strings

---

### 7. Singleton patterns leak module state across tests

**Location:**
- `backend/api/routes/analysis.py:32` — `_pipeline = None`
- `backend/rag/embeddings.py` — `_model = None`
- `backend/rag/reranker.py` — `_reranker = None`
- `backend/rag/retriever.py` — `_db, _table = None, None`

These globals make the modules hard to test in isolation. Each test that imports
the modules either reuses the cached state (good for speed, bad for isolation)
or fails because the singleton was modified by a previous test.

**Action:**
- Wrap singletons in a class-based service container
- Provide a way to reset singletons in tests (e.g., `reset_singletons()` helper)
- Use FastAPI's dependency injection (`Depends`) instead of module-level globals

---

### 8. Print-based logging instead of structured logging

**Location:** Throughout the codebase (`pipeline.py`, `synthesizer.py`,
`retriever.py`, etc.)

```python
print(f"[RAG] Stage 1 (Query Rewriting): {timings['query_rewriting']:.2f}s")
```

This:
- Doesn't have log levels (can't suppress in tests, can't increase in debug)
- Isn't structured (can't filter or query logs)
- Mixes with stdout output the user might want clean
- Doesn't go anywhere persistent

**Action:**
- Replace `print()` with Python's `logging` module
- Configure a logger per module: `logger = logging.getLogger(__name__)`
- Use levels: DEBUG for stage timings, INFO for stage completion, WARNING for
  fallbacks, ERROR for failures
- Add a logging config at startup in `main.py`

---

### 9. No timeouts on LLM calls

**Location:** `backend/llm/synthesizer.py:_call_llm`

```python
response = ollama.generate(
    model=model,
    system=SYSTEM_PROMPT,
    prompt=prompt,
    format="json",
    options={"temperature": 0.3, "num_predict": 2048},
)
```

The architecture spec calls for a 30-second timeout on LLM synthesis. Currently
there's no timeout — if Ollama hangs, the whole request hangs.

**Action:**
- Add timeout per stage as documented in `ARCHITECTURE.md`:
  - OCR: 15s
  - Query rewriting: 10s
  - RAG: 7s
  - LLM synthesis: 30s
- Use `asyncio.wait_for()` for async, or `concurrent.futures.ThreadPoolExecutor`
  with a timeout for sync ollama calls
- On timeout, return graceful fallback (raw biomarkers + verification flags)

---

### 10. Demo file reading happens at import time

**Location:** `backend/llm/demo_outputs.py`

The file constructs `AnalysisOutput` instances at module level (`DEMO_IRON_DEFICIENCY = AnalysisOutput(...)`).

If a Pydantic schema changes, every demo breaks at import time, which means the
whole API fails to start. This is fragile.

**Action:**
- Store demos as JSON files in `backend/llm/demo_data/`
- Load lazily on first access, validate against the schema
- Add a startup health check that loads each demo and warns if any are invalid
  (but doesn't crash)

---

### 11. OCR reference ranges are duplicated

**Location:**
- `backend/api/routes/ocr.py:33` — `REFERENCE_RANGES` dict
- `backend/rag/organ_system_map.py` — different lookup
- Hardcoded ref ranges in `verification/hemolysis.py`, `plausibility.py`

There's no single source of truth for normal ranges. If a clinical guideline
updates (e.g., new HbA1c diabetes threshold), three files need updating.

**Action:**
- Create `backend/clinical/reference_ranges.py` as the single source
- All other modules import from there
- Tag each range with its source (e.g., AHA, ADA, NCCLS) for auditability

---

### 12. organ_system_map has both "metabolic" and "cardiometabolic" inconsistently

**Location:** `backend/rag/organ_system_map.py`

Some biomarkers list `"metabolic"`, some `"cardiometabolic"`, some both. The
LanceDB chunks use `"cardiometabolic"`. The retriever filter does `LIKE
'%metabolic%'` which matches both — works by accident, not by design.

**Action:**
- Pick ONE canonical name (`cardiometabolic` since that's what the parser
  generates in chunks)
- Update `ORGAN_SYSTEM_MAP` so every metabolic biomarker has only that label
- Remove the LIKE pattern hack in `retriever.py:_build_organ_system_filter`

---

### 13. parse_wallach.py output title may include "(part 1)" suffix

**Location:** `knowledge-base/parse_wallach.py`

When sub-splitting a large h3 by h4, the suffix logic was changed to NOT add
`— Definition` or similar. But there's still residual code in `_flush_chunk`
that supports a `suffix` parameter, which can leak in some edge cases.

**Action:**
- Verify with current `chunks.json` that no chunk title contains "(part" or
  "— Suggested Readings" or other artifacts
- If found, remove the dead `suffix` parameter from `_flush_chunk`

---

### 14. Cross-encoder threshold is brittle

**Location:** `backend/rag/reranker.py:RELEVANCE_THRESHOLD = -3.0`

The threshold was calibrated for the fallback (rule-based) query rewriter, which
produces non-natural-language queries. With a real LLM rewriter (Ollama), scores
are positive and `-3.0` is too lenient. Without LLM, scores are negative and
the test had to drop to `-3.0` from `0.3`.

**Action:**
- Detect whether the input query came from LLM or fallback, and use different
  thresholds
- OR: normalize cross-encoder scores into `[0, 1]` range and use a single
  threshold like `0.5`
- OR: drop the threshold entirely (we already have `always_return_top_k=True`),
  and rely on confidence labels for downstream filtering

---

## 🔵 Nice-to-Have Improvements

### 15. No automated test runner

There are test files in three places:
- `knowledge-base/test_pipeline.py`
- `knowledge-base/test_rag_quality.py`
- `backend/verification/test_verification.py`
- `backend/llm/test_module5.py`

But no `pytest`, no CI, no `conftest.py`. Each test has to be run manually with
`python file.py`.

**Action:**
- Add `pytest` to `requirements.txt`
- Convert tests to use `pytest` conventions (functions starting with `test_`)
- Add a `tests/` directory at the project root
- Add a GitHub Actions workflow that runs `pytest` on push

---

### 16. Citation source string is over-formatted

**Location:** `backend/rag/citation.py:_format_source`

Currently produces:
```
Wallach's Interpretation of Diagnostic Tests, 11th Edition, Chapter Hematologic_Disorders, Red Blood Cell Disorders — Microcytic Anemias
```

The chapter slug `Hematologic_Disorders` is shown raw (with underscore). Could
be cleaned to `Hematologic Disorders`.

**Action:**
- Replace underscores with spaces in chapter
- Drop "Chapter" prefix if the chapter slug isn't `chapter1`-style
- Title-case sensibly (don't title-case `α` and `β` symbols)

---

### 17. The clinical graph builder has hard-coded patterns

**Location:** `backend/graph/graph_builder.py:CAUSAL_CHAINS`

The graph relationships (e.g., `"ferritin --causes--> iron"`) are hardcoded for
4-5 known patterns. New patterns won't show on the graph.

**Action (for v2):**
- Use the LLM to generate causal links from retrieved chunks
- Cache common patterns in `CAUSAL_CHAINS` for speed/consistency
- Validate generated graphs against the curated patterns when both apply

---

### 18. No request validation for biomarker units

**Location:** `backend/api/models/schemas.py:BiomarkerResult`

A user could pass `value=12, unit="kg"` for ferritin. The pipeline runs anyway
and gives meaningless results.

**Action:**
- Add a unit registry: `Ferritin: ng/mL`, `Hemoglobin: g/dL`, etc.
- Validate units on input, normalize where possible (e.g., `mmol/L` → `mg/dL`
  for cholesterol with a known conversion)
- Reject obviously wrong units with HTTP 400

---

### 19. No rate limiting or auth on API endpoints

**Location:** `backend/main.py`

The API is open. For a hackathon demo this is fine; for production it isn't.

**Action (for v2):**
- Add `slowapi` rate limiting per IP
- Add a basic API key check for `/api/analyze`
- Document that this is a hackathon prototype, not production

---

### 20. Frontend integration is undocumented

**Location:** No documentation file for the frontend team

The frontend team needs to know:
- The exact JSON shape of `AnalysisOutput`
- Which fields are required vs optional
- How to call `/api/analyze` (request shape, error codes)
- How to use `?demo=iron_deficiency` for instant demos
- How to handle the clinical graph for visualization

**Action:**
- Write `docs/FRONTEND_API.md` with TypeScript interfaces and example
  requests/responses
- Or better: generate it from FastAPI's OpenAPI schema
  (`http://localhost:8000/docs`)

---

### 21. The fallback query rewriter doesn't recognize many patterns

**Location:** `backend/rag/query_rewriter.py:_fallback_query`

Only 7 patterns are detected: iron deficiency, B12 deficiency, hypothyroidism,
metabolic syndrome, kidney, liver, hyperkalemia.

Missing common patterns:
- Anemia of chronic disease
- Hypercalcemia / hypocalcemia
- Hyponatremia / hypernatremia
- Diabetic ketoacidosis (anion gap + glucose)
- Pancreatitis (lipase + amylase)
- Cholestatic liver disease (ALP > AST/ALT)
- Pre-eclampsia
- Sepsis screen (WBC + CRP + lactate)

**Action:**
- Add detection rules for the most common missing patterns
- Ideally, generate the rules from the KB itself rather than hardcoding

---

### 22. Embedding model loaded eagerly even when not needed

**Location:** `backend/rag/embeddings.py:get_model`

Every test that imports `embeddings` triggers a 90 MB download/load on first
call. The verification module doesn't need embeddings — but if it transitively
imports something from `rag/`, the model loads anyway.

**Action:**
- Lazy-load embeddings only when the first `embed_text()` call happens
- Verify nothing in `verification/` imports from `rag/`
- Add a fast unit test mode where the embedding model is mocked

---

### 23. No README at the project root

The repo has good docs in `docs/` but no top-level `README.md` that tells a new
contributor:
- What the project is
- How to install dependencies
- How to run the backend
- How to run tests

**Action:** Create `README.md` with a quickstart, links to architecture docs,
and a minimal "hello world" example.

---

## Quick Wins (do these first)

If you only have 1 hour, do these:

1. ✂️ Delete `backend/api/routes/analyze.py` and `backend/api/routes/__pycache__/`
2. 📦 Move `backend/report*.pdf` and `backend/output.json` out of the backend
   package
3. 📝 Update `backend/main.py` docstring to match actual routes
4. 🐛 Fix the Tesseract path issue (env var or PATH first, hardcode last)
5. 📋 Create `README.md` at the project root

These 5 changes take an hour and remove the most jarring issues.

---

## Recommended Refactor Order

For a more thorough cleanup (1-2 days):

1. **Hour 1**: Quick wins above
2. **Hour 2-3**: Replace `print` with `logging` everywhere
3. **Hour 4**: Add timeouts to all LLM/RAG calls
4. **Hour 5**: Consolidate reference ranges into one module
5. **Hour 6**: Fix singleton patterns with FastAPI Depends
6. **Hour 7-8**: Add pytest + convert existing test files
7. **Hour 9-10**: Add unit validation for BiomarkerResult
8. **Hour 11-12**: Write `FRONTEND_API.md` from OpenAPI

---

## Don't Touch For Now

These look like issues but are intentional / acceptable for the hackathon:

- The 1.5 MB committed LanceDB — this is intentional so the team can clone and
  run without rebuilding.
- The `Suggested Readings` filter in the parser — it's working as designed.
- The fallback query rewriter producing question-shaped queries — necessary for
  the cross-encoder to score correctly.
- Module 1 (OCR) being incomplete — another teammate is finishing it.
- The graphify hardcoded chains — adequate for the 4 demo scenarios.
