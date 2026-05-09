"""LLM-driven query router using OpenAI-compatible function calling.

Returns a RouteDecision telling the RAG engine which sources to query and,
optionally, an explicit SELECT statement for SQL aggregations / joins.
"""
from __future__ import annotations

import json
import logging

from app.models.route_decision import RouteDecision
from app.providers.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


ROUTING_TOOL = {
    "type": "function",
    "function": {
        "name": "route_query",
        "description": (
            "Decide which procurement data source(s) to query and, if SQL is "
            "needed, generate a single safe SELECT statement."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["sql_semantic", "sql_query", "pdf", "json", "image"],
                    },
                    "description": (
                        "Sources to query. Use [] when the question is unanswerable "
                        "from available data (e.g. shipping tracking numbers)."
                    ),
                },
                "sql_query": {
                    "type": "string",
                    "description": (
                        "Single SELECT statement (no DML/DDL, no semicolons). "
                        "Required when 'sql_query' is in sources."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": "One-sentence rationale for the chosen sources.",
                },
            },
            "required": ["sources", "reasoning"],
        },
    },
}


_SYSTEM_PROMPT = """You are a query router for a procurement RAG system.

Available data sources:
- sql_semantic: Semantic search over indexed DB rows. Use for vague filtering ("vendors that ship fast").
- sql_query: Run an explicit SELECT (you generate it). Use for aggregates, joins, exact counts, exact lookups by primary key. Prefer this for numeric questions.
- pdf: Vendor catalog with prices, MOQs, certifications visible in catalog. Use for catalog/price questions.
- json: Product technical specifications (voltage, certifications, packaging, marketing). Use for spec questions.
- image: Scanned invoice (PO-2847 only). Use for invoice/OCR questions.

Database schema:
{schema}

Decision rules:
1. If the question asks about "in stock", "stock quantity", "reorder level" — use sql_query with a precise SELECT.
2. If "catalog price" or "MOQ" — use pdf.
3. If "certifications", "wattage", "lumens", "warranty" — use json.
4. If "invoice", "OCR", "scanned" — use image.
5. For comparisons across sources (e.g. catalog vs PO price) — combine the relevant sources.
6. For information that is not in any source (e.g. shipping tracking numbers, vendor SLA, future delivery ETAs) — return sources=[] and explain in reasoning.
7. Always prefer sql_query when an exact answer is computable from the schema; only use sql_semantic as a fallback.

When generating SQL: use only SELECT, no semicolons, valid SQLite syntax.
"""


class QueryRouter:
    """Route a user query to the right data sources."""

    def __init__(self, llm: LLMProvider, schema_ddl: str) -> None:
        self.llm = llm
        self.schema_ddl = schema_ddl

    def route(self, query: str) -> RouteDecision:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT.format(schema=self.schema_ddl)},
            {"role": "user", "content": query},
        ]
        try:
            msg = self.llm.chat(
                messages=messages,
                tools=[ROUTING_TOOL],
                tool_choice={"type": "function", "function": {"name": "route_query"}},
                temperature=0.0,
            )
        except Exception as e:
            logger.warning("Router LLM call failed: %s — falling back to semantic", e)
            return RouteDecision(
                sources=["sql_semantic", "pdf", "json"],
                reasoning="Router error; using fallback semantic across all sources.",
            )

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            logger.warning("Router did not emit tool call; raw msg: %s", msg)
            return RouteDecision(
                sources=["sql_semantic", "pdf", "json"],
                reasoning="No tool call; falling back to semantic across sources.",
            )
        try:
            args = json.loads(tool_calls[0]["function"]["arguments"])
            return RouteDecision(**args)
        except Exception as e:
            logger.exception("Failed to parse router output: %s", e)
            return RouteDecision(
                sources=["sql_semantic"],
                reasoning="Parse error; using semantic fallback.",
            )
