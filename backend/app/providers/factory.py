"""Factory functions to instantiate LLM and embedding providers from settings."""
from __future__ import annotations

from app.providers.embedding_provider import (
    EmbeddingProvider,
    FastEmbedProvider,
    OpenAIEmbeddingProvider,
    SentenceTransformerProvider,
)
from app.providers.llm_provider import GroqProvider, LLMProvider, OpenAIProvider
from app.settings import Settings


def build_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    """Pick an embedding provider based on settings.embedding_provider.

    Returns None when EMBEDDING_PROVIDER=none — caller skips vector store
    and runs in BM25-only mode (low-memory hosts).
    """
    name = settings.embedding_provider
    if name == "none":
        return None
    if name == "openai":
        if not settings.openai_api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY in env"
            )
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )
    if name == "sentence-transformers":
        return SentenceTransformerProvider(model_name=settings.st_model)
    if name == "fastembed":
        return FastEmbedProvider(model_name=settings.fastembed_model)
    raise ValueError(f"Unknown embedding provider: {name}")


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Pick an LLM provider based on settings.llm_provider."""
    name = settings.llm_provider
    if name == "openai":
        if not settings.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai requires OPENAI_API_KEY in env")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    if name == "groq":
        if not settings.groq_api_key:
            raise ValueError("LLM_PROVIDER=groq requires GROQ_API_KEY in env")
        return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)
    raise ValueError(f"Unknown LLM provider: {name}")
