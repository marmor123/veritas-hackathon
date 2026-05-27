# VERITAS

A privacy-first, on-device platform that transforms blood test results from confusing alerts into verified clinical intelligence. Applies cross-industry alert management (SIEM event correlation, SCADA state-based logic, aviation severity hierarchy) to laboratory data interpretation.

## What Makes This Different

1. **Verifies before explaining** — detects pre-analytical errors (hemolysis, drug interference, physiological impossibilities) before clinical interpretation
2. **Recognizes patterns, not individual markers** — groups related biomarkers into clinical patterns using RAG against Wallach's Interpretation of Diagnostic Tests
3. **Every claim is cited** — assertions trace back to specific medical sources, not AI hallucination
4. **Runs entirely on-device** — no health data ever leaves your machine
5. **Wearable correlation** — distinguishes "abnormal lab value" from "abnormal lab value that's affecting your body"

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Knowledge Base (run once)
cd knowledge-base
python build_kb.py

# Local LLM (separate terminal)
ollama pull qvac-medpsy:1.7b
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

## For Team Members

- **CS students:** Start with [docs/FOR_TEAMMATES.md](docs/FOR_TEAMMATES.md) for medical context
- **Designers:** See [docs/DESIGN_SPEC.md](docs/DESIGN_SPEC.md) for page requirements and UI states
- **AI agents:** See [docs/AGENT_PLAN.md](docs/AGENT_PLAN.md) for implementation instructions

## License

Hackathon project — not for production use. This is not a medical device.
