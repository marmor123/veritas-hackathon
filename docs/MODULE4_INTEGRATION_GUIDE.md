# Module 4: RAG Engine + Graphify — Integration Guide

## What This Module Does

Module 4 is the **clinical knowledge retrieval engine** for VERITAS. Given a set of abnormal blood test results, it:

1. **Rewrites** the raw biomarker list into a clinical retrieval query (LLM or fallback)
2. **Searches** a vector database of 831 medical textbook chunks (Wallach's 9th Edition)
3. **Re-ranks** results using a cross-encoder for precision
4. **Tracks citations** so every claim is traceable to a source
5. **Builds a knowledge graph** showing causal relationships between biomarkers

The output feeds directly into Module 5 (LLM Synthesis) and Module 6 (Dashboard).

---

## Architecture Overview

```
Verified Biomarkers (from Module 3)
        │
        ▼
┌──────────────────────────────────────────────┐
│  STAGE 1: Query Rewriting                    │
│  Raw values → clinical retrieval query       │
│  (LLM via Ollama, or deterministic fallback) │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  STAGE 2: Metadata-Filtered Hybrid Search    │
│  Organ system pre-filter → semantic (0.7)    │
│  + keyword (0.3) search in LanceDB           │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  STAGE 3: Cross-Encoder Re-Ranking           │
│  ms-marco-MiniLM scores (query, chunk) pairs │
│  Drops low-relevance chunks                  │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  STAGE 4: Citation Tracking                  │
│  Attach source metadata to each chunk        │
│  Format for LLM synthesis prompt             │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│  GRAPHIFY: Knowledge Graph Builder           │
│  Biomarker nodes + causal edges + patterns   │
│  Output: JSON graph for D3.js visualization  │
└──────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- ~2GB disk space (models + vector DB)
- No GPU required (runs on CPU)

### Installation

```bash
cd veritas-hackathon

# Install dependencies
pip install -r backend/requirements.txt

# Or install individually:
pip install sentence-transformers lancedb ollama fastapi uvicorn
```

### Build the Knowledge Base (one-time setup)

```bash
# Step 1: Parse the Wallach 11th Edition HTML files into chunks
# (HTML files saved from apn.lwwhealthlibrary.com via View Source)
python knowledge-base/parse_wallach.py

# Step 2: Embed chunks and build the vector database
python knowledge-base/build_kb.py
```

This creates:
- `knowledge-base/chunks.json` — 467 clinical pattern chunks (one per condition)
- `knowledge-base/lancedb/` — Vector database with embeddings

The parser only includes clinical pattern chapters (Hematologic, Endocrine, Cardiovascular,
Renal, etc.) and skips non-pattern chapters (Laboratory Tests A-Z, Toxicology, Transfusion, etc.)
that would pollute retrieval with single-test reference cards.

### Run Tests

```bash
# Full pipeline test (no LLM required — uses fallback query rewriter)
python knowledge-base/test_pipeline.py
```

### Start the API Server

```bash
uvicorn backend.main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

---

## API Reference

### POST /api/rag

Runs the full RAG pipeline on verified biomarker results.

**Request:**
```json
{
  "verified_results": [
    {
      "biomarker": "Ferritin",
      "value": 12.0,
      "unit": "ng/mL",
      "ref_low": 15.0,
      "ref_high": 150.0,
      "flagged": true,
      "flag_reason": "Below range"
    },
    {
      "biomarker": "MCV",
      "value": 78.0,
      "unit": "fL",
      "ref_low": 80.0,
      "ref_high": 100.0,
      "flagged": true,
      "flag_reason": "Below range"
    }
  ],
  "medications": ["Metformin"],
  "wearable_data": {
    "resting_hr_avg": 76,
    "resting_hr_trend": "rising"
  }
}
```

**Response:**
```json
{
  "rag_output": {
    "matched_patterns": [
      {
        "pattern_name": "Microcytic Anemias",
        "confidence": "HIGH",
        "supporting_biomarkers": ["ferritin", "mcv"],
        "retrieved_chunks": ["wallach_ch10_s003"],
        "differential": []
      }
    ],
    "unmatched_abnormal_biomarkers": []
  },
  "citations": [
    {
      "chunk_id": "wallach_ch10_s003",
      "source": "Wallach's Interpretation of Diagnostic Tests, 9th Edition, Chapter10",
      "text": "Iron deficiency is the most common cause of microcytic anemia...",
      "relevance_score": 0.735,
      "biomarkers_involved": ["iron", "ferritin", "mcv", "tibc"]
    }
  ],
  "citations_formatted": "[CITATION wallach_ch10_s003] (Source: ...) ...",
  "clinical_graph": {
    "nodes": [
      {"id": "ferritin", "label": "Low Ferritin", "type": "biomarker", "severity": "CAUTION"},
      {"id": "iron_deficiency", "label": "Iron Deficiency", "type": "pattern"},
      {"id": "hematologic", "label": "Hematologic", "type": "system"},
      {"id": "resting_hr", "label": "Resting HR ↑ (76 bpm)", "type": "symptom"}
    ],
    "edges": [
      {"source": "ferritin", "target": "iron_deficiency", "relation": "supports"},
      {"source": "iron_deficiency", "target": "hematologic", "relation": "belongs_to"},
      {"source": "hemoglobin", "target": "resting_hr", "relation": "may_cause"}
    ]
  },
  "rewritten_query": "Microcytic anemia pattern with depleted iron stores...",
  "timings": {
    "query_rewriting": 0.001,
    "hybrid_search": 0.04,
    "reranking": 0.55,
    "citation_tracking": 0.001,
    "graph_building": 0.001
  }
}
```

### GET /api/rag/health

Returns component health status.

```json
{
  "healthy": true,
  "components": {
    "embedding_model": true,
    "lancedb": true,
    "cross_encoder": true,
    "llm": false
  }
}
```

---

## Integration with Other Modules

### Receiving Input from Module 3 (Verification Layer)

Module 4 expects `VerifiedResult` objects from Module 3:

```python
from backend.api.models.schemas import VerifiedResult

# Module 3 produces these:
verified_results = [
    VerifiedResult(
        biomarker="Ferritin",
        value=12.0,
        unit="ng/mL",
        ref_low=15.0,
        ref_high=150.0,
        flagged=True,
        flag_reason="Below range"
    ),
    # ... more results
]
```

### Feeding Output to Module 5 (LLM Synthesis)

Module 5 needs two things from Module 4:

1. **`citations_formatted`** — A string containing the top-5 retrieved chunks formatted with citation IDs. Paste this directly into the LLM synthesis prompt.

2. **`rag_output.matched_patterns`** — Pattern metadata for the LLM to reference.

```python
from backend.rag.pipeline import RAGPipeline

pipeline = RAGPipeline()
result = pipeline.run(verified_results, medications, wearable_data)

# Pass to Module 5:
llm_context = result["citations_formatted"]  # String for the prompt
patterns = result["rag_output"].matched_patterns  # Pattern metadata
```

### Feeding Output to Module 6 (Dashboard)

Module 6 needs the `clinical_graph` for the network visualization:

```typescript
// Frontend receives this JSON from the API:
interface ClinicalGraph {
  nodes: Array<{
    id: string;
    label: string;
    type: "biomarker" | "pattern" | "system" | "symptom";
    severity?: "WARNING" | "CAUTION" | "ADVISORY";
    value?: number;
    unit?: string;
  }>;
  edges: Array<{
    source: string;  // node id
    target: string;  // node id
    relation: "supports" | "causes" | "may_cause" | "belongs_to" | "contributes_to";
    weight?: number;
  }>;
}
```

Render with D3.js force-directed graph:
- Node color = severity (red/amber/blue/green)
- Node size = deviation from reference range
- Edge style = relation type (solid for "causes", dashed for "may_cause")

---

## Using the Pipeline Programmatically (Python)

```python
import sys
sys.path.insert(0, "/path/to/veritas-hackathon")

from backend.api.models.schemas import VerifiedResult
from backend.rag.pipeline import RAGPipeline

# Initialize (loads models on first call)
pipeline = RAGPipeline(
    llm_model="qvac-medpsy:1.7b",  # or any Ollama model
    rerank_threshold=-2.0,          # adjust based on query quality
    rerank_top_k=5,
    search_top_k=15,
)

# Define input
verified_results = [
    VerifiedResult(biomarker="Ferritin", value=12, unit="ng/mL",
                   ref_low=15, ref_high=150, flagged=True, flag_reason="Below range"),
    VerifiedResult(biomarker="Hemoglobin", value=11.2, unit="g/dL",
                   ref_low=12, ref_high=16, flagged=True, flag_reason="Below range"),
]

# Run pipeline
result = pipeline.run(
    verified_results=verified_results,
    medications=["Metformin"],
    wearable_data={"resting_hr_avg": 76, "resting_hr_trend": "rising"},
)

# Access results
print(result["rag_output"].matched_patterns)
print(result["clinical_graph"].nodes)
print(result["citations_formatted"])
print(result["timings"])
```

---

## Using the Graph Builder Standalone

If you only need the knowledge graph (without RAG retrieval):

```python
from backend.api.models.schemas import VerifiedResult
from backend.graph.graph_builder import build_clinical_graph

verified_results = [
    VerifiedResult(biomarker="Ferritin", value=12, unit="ng/mL",
                   ref_low=15, ref_high=150, flagged=True, flag_reason="Below range"),
    VerifiedResult(biomarker="Iron", value=35, unit="µg/dL",
                   ref_low=60, ref_high=170, flagged=True, flag_reason="Below range"),
    VerifiedResult(biomarker="MCV", value=78, unit="fL",
                   ref_low=80, ref_high=100, flagged=True, flag_reason="Below range"),
    VerifiedResult(biomarker="Hemoglobin", value=11.2, unit="g/dL",
                   ref_low=12, ref_high=16, flagged=True, flag_reason="Below range"),
]

graph = build_clinical_graph(
    verified_results=verified_results,
    wearable_data={"resting_hr_avg": 76, "resting_hr_trend": "rising"},
)

# Output: ClinicalGraph with nodes and edges
for node in graph.nodes:
    print(f"  [{node.type}] {node.label} (severity: {node.severity})")

for edge in graph.edges:
    print(f"  {edge.source} --{edge.relation}--> {edge.target}")
```

**Output:**
```
  [biomarker] Low Ferritin (severity: CAUTION)
  [biomarker] Low Iron (severity: CAUTION)
  [biomarker] Low MCV (severity: ADVISORY)
  [biomarker] Low Hemoglobin (severity: ADVISORY)
  [pattern] Iron Deficiency (severity: None)
  [system] Hematologic (severity: None)
  [symptom] Resting HR ↑ (76 bpm) (severity: None)

  iron_deficiency --belongs_to--> hematologic
  ferritin --causes--> iron
  ferritin --supports--> iron_deficiency
  iron --contributes_to--> mcv
  mcv --contributes_to--> hemoglobin
  hemoglobin --may_cause--> resting_hr
```

---

## File Structure

```
backend/
├── __init__.py
├── main.py                      # FastAPI app entry point
├── requirements.txt             # Python dependencies
├── api/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # All Pydantic types (shared across modules)
│   └── routes/
│       ├── __init__.py
│       └── rag.py               # POST /api/rag endpoint
├── rag/
│   ├── __init__.py
│   ├── organ_system_map.py      # Biomarker → organ system mapping
│   ├── embeddings.py            # all-MiniLM-L6-v2 wrapper
│   ├── query_rewriter.py        # Stage 1: LLM query rewriting
│   ├── retriever.py             # Stage 2: Hybrid search in LanceDB
│   ├── reranker.py              # Stage 3: Cross-encoder re-ranking
│   ├── citation.py              # Stage 4: Citation tracking
│   └── pipeline.py              # Orchestrates all stages
└── graph/
    ├── __init__.py
    └── graph_builder.py         # Graphify: knowledge graph construction

knowledge-base/
├── *.html                       # Wallach 11th Edition HTML source (gitignored)
├── parse_wallach.py             # HTML parser → clinical pattern chunks
├── build_kb.py                  # Embed chunks → LanceDB
├── chunks.json                  # 467 clinical pattern chunks (committed)
├── lancedb/                     # Vector database (gitignored, rebuild with build_kb.py)
└── test_pipeline.py             # End-to-end pipeline tests
```

---

## How to Add More Knowledge

### Option A: Add more HTML chapters from the website

The 11th Edition from lwwhealthlibrary.com is the source of truth.

**Workflow:**

```bash
# 1. Medical student saves HTML source from the website:
#    Go to https://apn.lwwhealthlibrary.com/book.aspx?bookid=2839
#    Log in with Hebrew University credentials
#    Navigate to chapter → Right-click → View Source → Save as .html
#    Save files to: knowledge-base/

# 2. Parse all HTML files (parser auto-detects clinical vs reference chapters):
python knowledge-base/parse_wallach.py

# 3. Rebuild vector DB:
python knowledge-base/build_kb.py
```

The parser:
- Chunks at h3 (one chunk per clinical condition)
- Sub-splits large conditions at h4 (Definition, Lab Findings, etc.) — never mid-sentence
- Auto-skips reference chapters (Laboratory Tests A-Z, Toxicology, Transfusion, etc.)
- Detects biomarkers and organ systems automatically

### Option B: Add custom clinical knowledge

1. Create a JSON file with the same schema as `chunks.json`:
```json
[
  {
    "chunk_id": "custom_001",
    "source": "Your Source Name",
    "chapter": "custom",
    "section_title": "Iron Deficiency in Athletes",
    "text": "Your clinical text here...",
    "organ_system": ["hematologic", "nutritional"],
    "biomarkers_mentioned": ["ferritin", "iron", "hemoglobin"],
    "word_count": 150
  }
]
```

2. Merge with existing chunks and rebuild:
```python
import json
existing = json.load(open("knowledge-base/chunks.json"))
custom = json.load(open("my_custom_chunks.json"))
merged = existing + custom
json.dump(merged, open("knowledge-base/chunks.json", "w"), indent=2)
```

3. Run `python knowledge-base/build_kb.py` to re-embed.

### Adding new causal chains to the graph:

Edit `backend/graph/graph_builder.py` and add entries to `CAUSAL_CHAINS`:

```python
{
    "trigger": ["vitamin_d"],  # Which biomarkers trigger this chain
    "chain": [
        {"from": "vitamin_d", "to": "calcium", "relation": "may_cause",
         "label": "Low Vitamin D → Low Calcium Absorption"},
        {"from": "vitamin_d", "to": "pth", "relation": "causes",
         "label": "Low Vitamin D → Elevated PTH"},
    ],
    "pattern": "Vitamin D Deficiency",
    "system": "Nutritional",
}
```

---

## Configuration & Tuning

| Parameter | Default | Description |
|-----------|---------|-------------|
| `llm_model` | `"qvac-medpsy:1.7b"` | Ollama model for query rewriting |
| `rerank_threshold` | `-2.0` | Cross-encoder minimum score (raise for stricter filtering) |
| `rerank_top_k` | `5` | Max chunks after re-ranking |
| `search_top_k` | `15` | Candidates for re-ranking |
| `semantic_weight` | `0.7` | Weight for embedding similarity in hybrid search |
| `keyword_weight` | `0.3` | Weight for keyword/FTS matching |

**Tuning tips:**
- If results are too broad: raise `rerank_threshold` toward 0
- If results are too narrow: lower `rerank_threshold` toward -5
- With LLM query rewriter active: set `rerank_threshold` to 0.3 (positive scores expected)
- Without LLM (fallback mode): keep `rerank_threshold` at -2.0

---

## Performance

| Stage | Latency (first run) | Latency (warm) |
|-------|--------------------:|---------------:|
| Model loading | ~5s | 0s (cached) |
| Query rewriting (fallback) | <1ms | <1ms |
| Query rewriting (LLM) | ~3s | ~3s |
| Hybrid search | ~40ms | ~40ms |
| Cross-encoder re-ranking | ~550ms | ~550ms |
| Citation tracking | <1ms | <1ms |
| Graph building | <1ms | <1ms |
| **Total (warm, no LLM)** | — | **~600ms** |
| **Total (warm, with LLM)** | — | **~4s** |

---

## Prompt for AI Assistants

If you're asking an AI to integrate this module into your project, use this prompt:

```
I have a RAG engine module for a blood test analysis app. Here's what it does:

INPUT: A list of verified biomarker results (name, value, unit, ref_low, ref_high, flagged)
OUTPUT: 
  - Matched clinical patterns with citations from Wallach's textbook
  - A knowledge graph (nodes + edges) showing causal relationships
  - Formatted citation text for LLM synthesis

The module is at backend/rag/ and backend/graph/. 
The API endpoint is POST /api/rag.
The knowledge base is at knowledge-base/lancedb/ (831 embedded chunks).

Key files:
- backend/rag/pipeline.py — main orchestrator (RAGPipeline class)
- backend/graph/graph_builder.py — builds causal knowledge graphs
- backend/api/models/schemas.py — all shared types (VerifiedResult, ClinicalGraph, etc.)
- backend/api/routes/rag.py — FastAPI endpoint

To integrate:
1. Module 3 (Verification) feeds VerifiedResult objects into pipeline.run()
2. Module 5 (LLM Synthesis) receives citations_formatted string for its prompt
3. Module 6 (Dashboard) receives clinical_graph JSON for D3.js network visualization

The graph output looks like:
  nodes: [{id, label, type: "biomarker"|"pattern"|"system"|"symptom", severity}]
  edges: [{source, target, relation: "causes"|"supports"|"may_cause"|"belongs_to"}]

Please [describe what you want the AI to do with this module].
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `No table 'clinical_patterns'` | Run `python knowledge-base/build_kb.py` |
| `chunks.json not found` | Run `python knowledge-base/parse_wallach.py` |
| Cross-encoder returns all negative scores | Normal without LLM rewriter. Threshold is set to -2.0 |
| LLM query rewriter fails | Falls back to deterministic query. Install Ollama for better results |
| Search returns irrelevant results | Check organ system mapping in `organ_system_map.py` |
| Empty graph for known patterns | Check `CAUSAL_CHAINS` in `graph_builder.py` |
