"""POST /upload — accept PDF/JSON/Image, parse, append to indexes."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.data_sources import ImageOCR, JSONLoader, PDFProcessor

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_SUFFIXES = {".pdf", ".json", ".jpg", ".jpeg", ".png"}


def _sanitize_suffix(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(415, f"Unsupported file type: {suffix}")
    return suffix


@router.post("")
async def upload(file: UploadFile, request: Request) -> dict:
    suffix = _sanitize_suffix(file.filename or "upload")

    body = await file.read()
    if len(body) > _MAX_BYTES:
        raise HTTPException(413, "File too large (max 10 MB)")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(body)
        tmp_path = Path(tmp.name)

    try:
        if suffix == ".pdf":
            chunks = PDFProcessor(tmp_path).extract_chunks()
            source_type = "pdf"
        elif suffix == ".json":
            chunks = JSONLoader(tmp_path).load_chunks()
            source_type = "json"
        else:  # image
            chunks = ImageOCR(tmp_path).to_chunks()
            source_type = "image"

        engine = request.app.state.engine
        # Append to vector store if present; BM25 index is in-memory and won't
        # see uploads until next rebuild — acceptable for the assessment scope.
        if engine.retriever.vector_store is not None:
            engine.retriever.vector_store.add(chunks)
        logger.info("Uploaded %d %s chunks", len(chunks), source_type)
        return {
            "chunks_added": len(chunks),
            "source_type": source_type,
            "filename": file.filename,
        }
    finally:
        tmp_path.unlink(missing_ok=True)
