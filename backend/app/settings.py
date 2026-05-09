"""Application settings loaded from environment via pydantic-settings."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Provider toggles
    llm_provider: Literal["openai", "groq"] = "openai"
    embedding_provider: Literal[
        "openai", "sentence-transformers", "fastembed", "none"
    ] = "openai"
    # When "none", the system runs BM25-only (no vector store / no embeddings).
    # Suitable for low-memory hosts (e.g. Render free tier 512MB).

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Sentence-transformers
    st_model: str = "all-MiniLM-L6-v2"

    # Fastembed (ONNX runtime — low-memory free path)
    fastembed_model: str = "BAAI/bge-small-en-v1.5"

    # Paths
    data_dir: str = "/app/data"
    chroma_persist_dir: str = "/app/chroma_db"

    # CORS - comma-separated origins
    allowed_origins: str = "http://localhost:3000"

    # Logging
    log_level: str = "INFO"

    # Retrieval tuning
    retrieval_top_k: int = 5
    hybrid_rrf_k: int = 60
    confidence_threshold: float = 0.3

    @property
    def allowed_origins_list(self) -> list[str]:
        """Split CORS origins string to list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton settings accessor."""
    return Settings()
