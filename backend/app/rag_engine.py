"""RAG orchestration engine.

Pipeline:
1. Router → RouteDecision (which sources, optional SQL).
2. Retrieve from each requested source (SQL exec, hybrid retrieval per source).
3. Assemble context block (capped per chunk).
4. Generate cited answer; emit "I don't have this info" when context is empty.

`stream_answer` yields SSE-style events for the frontend; `answer` returns
the final dict synchronously for tests / batch eval.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from app.data_sources import Chunk, ScoredChunk, SQLConnector, UnsafeSQLError
from app.models.route_decision import Citation, Confidence, RAGResponse, RouteDecision
from app.providers.llm_provider import LLMProvider
from app.query_router import QueryRouter
from app.retrieval import HybridRetriever

logger = logging.getLogger(__name__)

_MAX_CHUNK_CHARS = 800
_MAX_CONTEXT_CHUNKS = 12

_IDK_TEXT = "I don't have this information in the available data sources."

_ANSWER_SYSTEM = """You are a procurement AI assistant for Switch Supply.

Strict rules:
1. Answer ONLY from the CONTEXT below. Never invent data.
2. Cite sources inline using their source_id token in square brackets, e.g. [sql:vendors:1] or [pdf:vendor_catalog:p2:SKU-LED-100].
3. If the context is empty or insufficient, reply exactly: "I don't have this information in the available data sources."
4. For numeric comparisons or calculations, show the inputs and the math briefly.
5. Be concise. No marketing fluff."""


def _truncate(text: str, limit: int = _MAX_CHUNK_CHARS) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _format_chunk(chunk: Chunk) -> str:
    return f"[{chunk.source_id}]\n{_truncate(chunk.content)}"


def _format_sql_rows(rows: list[dict], sql: str) -> Chunk:
    """Wrap raw SQL rows as a synthetic chunk so the LLM can quote them."""
    pretty = json.dumps(rows, indent=2, default=str)
    return Chunk(
        chunk_id="sql-exec-result",
        source_id=f"sql:exec:{abs(hash(sql)) % 10_000_000}",
        source_type="sql",
        content=f"SQL executed: {sql}\nRows returned ({len(rows)}):\n{pretty}",
        metadata={"sql": sql, "rows": rows, "executed": True},
    )


class RAGEngine:
    """Top-level orchestrator combining router, retrieval, and LLM."""

    def __init__(
        self,
        llm: LLMProvider,
        router: QueryRouter,
        retriever: HybridRetriever,
        sql: SQLConnector,
    ) -> None:
        self.llm = llm
        self.router = router
        self.retriever = retriever
        self.sql = sql

    # ----------------- public API ------------------------------------------
    def answer(self, query: str) -> RAGResponse:
        decision = self.router.route(query)
        chunks, sql_rows = self._retrieve(query, decision)

        if not chunks:
            return RAGResponse(
                answer=_IDK_TEXT,
                citations=[],
                confidence="none",
                route=decision,
                sql_rows=sql_rows,
            )

        prompt = self._build_user_prompt(query, chunks)
        msg = self.llm.chat(
            messages=[
                {"role": "system", "content": _ANSWER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        text = msg.get("content") or _IDK_TEXT
        return RAGResponse(
            answer=text,
            citations=self._mk_citations(chunks),
            confidence=self._confidence(chunks, decision),
            route=decision,
            sql_rows=sql_rows,
        )

    async def stream_answer(self, query: str) -> AsyncIterator[dict[str, Any]]:
        """Yield SSE events: route → citations → token* → done | idk."""
        decision = self.router.route(query)
        yield {
            "event": "route",
            "data": {
                "sources": decision.sources,
                "sql_query": decision.sql_query,
                "reasoning": decision.reasoning,
            },
        }

        chunks, sql_rows = self._retrieve(query, decision)
        citations = self._mk_citations(chunks)
        yield {"event": "citations", "data": {"citations": [c.model_dump() for c in citations]}}

        if not chunks:
            yield {"event": "token", "data": {"text": _IDK_TEXT}}
            yield {"event": "done", "data": {"confidence": "none"}}
            return

        prompt = self._build_user_prompt(query, chunks)
        async for delta in self.llm.stream_chat(
            messages=[
                {"role": "system", "content": _ANSWER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        ):
            yield {"event": "token", "data": {"text": delta}}

        yield {"event": "done", "data": {"confidence": self._confidence(chunks, decision)}}

    # ----------------- internals -------------------------------------------
    def _retrieve(
        self, query: str, decision: RouteDecision
    ) -> tuple[list[Chunk], list[dict] | None]:
        chunks: list[Chunk] = []
        sql_rows: list[dict] | None = None

        if "sql_query" in decision.sources and decision.sql_query:
            try:
                sql_rows = self.sql.execute(decision.sql_query)
                chunks.append(_format_sql_rows(sql_rows, decision.sql_query))
            except UnsafeSQLError as e:
                logger.warning("Rejected unsafe SQL: %s (%s)", decision.sql_query, e)
            except Exception as e:
                logger.exception("SQL execution failed: %s", e)

        wanted_for_retrieval = {
            "sql_semantic": ["sql"],
            "pdf": ["pdf"],
            "json": ["json"],
            "image": ["image"],
        }
        source_filter: list[str] = []
        for src in decision.sources:
            source_filter.extend(wanted_for_retrieval.get(src, []))
        # Deduplicate while preserving order.
        source_filter = list(dict.fromkeys(source_filter))

        if source_filter:
            scored = self.retriever.retrieve(
                query, k=5, source_filter=source_filter
            )
            for sc in scored:
                # Skip duplicates (e.g. SQL chunk we may already have inserted via execute).
                if sc.chunk.chunk_id not in {c.chunk_id for c in chunks}:
                    chunks.append(sc.chunk)

        return chunks[:_MAX_CONTEXT_CHUNKS], sql_rows

    def _build_user_prompt(self, query: str, chunks: list[Chunk]) -> str:
        ctx = "\n\n---\n".join(_format_chunk(c) for c in chunks)
        return f"CONTEXT:\n{ctx}\n\nQUESTION: {query}\n\nANSWER:"

    @staticmethod
    def _mk_citations(chunks: list[Chunk]) -> list[Citation]:
        return [
            Citation(
                source_id=c.source_id,
                source_type=c.source_type,
                preview=_truncate(c.content, 240),
            )
            for c in chunks
        ]

    @staticmethod
    def _confidence(chunks: list[Chunk], decision: RouteDecision) -> Confidence:
        if not chunks:
            return "none"
        if any(c.metadata.get("executed") for c in chunks):
            # Direct SQL hit is the most authoritative signal.
            return "high"
        if len(chunks) >= len(decision.sources):
            return "high"
        return "medium"
