from app.core.config import Settings


def test_settings_defaults(monkeypatch):
    for name in (
        "APP_NAME",
        "APP_VERSION",
        "ENVIRONMENT",
        "DEBUG",
        "TAVILY_API_KEY",
        "TAVILY_BASE_URL",
        "WEB_FETCH_TIMEOUT_SECONDS",
        "WEB_FETCH_USER_AGENT",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "AI Search Engine API"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.tavily_api_key is None
    assert settings.tavily_base_url == "https://api.tavily.com"
    assert settings.web_fetch_timeout_seconds == 10.0
    assert settings.web_fetch_user_agent == "AI-Search-Engine/0.1"


def test_settings_environment_overrides(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test API")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test-secret")
    monkeypatch.setenv("WEB_FETCH_TIMEOUT_SECONDS", "5.5")
    monkeypatch.setenv("WEB_FETCH_USER_AGENT", "Test Fetcher/1.0")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Test API"
    assert settings.debug is True
    assert settings.tavily_api_key is not None
    assert settings.tavily_api_key.get_secret_value() == "tvly-test-secret"
    assert settings.web_fetch_timeout_seconds == 5.5
    assert settings.web_fetch_user_agent == "Test Fetcher/1.0"
    assert "tvly-test-secret" not in repr(settings)
