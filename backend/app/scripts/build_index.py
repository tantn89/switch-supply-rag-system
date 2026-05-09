"""Build (or rebuild) the vector store + BM25 index from data sources.

Run inside the container or with the same env: `python -m app.scripts.build_index`.
Idempotent: existing chunks are upserted by chunk_id.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.data_sources import (
    Chunk,
    ImageOCR,
    JSONLoader,
    PDFProcessor,
    SQLConnector,
)
from app.providers.factory import build_embedding_provider
from app.retrieval import BM25Index, VectorStore
from app.settings import get_settings

logger = logging.getLogger(__name__)


def collect_all_chunks(data_dir: Path) -> list[Chunk]:
    """Run every connector and concatenate their chunks."""
    chunks: list[Chunk] = []

    db = data_dir / "procurement.db"
    if db.exists():
        chunks.extend(SQLConnector(db).index_all())
        logger.info("SQL connector emitted %d chunks", len(chunks))

    pdf = data_dir / "vendor_catalog.pdf"
    if pdf.exists():
        pdf_chunks = PDFProcessor(pdf).extract_chunks()
        chunks.extend(pdf_chunks)
        logger.info("PDF connector emitted %d chunks", len(pdf_chunks))

    json_path = data_dir / "product_specs.json"
    if json_path.exists():
        json_chunks = JSONLoader(json_path).load_chunks()
        chunks.extend(json_chunks)
        logger.info("JSON connector emitted %d chunks", len(json_chunks))

    image = data_dir / "invoice_scan.jpg"
    if image.exists():
        image_chunks = ImageOCR(image).to_chunks()
        chunks.extend(image_chunks)
        logger.info("Image OCR connector emitted %d chunks", len(image_chunks))

    return chunks


def build() -> tuple[VectorStore, BM25Index, list[Chunk]]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    data_dir = Path(settings.data_dir)
    chunks = collect_all_chunks(data_dir)
    if not chunks:
        raise RuntimeError(f"No chunks produced — check data_dir={data_dir}")

    embedder = build_embedding_provider(settings)
    store = VectorStore(
        persist_dir=settings.chroma_persist_dir,
        embedding_provider=embedder,
    )
    store.add(chunks)
    logger.info("Vector store now contains %d chunks", store.count())

    bm25 = BM25Index(chunks)
    logger.info("BM25 indexed %d chunks", len(chunks))

    return store, bm25, chunks


if __name__ == "__main__":
    build()
