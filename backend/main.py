"""
VERITAS Backend — FastAPI Application Entry Point

Runs the full pipeline API:
  POST /api/ocr       — OCR pipeline (Module 1)
  POST /api/verify    — Verification layer (Module 3)
  POST /api/rag       — RAG engine (Module 4)
  POST /api/analyze   — Full LLM synthesis (Module 5)
  GET  /api/rag/health — RAG health check

Usage:
    uvicorn backend.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.rag import router as rag_router
from backend.api.routes.verification import router as verification_router
from backend.api.routes.analysis import router as analysis_router
from backend.api.routes.ocr import router as ocr_router

app = FastAPI(
    title="VERITAS — Blood Test Analysis Engine",
    description="Verification and correlation engine for blood test results. "
                "Applies industrial alarm management to human biology.",
    version="0.1.0",
)

# CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ocr_router, tags=["OCR (Module 1)"])
app.include_router(verification_router, tags=["Verification"])
app.include_router(rag_router, tags=["RAG Engine"])
app.include_router(analysis_router, tags=["Analysis (Module 5)"])


@app.get("/")
async def root():
    return {
        "name": "VERITAS",
        "version": "0.1.0",
        "description": "Blood test verification and correlation engine",
        "modules": {
            "ocr": "/api/ocr",
            "verify": "/api/verify",
            "analyze": "/api/analyze",
            "analyze_demos": "/api/analyze/demos",
            "rag": "/api/rag",
            "rag_health": "/api/rag/health",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
