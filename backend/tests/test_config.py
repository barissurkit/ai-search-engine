import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_defaults(monkeypatch):
    for name in (
        "APP_NAME",
        "APP_VERSION",
        "ENVIRONMENT",
        "DEBUG",
        "TAVILY_API_KEY",
        "TAVILY_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_EMBEDDING_MODEL",
        "OPENAI_EMBEDDING_DIMENSIONS",
        "OPENAI_GENERATION_MODEL",
        "LLM_PROVIDER",
        "EMBEDDING_PROVIDER",
        "OLLAMA_BASE_URL",
        "OLLAMA_API_KEY",
        "OLLAMA_GENERATION_MODEL",
        "OLLAMA_EMBEDDING_MODEL",
        "OLLAMA_EMBEDDING_DIMENSIONS",
        "OLLAMA_REQUEST_TIMEOUT_SECONDS",
        "RAG_RETRIEVAL_TOP_K",
        "RETRIEVAL_CANDIDATE_MULTIPLIER",
        "RETRIEVAL_MAX_CHUNKS_PER_SOURCE",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "QDRANT_COLLECTION_NAME",
        "CORS_ALLOWED_ORIGINS",
        "WEB_FETCH_TIMEOUT_SECONDS",
        "WEB_FETCH_USER_AGENT",
        "WEB_INGESTION_MAX_CONCURRENCY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "AI Search Engine API"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.tavily_api_key is None
    assert settings.tavily_base_url == "https://api.tavily.com"
    assert settings.openai_api_key is None
    assert settings.openai_embedding_model == "text-embedding-3-small"
    assert settings.openai_embedding_dimensions == 1536
    assert settings.openai_generation_model == "gpt-5.6-terra"
    assert settings.llm_provider == "ollama"
    assert settings.embedding_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_api_key is None
    assert settings.ollama_generation_model == "qwen3:4b-instruct"
    assert settings.ollama_embedding_model == "embeddinggemma"
    assert settings.ollama_embedding_dimensions == 768
    assert settings.ollama_request_timeout_seconds == 120.0
    assert settings.rag_retrieval_top_k == 5
    assert settings.retrieval_candidate_multiplier == 3
    assert settings.retrieval_max_chunks_per_source == 1
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.qdrant_api_key is None
    assert settings.qdrant_collection_name == "ai_search_chunks"
    assert settings.cors_allowed_origins == ()
    assert settings.web_fetch_timeout_seconds == 10.0
    assert settings.web_fetch_user_agent == "AI-Search-Engine/0.1"
    assert settings.web_ingestion_max_concurrency == 3


def test_settings_environment_overrides(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test API")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-secret")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "test-embedding-model")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "8")
    monkeypatch.setenv("OPENAI_GENERATION_MODEL", "test-generation-model")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-test-secret")
    monkeypatch.setenv("OLLAMA_GENERATION_MODEL", "test-ollama-generation")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "test-ollama-embedding")
    monkeypatch.setenv("OLLAMA_EMBEDDING_DIMENSIONS", "12")
    monkeypatch.setenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("RAG_RETRIEVAL_TOP_K", "7")
    monkeypatch.setenv("RETRIEVAL_CANDIDATE_MULTIPLIER", "4")
    monkeypatch.setenv("RETRIEVAL_MAX_CHUNKS_PER_SOURCE", "2")
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.test:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "qdrant-test-secret")
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "test_chunks")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " https://web.test,https://admin.test ")
    monkeypatch.setenv("WEB_FETCH_TIMEOUT_SECONDS", "5.5")
    monkeypatch.setenv("WEB_FETCH_USER_AGENT", "Test Fetcher/1.0")
    monkeypatch.setenv("WEB_INGESTION_MAX_CONCURRENCY", "2")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Test API"
    assert settings.debug is True
    assert settings.tavily_api_key is not None
    assert settings.tavily_api_key.get_secret_value() == "tvly-test-secret"
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "openai-test-secret"
    assert settings.openai_embedding_model == "test-embedding-model"
    assert settings.openai_embedding_dimensions == 8
    assert settings.openai_generation_model == "test-generation-model"
    assert settings.llm_provider == "openai"
    assert settings.embedding_provider == "openai"
    assert settings.ollama_base_url == "http://ollama.test"
    assert settings.ollama_api_key is not None
    assert settings.ollama_api_key.get_secret_value() == "ollama-test-secret"
    assert settings.ollama_generation_model == "test-ollama-generation"
    assert settings.ollama_embedding_model == "test-ollama-embedding"
    assert settings.ollama_embedding_dimensions == 12
    assert settings.ollama_request_timeout_seconds == 30.0
    assert settings.rag_retrieval_top_k == 7
    assert settings.retrieval_candidate_multiplier == 4
    assert settings.retrieval_max_chunks_per_source == 2
    assert settings.qdrant_url == "http://qdrant.test:6333"
    assert settings.qdrant_api_key is not None
    assert settings.qdrant_api_key.get_secret_value() == "qdrant-test-secret"
    assert settings.qdrant_collection_name == "test_chunks"
    assert settings.cors_allowed_origins == ("https://web.test", "https://admin.test")
    assert settings.web_fetch_timeout_seconds == 5.5
    assert settings.web_fetch_user_agent == "Test Fetcher/1.0"
    assert settings.web_ingestion_max_concurrency == 2
    assert "tvly-test-secret" not in repr(settings)
    assert "openai-test-secret" not in repr(settings)
    assert "ollama-test-secret" not in repr(settings)
    assert "qdrant-test-secret" not in repr(settings)


def test_cors_origins_normalize_whitespace_blanks_and_duplicates():
    settings = Settings(
        _env_file=None,
        cors_allowed_origins=" https://web.test, ,https://admin.test,https://web.test ",
    )

    assert settings.cors_allowed_origins == ("https://web.test", "https://admin.test")


def test_production_configuration_smoke_parses_remote_services_without_exposing_secrets():
    settings = Settings(
        _env_file=None,
        qdrant_url="https://qdrant.test",
        qdrant_api_key="qdrant-production-secret",
        ollama_base_url="https://ollama.test",
        ollama_api_key="ollama-production-secret",
        cors_allowed_origins="https://web.test",
    )

    assert settings.qdrant_url == "https://qdrant.test"
    assert settings.ollama_base_url == "https://ollama.test"
    assert settings.cors_allowed_origins == ("https://web.test",)
    assert "qdrant-production-secret" not in repr(settings)
    assert "ollama-production-secret" not in repr(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("retrieval_candidate_multiplier", 0),
        ("retrieval_candidate_multiplier", -1),
        ("retrieval_max_chunks_per_source", 0),
        ("retrieval_max_chunks_per_source", -1),
    ],
)
def test_retrieval_diversification_settings_require_positive_values(field: str, value: int):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
