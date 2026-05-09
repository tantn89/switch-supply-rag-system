"""Application lifespan: build the RAG engine once at startup."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.data_sources import SQLConnector
from app.providers.factory import build_embedding_provider, build_llm_provider
from app.query_router import QueryRouter
from app.rag_engine import RAGEngine
from app.retrieval import BM25Index, HybridRetriever, VectorStore
from app.scripts.build_index import collect_all_chunks
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _build_engine(settings: Settings) -> RAGEngine:
    data_dir = Path(settings.data_dir)
    chunks = collect_all_chunks(data_dir)
    if not chunks:
        raise RuntimeError(f"No chunks produced — check DATA_DIR={data_dir}")

    embedder = build_embedding_provider(settings)
    llm = build_llm_provider(settings)
    sql = SQLConnector(data_dir / "procurement.db")

    if embedder is None:
        # BM25-only mode — skip vector store entirely (saves ~150MB RAM).
        logger.info("EMBEDDING_PROVIDER=none → running BM25-only retrieval")
        store = None
    else:
        store = VectorStore(
            persist_dir=settings.chroma_persist_dir, embedding_provider=embedder
        )
        if store.count() == 0:
            store.add(chunks)
    bm25 = BM25Index(chunks)
    retriever = HybridRetriever(store, bm25, rrf_k=settings.hybrid_rrf_k)
    router = QueryRouter(llm=llm, schema_ddl=sql.get_schema())
    return RAGEngine(llm=llm, router=router, retriever=retriever, sql=sql)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger.info(
        "Booting backend (LLM=%s, embedding=%s)",
        settings.llm_provider,
        settings.embedding_provider,
    )
    app.state.engine = _build_engine(settings)
    app.state.settings = settings
    logger.info("Engine ready")
    yield
    logger.info("Shutting down")
