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
        "QDRANT_URL",
        "QDRANT_COLLECTION_NAME",
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
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.qdrant_collection_name == "ai_search_chunks"
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
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.test:6333")
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "test_chunks")
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
    assert settings.qdrant_url == "http://qdrant.test:6333"
    assert settings.qdrant_collection_name == "test_chunks"
    assert settings.web_fetch_timeout_seconds == 5.5
    assert settings.web_fetch_user_agent == "Test Fetcher/1.0"
    assert settings.web_ingestion_max_concurrency == 2
    assert "tvly-test-secret" not in repr(settings)
    assert "openai-test-secret" not in repr(settings)
