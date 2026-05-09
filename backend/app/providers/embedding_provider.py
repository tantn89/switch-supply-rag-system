"""Embedding provider abstraction.

Two implementations are wired through the factory:
- OpenAI text-embedding-3-small (1536d) — paid, hosted.
- sentence-transformers all-MiniLM-L6-v2 (384d) — free, local CPU.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    name: str
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per input text."""


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI hosted embeddings (text-embedding-3-small by default)."""

    name = "openai"
    dimension = 1536

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Batch up to 100 at a time to stay well under request limits.
        out: list[list[float]] = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            resp = self._client.embeddings.create(model=self.model, input=batch)
            out.extend(d.embedding for d in resp.data)
        return out


class SentenceTransformerProvider(EmbeddingProvider):
    """Local CPU embeddings via sentence-transformers (free, but heavy ~500MB)."""

    name = "sentence-transformers"
    dimension = 384  # all-MiniLM-L6-v2

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Lazy import — sentence-transformers pulls torch (~500MB).
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        # Override dimension based on the actual loaded model in case the
        # caller swaps to a larger encoder.
        self.dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]


class FastEmbedProvider(EmbeddingProvider):
    """ONNX-runtime embeddings via fastembed (Qdrant). Free, ~150MB RAM total.

    Designed for low-memory environments (Render free 512MB tier).
    Default model is BAAI/bge-small-en-v1.5 — 384d, ~33MB cached.
    """

    name = "fastembed"
    dimension = 384

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        # Lazy import to keep startup fast when this provider isn't selected.
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        # fastembed exposes the dimension via the model registry.
        for entry in TextEmbedding.list_supported_models():
            if entry.get("model") == model_name:
                self.dimension = int(entry.get("dim", self.dimension))
                break

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [v.tolist() for v in self._model.embed(texts)]
