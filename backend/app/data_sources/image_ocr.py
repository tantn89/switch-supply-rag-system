"""Image OCR connector for scanned invoices.

Pipeline: PIL → pytesseract → regex parse known invoice fields.
Emits two chunks per image: one with the raw OCR text and one with a
structured summary that the LLM can quote precisely.
"""
import re
from pathlib import Path
from typing import Any

import pytesseract
from PIL import Image, ImageOps

from app.data_sources.chunk_schema import Chunk

# Invoice field patterns. Tolerant of OCR noise (extra whitespace, OCR'd $).
_INVOICE_NO_RE = re.compile(r"Invoice\s*#?\s*([A-Z0-9-]+)", re.IGNORECASE)
_PO_NO_RE = re.compile(r"PO\s*Number[:\s]*([A-Z]+-?\d+)", re.IGNORECASE)
_DATE_RE = re.compile(r"Date[:\s]*([A-Za-z]+\s+\d{1,2},?\s*\d{4})", re.IGNORECASE)
_SUBTOTAL_RE = re.compile(r"Subtotal[:\s]*\$?\s*([\d,]+\.\d{2})", re.IGNORECASE)
_TAX_RE = re.compile(r"Tax[^$]*\$?\s*([\d,]+\.\d{2})", re.IGNORECASE)
_SHIPPING_RE = re.compile(r"Shipping[:\s]*\$?\s*([\d,]+\.\d{2})", re.IGNORECASE)
_TOTAL_RE = re.compile(r"\bTOTAL[:\s]*\$?\s*([\d,]+\.\d{2})", re.IGNORECASE)
# Line items: SKU description [optional qty] unit_price total.
# Tesseract sometimes drops the qty column when it merges with neighbours,
# so qty is optional. We then derive qty = round(line_total / unit_price).
_LINE_ITEM_RE = re.compile(
    r"(SKU-[A-Z]+-\d+)\s+(.+?)\s+(?:(\d+)\s+)?\$?\s*([\d,]+\.\d{2})\s+\$?\s*([\d,]+\.\d{2})"
)


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


class ImageOCR:
    """Extract structured invoice data from a scanned JPEG/PNG."""

    def __init__(self, image_path: str | Path):
        self.image_path = str(image_path)
        self.source_name = Path(image_path).stem  # e.g. "invoice_scan"

    def extract_text(self) -> str:
        # PSM 6 (uniform block of text) gives the best results on this scan
        # — it preserves the PO Number / Date header that PSM 3 (default) drops.
        img = ImageOps.grayscale(Image.open(self.image_path))
        return pytesseract.image_to_string(img, config="--psm 6")

    def parse_invoice(self, raw_text: str) -> dict[str, Any]:
        """Best-effort regex extraction. Missing fields return None."""

        def _first(pattern: re.Pattern, text: str) -> str | None:
            m = pattern.search(text)
            return m.group(1).strip() if m else None

        line_items = []
        for m in _LINE_ITEM_RE.finditer(raw_text):
            unit_price = _to_float(m.group(4))
            line_total = _to_float(m.group(5))
            qty_str = m.group(3)
            qty = (
                int(qty_str)
                if qty_str
                else (round(line_total / unit_price) if unit_price > 0 else 0)
            )
            line_items.append(
                {
                    "sku": m.group(1),
                    "description": m.group(2).strip(),
                    "quantity": qty,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )

        return {
            "invoice_number": _first(_INVOICE_NO_RE, raw_text),
            "po_number": _first(_PO_NO_RE, raw_text),
            "date": _first(_DATE_RE, raw_text),
            "subtotal": _to_float(_first(_SUBTOTAL_RE, raw_text))
            if _first(_SUBTOTAL_RE, raw_text)
            else None,
            "tax": _to_float(_first(_TAX_RE, raw_text))
            if _first(_TAX_RE, raw_text)
            else None,
            "shipping": _to_float(_first(_SHIPPING_RE, raw_text))
            if _first(_SHIPPING_RE, raw_text)
            else None,
            "total": _to_float(_first(_TOTAL_RE, raw_text))
            if _first(_TOTAL_RE, raw_text)
            else None,
            "line_items": line_items,
        }

    def to_chunks(self) -> list[Chunk]:
        raw = self.extract_text()
        parsed = self.parse_invoice(raw)

        raw_chunk = Chunk(
            chunk_id=f"image-{self.source_name}-raw",
            source_id=f"image:{self.source_name}:raw",
            source_type="image",
            content=f"Raw OCR text from {self.source_name}.jpg:\n{raw.strip()}",
            metadata={"image": self.source_name, "kind": "raw_ocr"},
        )

        items_str = (
            "\n".join(
                f"- {li['sku']} x{li['quantity']} @ ${li['unit_price']:.2f} = ${li['line_total']:.2f}"
                for li in parsed["line_items"]
            )
            or "(no line items parsed)"
        )
        structured_content = (
            f"Invoice {parsed.get('invoice_number')} for purchase order "
            f"{parsed.get('po_number')} dated {parsed.get('date')}.\n"
            f"Line items:\n{items_str}\n"
            f"Subtotal: ${parsed.get('subtotal')}, "
            f"Tax: ${parsed.get('tax')}, "
            f"Shipping: ${parsed.get('shipping')}, "
            f"Total: ${parsed.get('total')}."
        )
        structured_chunk = Chunk(
            chunk_id=f"image-{self.source_name}-structured",
            source_id=f"image:{self.source_name}:structured",
            source_type="image",
            content=structured_content,
            metadata={"image": self.source_name, "kind": "parsed_invoice", **parsed},
        )

        return [raw_chunk, structured_chunk]
