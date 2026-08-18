from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "AI Search Engine API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    tavily_api_key: SecretStr | None = None
    tavily_base_url: str = "https://api.tavily.com"
    openai_api_key: SecretStr | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    openai_generation_model: str = "gpt-5.6-terra"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "ai_search_chunks"
    web_fetch_timeout_seconds: float = 10.0
    web_fetch_user_agent: str = "AI-Search-Engine/0.1"
    web_ingestion_max_concurrency: int = 3

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
