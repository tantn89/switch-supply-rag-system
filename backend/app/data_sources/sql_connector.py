"""SQLite connector for the procurement database.

Two retrieval paths:
1. `execute()` — runs LLM-generated SELECT queries (for aggregations, joins).
   Hard-whitelisted to SELECT statements only.
2. `index_all()` — emits one Chunk per row, with a human-readable description
   suitable for embedding and BM25 indexing.
"""
import re
import sqlite3
from pathlib import Path
from typing import Any

from app.data_sources.chunk_schema import Chunk

# Only single SELECT statements allowed. Reject any DML/DDL.
_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE | re.DOTALL)
_FORBIDDEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|PRAGMA)\b",
    re.IGNORECASE,
)

# Tables exposed to the routing layer. The actual sqlite_master also contains
# `sqlite_sequence` which we deliberately hide.
ALLOWED_TABLES = ("vendors", "products", "purchase_orders", "po_line_items")


class UnsafeSQLError(ValueError):
    """Raised when the LLM-supplied SQL is not a safe SELECT."""


class SQLConnector:
    """Read-only access to procurement.db with chunk indexing for RAG."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # --- Path 1: direct query (LLM tool calling) ----------------------------
    def execute(self, sql: str, max_rows: int = 200) -> list[dict[str, Any]]:
        """Run a single SELECT and return rows as list of dicts.

        Raises UnsafeSQLError if the query is not a single safe SELECT.
        """
        self._validate(sql)
        with self._connect() as conn:
            cur = conn.execute(sql)
            return [dict(r) for r in cur.fetchmany(max_rows)]

    def _validate(self, sql: str) -> None:
        if not _SELECT_RE.match(sql):
            raise UnsafeSQLError("Only SELECT queries are permitted")
        # No multiple statements
        body = sql.strip().rstrip(";")
        if ";" in body:
            raise UnsafeSQLError("Multiple statements not permitted")
        if _FORBIDDEN_RE.search(body):
            raise UnsafeSQLError("Forbidden keyword detected")

    def get_schema(self) -> str:
        """Return the schema DDL for the LLM router prompt."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name IN ({})".format(
                    ",".join(f"'{t}'" for t in ALLOWED_TABLES)
                )
            ).fetchall()
        return "\n\n".join(r["sql"] for r in rows if r["sql"])

    # --- Path 2: index for semantic + BM25 search --------------------------
    def index_all(self) -> list[Chunk]:
        """Emit one Chunk per row in every allowed table."""
        chunks: list[Chunk] = []
        with self._connect() as conn:
            chunks.extend(self._chunk_vendors(conn))
            chunks.extend(self._chunk_products(conn))
            chunks.extend(self._chunk_purchase_orders(conn))
            chunks.extend(self._chunk_line_items(conn))
        return chunks

    def _chunk_vendors(self, conn: sqlite3.Connection) -> list[Chunk]:
        chunks: list[Chunk] = []
        for r in conn.execute(
            "SELECT vendor_id, vendor_name, contact_email, country, payment_terms FROM vendors"
        ):
            row = dict(r)
            content = (
                f"Vendor {row['vendor_name']} (id={row['vendor_id']}). "
                f"Contact email: {row['contact_email']}. "
                f"Country: {row['country']}. "
                f"Payment terms: {row['payment_terms']}."
            )
            chunks.append(
                Chunk(
                    chunk_id=f"sql-vendors-{row['vendor_id']}",
                    source_id=f"sql:vendors:{row['vendor_id']}",
                    source_type="sql",
                    content=content,
                    metadata={"table": "vendors", **row},
                )
            )
        return chunks

    def _chunk_products(self, conn: sqlite3.Connection) -> list[Chunk]:
        chunks: list[Chunk] = []
        for r in conn.execute(
            """SELECT p.sku, p.product_name, p.category, p.stock_quantity, p.reorder_level,
                      p.unit_cost, p.vendor_id, p.last_updated, v.vendor_name
                 FROM products p LEFT JOIN vendors v ON p.vendor_id = v.vendor_id"""
        ):
            row = dict(r)
            content = (
                f"Product {row['sku']} - {row['product_name']} ({row['category']}). "
                f"Stock quantity: {row['stock_quantity']} units. "
                f"Reorder level: {row['reorder_level']} units. "
                f"Unit cost: ${row['unit_cost']:.2f}. "
                f"Supplied by vendor {row['vendor_name']} (id={row['vendor_id']}). "
                f"Last updated: {row['last_updated']}."
            )
            chunks.append(
                Chunk(
                    chunk_id=f"sql-products-{row['sku']}",
                    source_id=f"sql:products:{row['sku']}",
                    source_type="sql",
                    content=content,
                    metadata={"table": "products", **row},
                )
            )
        return chunks

    def _chunk_purchase_orders(self, conn: sqlite3.Connection) -> list[Chunk]:
        chunks: list[Chunk] = []
        for r in conn.execute(
            """SELECT po.po_number, po.vendor_id, po.order_date, po.status, po.total_amount,
                      po.expected_delivery, v.vendor_name
                 FROM purchase_orders po LEFT JOIN vendors v ON po.vendor_id = v.vendor_id"""
        ):
            row = dict(r)
            content = (
                f"Purchase order {row['po_number']} from vendor {row['vendor_name']} "
                f"(id={row['vendor_id']}). Order date: {row['order_date']}. "
                f"Status: {row['status']}. Total amount: ${row['total_amount']:.2f}. "
                f"Expected delivery: {row['expected_delivery']}."
            )
            chunks.append(
                Chunk(
                    chunk_id=f"sql-purchase_orders-{row['po_number']}",
                    source_id=f"sql:purchase_orders:{row['po_number']}",
                    source_type="sql",
                    content=content,
                    metadata={"table": "purchase_orders", **row},
                )
            )
        return chunks

    def _chunk_line_items(self, conn: sqlite3.Connection) -> list[Chunk]:
        chunks: list[Chunk] = []
        for r in conn.execute(
            """SELECT li.line_id, li.po_number, li.sku, li.quantity, li.unit_price, li.line_total,
                      p.product_name
                 FROM po_line_items li LEFT JOIN products p ON li.sku = p.sku"""
        ):
            row = dict(r)
            content = (
                f"PO line item #{row['line_id']} on {row['po_number']}: "
                f"{row['quantity']} units of {row['sku']} ({row['product_name']}) "
                f"at unit price ${row['unit_price']:.2f}, line total ${row['line_total']:.2f}."
            )
            chunks.append(
                Chunk(
                    chunk_id=f"sql-po_line_items-{row['line_id']}",
                    source_id=f"sql:po_line_items:{row['line_id']}",
                    source_type="sql",
                    content=content,
                    metadata={"table": "po_line_items", **row},
                )
            )
        return chunks
