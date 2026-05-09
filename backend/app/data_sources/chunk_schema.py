"""Unified Chunk schema returned by every data source connector.

A Chunk is the smallest indexable unit fed to the embedding + BM25 pipeline.
The `source_id` doubles as the citation token surfaced in LLM responses.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal["sql", "pdf", "json", "image"]


class Chunk(BaseModel):
    """Single retrievable chunk with provenance metadata."""

    chunk_id: str = Field(..., description="Globally unique chunk identifier")
    content: str = Field(..., description="Text body fed to embedding + BM25")
    source_id: str = Field(
        ...,
        description="Citation token (e.g. 'sql:vendors:1', 'pdf:vendor_catalog:p2')",
    )
    source_type: SourceType
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw row, page number, SKU, or any structured payload",
    )


class ScoredChunk(BaseModel):
    """Chunk with a retrieval score (semantic, BM25, or fused)."""

    chunk: Chunk
    score: float
    rank: int | None = None
