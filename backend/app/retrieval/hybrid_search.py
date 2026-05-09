"""Hybrid retrieval: BM25 + semantic, fused with Reciprocal Rank Fusion.

RRF formula (Cormack et al., 2009):
    score(d) = Σ 1 / (k + rank_i(d))

Rank-only fusion needs no score normalisation across BM25 (raw float) and
cosine similarity (-1..1). k=60 is the published default and works well.
"""
from __future__ import annotations

from collections import defaultdict

from app.data_sources.chunk_schema import Chunk, ScoredChunk
from app.retrieval.bm25_index import BM25Index
from app.retrieval.vector_store import VectorStore


class HybridRetriever:
    """Fuse semantic + keyword retrieval. Falls back to BM25-only when
    vector_store is None (low-memory deployments)."""

    def __init__(
        self,
        vector_store: VectorStore | None,
        bm25_index: BM25Index,
        rrf_k: int = 60,
    ) -> None:
        self.vector_store = vector_store
        self.bm25 = bm25_index
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        k: int = 5,
        source_filter: list[str] | None = None,
        candidates_per_source: int = 20,
    ) -> list[ScoredChunk]:
        kw = self.bm25.query(
            query, k=candidates_per_source, source_filter=source_filter
        )
        if self.vector_store is None:
            # BM25-only mode — return top-k keyword matches directly.
            return [
                ScoredChunk(chunk=sc.chunk, score=sc.score, rank=rank)
                for rank, sc in enumerate(kw[:k])
            ]
        sem = self.vector_store.query(
            query, k=candidates_per_source, source_filter=source_filter
        )
        return self._rrf_merge(sem, kw, k=k)

    def _rrf_merge(
        self,
        semantic: list[ScoredChunk],
        keyword: list[ScoredChunk],
        k: int,
    ) -> list[ScoredChunk]:
        """Reciprocal Rank Fusion."""
        chunk_by_id: dict[str, Chunk] = {}
        rrf_score: dict[str, float] = defaultdict(float)

        for sc in semantic:
            cid = sc.chunk.chunk_id
            chunk_by_id[cid] = sc.chunk
            rrf_score[cid] += 1.0 / (self.rrf_k + (sc.rank or 0) + 1)
        for sc in keyword:
            cid = sc.chunk.chunk_id
            chunk_by_id.setdefault(cid, sc.chunk)
            rrf_score[cid] += 1.0 / (self.rrf_k + (sc.rank or 0) + 1)

        ranked = sorted(rrf_score.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [
            ScoredChunk(chunk=chunk_by_id[cid], score=score, rank=rank)
            for rank, (cid, score) in enumerate(ranked)
        ]
