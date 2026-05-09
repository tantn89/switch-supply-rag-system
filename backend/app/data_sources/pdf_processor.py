"""PDF connector for the vendor catalog.

Strategy:
1. Extract text per page with pdfplumber.
2. Concatenate while remembering page boundaries.
3. Split by SKU header regex into product blocks.
4. Emit one Chunk per product (preserving page span) plus separate chunks
   for the cover info and the terms section.
"""
import re
from pathlib import Path

import pdfplumber

from app.data_sources.chunk_schema import Chunk

# Catalog SKUs appear at line start, optionally followed by the product name
# on the same line (pdfplumber tends to collapse the SKU/title pair).
_SKU_RE = re.compile(r"^(SKU-[A-Z]+-\d+)\b", re.MULTILINE)


class PDFProcessor:
    """Parse the vendor catalog PDF into chunks suitable for RAG."""

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = str(pdf_path)
        self.catalog_name = Path(pdf_path).stem  # used in source_id

    def extract_chunks(self) -> list[Chunk]:
        """Return all chunks: header, per-SKU product blocks, terms."""
        full_text, page_offsets = self._extract_text_with_offsets()
        chunks: list[Chunk] = []

        sku_matches = list(_SKU_RE.finditer(full_text))

        # Header (cover info up to first SKU)
        header_end = sku_matches[0].start() if sku_matches else len(full_text)
        header_text = full_text[:header_end].strip()
        if header_text:
            chunks.append(self._mk_chunk("header", header_text, page_offsets, 0, header_end))

        # Per-SKU blocks
        for i, m in enumerate(sku_matches):
            sku = m.group(1)
            start = m.start()
            end = sku_matches[i + 1].start() if i + 1 < len(sku_matches) else len(full_text)
            block = full_text[start:end].strip()
            chunks.append(self._mk_chunk(sku, block, page_offsets, start, end, sku=sku))

        # Trailing terms section after the last SKU's pricing block.
        # We detect it by the "Important Notes" marker if present.
        notes_match = re.search(r"Important Notes:.*", full_text, re.DOTALL)
        if notes_match:
            chunks.append(
                self._mk_chunk(
                    "terms",
                    notes_match.group(0).strip(),
                    page_offsets,
                    notes_match.start(),
                    len(full_text),
                )
            )

        return chunks

    # --- helpers ----------------------------------------------------------
    def _extract_text_with_offsets(self) -> tuple[str, list[tuple[int, int]]]:
        """Concatenate page texts; return (full_text, offsets[(start,page_no)])."""
        parts: list[str] = []
        offsets: list[tuple[int, int]] = []
        cursor = 0
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "") + "\n"
                offsets.append((cursor, page_no))
                parts.append(text)
                cursor += len(text)
        return "".join(parts), offsets

    @staticmethod
    def _pages_for_span(
        offsets: list[tuple[int, int]], start: int, end: int
    ) -> list[int]:
        """Return sorted unique page numbers spanned by [start, end)."""
        pages = set()
        for i, (off, pg) in enumerate(offsets):
            next_off = offsets[i + 1][0] if i + 1 < len(offsets) else float("inf")
            if start < next_off and end > off:
                pages.add(pg)
        return sorted(pages)

    def _mk_chunk(
        self,
        slug: str,
        content: str,
        offsets: list[tuple[int, int]],
        start: int,
        end: int,
        sku: str | None = None,
    ) -> Chunk:
        pages = self._pages_for_span(offsets, start, end)
        page_label = "p" + "-".join(str(p) for p in pages) if pages else "p?"
        meta: dict = {"pages": pages, "catalog": self.catalog_name}
        if sku:
            meta["sku"] = sku
        return Chunk(
            chunk_id=f"pdf-{self.catalog_name}-{slug}",
            source_id=f"pdf:{self.catalog_name}:{page_label}:{slug}",
            source_type="pdf",
            content=content,
            metadata=meta,
        )
