"""GET /health and GET /sources — observability endpoints."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    engine = getattr(request.app.state, "engine", None)
    if engine and engine.retriever.vector_store is not None:
        chunk_count = engine.retriever.vector_store.count()
    elif engine:
        chunk_count = len(engine.retriever.bm25.chunks)
    else:
        chunk_count = 0
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "embedding_provider": settings.embedding_provider,
        "index_size": chunk_count,
        "retrieval_mode": "hybrid" if engine and engine.retriever.vector_store else "bm25-only",
    }


@router.get("/sources")
def sources(request: Request) -> dict:
    """Return per-source-type chunk counts so the frontend can show data scope."""
    engine = request.app.state.engine
    counts: Counter[str] = Counter()
    for c in engine.retriever.bm25.chunks:
        counts[c.source_type] += 1
    return {"by_source_type": dict(counts), "total": sum(counts.values())}
