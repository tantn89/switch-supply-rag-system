"""BM25 keyword index over chunk content.

Pure in-memory; rebuild from scratch each startup. Good for ~10k chunks.
"""
from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

from app.data_sources.chunk_schema import Chunk, ScoredChunk

_TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    """In-memory BM25 over a fixed list of chunks."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = list(chunks)
        self._tokenized = [_tokenize(c.content) for c in self.chunks]
        self._bm25 = BM25Okapi(self._tokenized)

    def query(
        self,
        query: str,
        k: int = 10,
        source_filter: list[str] | None = None,
    ) -> list[ScoredChunk]:
        scores = self._bm25.get_scores(_tokenize(query))
        # Optionally mask out chunks not matching the source filter.
        if source_filter is not None:
            allowed = set(source_filter)
            mask = np.array(
                [c.source_type in allowed for c in self.chunks], dtype=bool
            )
            scores = np.where(mask, scores, -np.inf)
        # Take top-k by descending score.
        top_idx = np.argsort(scores)[::-1][:k]
        results: list[ScoredChunk] = []
        for rank, idx in enumerate(top_idx):
            score = float(scores[idx])
            if not np.isfinite(score):
                break  # Filtered-out chunks land here.
            results.append(ScoredChunk(chunk=self.chunks[idx], score=score, rank=rank))
        return results
