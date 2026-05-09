"""ChromaDB persistent vector store wrapping an EmbeddingProvider.

Collection name is suffixed with the provider name so swapping providers
(e.g. OpenAI ↔ sentence-transformers) does not collide on dimension.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.data_sources.chunk_schema import Chunk, ScoredChunk
from app.providers.embedding_provider import EmbeddingProvider


def _serialise_metadata(meta: dict) -> dict[str, str | int | float | bool]:
    """ChromaDB metadata only accepts scalar values — flatten complex fields."""
    out: dict[str, str | int | float | bool] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v if v is not None else ""
        else:
            # Lists, dicts, nested objects → JSON-encode for round-tripping.
            import json

            out[k] = json.dumps(v, default=str)
    return out


class VectorStore:
    """Thin wrapper over ChromaDB collection + embedding provider."""

    def __init__(
        self,
        persist_dir: str | Path,
        embedding_provider: EmbeddingProvider,
        collection_name: str = "procurement",
    ) -> None:
        self.persist_dir = str(persist_dir)
        self.embed = embedding_provider
        # Suffix collection so different providers (different dims) coexist.
        self.collection_name = f"{collection_name}_{embedding_provider.name.replace('-', '_')}"

        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ----- write ------------------------------------------------------------
    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        ids = [c.chunk_id for c in chunks]
        docs = [c.content for c in chunks]
        metas = [
            _serialise_metadata({"source_type": c.source_type, "source_id": c.source_id, **c.metadata})
            for c in chunks
        ]
        embeddings = self.embed.embed(docs)
        self._collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)

    def clear(self) -> None:
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ----- read -------------------------------------------------------------
    def count(self) -> int:
        return self._collection.count()

    def query(
        self,
        query_text: str,
        k: int = 10,
        source_filter: list[str] | None = None,
    ) -> list[ScoredChunk]:
        """Semantic search; lower distance = higher similarity."""
        q_emb = self.embed.embed([query_text])[0]
        where = {"source_type": {"$in": source_filter}} if source_filter else None
        result = self._collection.query(
            query_embeddings=[q_emb],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        scored: list[ScoredChunk] = []
        for rank, (cid, doc, meta, dist) in enumerate(
            zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            )
        ):
            chunk = Chunk(
                chunk_id=cid,
                content=doc,
                source_id=meta.get("source_id", cid),
                source_type=meta.get("source_type", "sql"),
                metadata={k: v for k, v in meta.items() if k not in {"source_id", "source_type"}},
            )
            # Convert cosine distance (0..2) to similarity (1..-1) for fusion.
            similarity = 1.0 - dist
            scored.append(ScoredChunk(chunk=chunk, score=similarity, rank=rank))
        return scored
