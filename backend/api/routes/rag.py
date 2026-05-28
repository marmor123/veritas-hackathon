"""
POST /api/rag — RAG Engine endpoint.

Accepts verified biomarker results and returns:
- Matched clinical patterns with citations
- Clinical knowledge graph for visualization
- Formatted citations for LLM synthesis
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from backend.api.models.schemas import (
    VerifiedResult,
    RAGOutput,
    ClinicalGraph,
    RetrievedChunk,
)
from backend.rag.pipeline import RAGPipeline

router = APIRouter()

# Singleton pipeline instance
_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    """Get or initialize the RAG pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline


class RAGRequest(BaseModel):
    """Request body for the RAG endpoint."""
    verified_results: List[VerifiedResult]
    medications: Optional[List[str]] = None
    wearable_data: Optional[dict] = None


class RAGResponse(BaseModel):
    """Response body from the RAG endpoint."""
    rag_output: RAGOutput
    citations: List[RetrievedChunk]
    citations_formatted: str
    clinical_graph: ClinicalGraph
    rewritten_query: str
    timings: dict


@router.post("/api/rag", response_model=RAGResponse)
async def run_rag(request: RAGRequest) -> RAGResponse:
    """
    Run the full RAG pipeline on verified biomarker results.

    Returns matched clinical patterns, citations, and a knowledge graph.
    """
    try:
        pipeline = get_pipeline()
        result = pipeline.run(
            verified_results=request.verified_results,
            medications=request.medications,
            wearable_data=request.wearable_data,
        )

        return RAGResponse(
            rag_output=result["rag_output"],
            citations=result["citations"],
            citations_formatted=result["citations_formatted"],
            clinical_graph=result["clinical_graph"],
            rewritten_query=result["rewritten_query"],
            timings=result["timings"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG pipeline error: {str(e)}",
        )


@router.get("/api/rag/health")
async def rag_health():
    """Health check for the RAG pipeline components."""
    status = {
        "embedding_model": False,
        "lancedb": False,
        "cross_encoder": False,
        "llm": False,
    }

    # Check embedding model
    try:
        from backend.rag.embeddings import get_model
        get_model()
        status["embedding_model"] = True
    except Exception as e:
        status["embedding_model_error"] = str(e)

    # Check LanceDB
    try:
        from backend.rag.retriever import get_db
        _, table = get_db()
        status["lancedb"] = table is not None
    except Exception as e:
        status["lancedb_error"] = str(e)

    # Check cross-encoder
    try:
        from backend.rag.reranker import get_reranker
        get_reranker()
        status["cross_encoder"] = True
    except Exception as e:
        status["cross_encoder_error"] = str(e)

    # Check LLM (Ollama)
    try:
        import ollama
        ollama.list()
        status["llm"] = True
    except Exception as e:
        status["llm_error"] = str(e)

    all_healthy = all(v for k, v in status.items() if isinstance(v, bool))
    return {"healthy": all_healthy, "components": status}
