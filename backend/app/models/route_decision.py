"""Pydantic schemas for query routing and RAG responses."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SourceTag = Literal["sql_semantic", "sql_query", "pdf", "json", "image"]


class RouteDecision(BaseModel):
    """Result of the query router."""

    sources: list[SourceTag] = Field(default_factory=list)
    sql_query: str | None = Field(
        default=None,
        description="Optional SELECT statement to run (only used if 'sql_query' in sources).",
    )
    reasoning: str = ""


class Citation(BaseModel):
    """One retrieved chunk surfaced to the user."""

    source_id: str
    source_type: str
    preview: str = Field(..., description="Short text snippet for tooltip preview")
    score: float | None = None


Confidence = Literal["high", "medium", "low", "none"]


class RAGResponse(BaseModel):
    """Final assistant response."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: Confidence = "medium"
    route: RouteDecision | None = None
    sql_rows: list[dict] | None = None
