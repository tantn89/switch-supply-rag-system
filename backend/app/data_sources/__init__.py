"""Data source connectors emitting unified Chunk objects."""
from app.data_sources.chunk_schema import Chunk, ScoredChunk, SourceType
from app.data_sources.image_ocr import ImageOCR
from app.data_sources.json_loader import JSONLoader
from app.data_sources.pdf_processor import PDFProcessor
from app.data_sources.sql_connector import SQLConnector, UnsafeSQLError

__all__ = [
    "Chunk",
    "ScoredChunk",
    "SourceType",
    "SQLConnector",
    "UnsafeSQLError",
    "PDFProcessor",
    "JSONLoader",
    "ImageOCR",
]
