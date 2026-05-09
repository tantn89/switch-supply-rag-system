"""JSON connector for product technical specifications.

Each product becomes one Chunk with a flattened searchable description and
the full nested object preserved in metadata for downstream LLM consumption.
"""
import json
from pathlib import Path
from typing import Any

from app.data_sources.chunk_schema import Chunk


class JSONLoader:
    """Load product_specs.json and emit per-product chunks."""

    def __init__(self, json_path: str | Path):
        self.json_path = str(json_path)
        self.source_name = Path(json_path).stem

    def load_chunks(self) -> list[Chunk]:
        with open(self.json_path, encoding="utf-8") as f:
            data = json.load(f)

        chunks: list[Chunk] = []
        for product in data.get("products", []):
            chunks.append(self._product_to_chunk(product))
        return chunks

    def _product_to_chunk(self, product: dict[str, Any]) -> Chunk:
        sku = product["sku"]
        tech = product.get("technical_specs", {})
        pkg = product.get("packaging", {})
        mkt = product.get("marketing", {})
        comp = product.get("compliance", {})

        certs = tech.get("certifications", []) or []
        features = mkt.get("features", []) or []
        applications = mkt.get("applications", []) or []

        content = (
            f"Product specifications for {sku}.\n"
            f"Technical: voltage={tech.get('voltage')}, wattage={tech.get('wattage')}, "
            f"lumens={tech.get('lumens')}, color_temperature={tech.get('color_temperature')}, "
            f"lifespan={tech.get('lifespan_hours')} hours, base_type={tech.get('base_type')}, "
            f"dimmable={tech.get('dimmable')}, CRI={tech.get('cri')}.\n"
            f"Certifications: {', '.join(certs) if certs else 'none'}.\n"
            f"Packaging: unit_weight={pkg.get('unit_weight_kg')}kg, case_qty={pkg.get('case_qty')}, "
            f"carton_weight={pkg.get('carton_weight_kg')}kg, pallet_qty={pkg.get('pallet_qty')}.\n"
            f"Marketing: {mkt.get('description', '')}\n"
            f"Features: {'; '.join(features)}.\n"
            f"Applications: {', '.join(applications)}.\n"
            f"Compliance: RoHS={comp.get('rohs')}, REACH={comp.get('reach')}, "
            f"Energy Star={comp.get('energy_star')}, warranty={comp.get('warranty_years')} years."
        )

        return Chunk(
            chunk_id=f"json-{self.source_name}-{sku}",
            source_id=f"json:{self.source_name}:{sku}",
            source_type="json",
            content=content,
            metadata={"sku": sku, "spec": product},
        )
