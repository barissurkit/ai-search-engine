from app.core.config import Settings


def test_settings_defaults(monkeypatch):
    for name in ("APP_NAME", "APP_VERSION", "ENVIRONMENT", "DEBUG"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_name == "AI Search Engine API"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"
    assert settings.debug is False


def test_settings_environment_overrides(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test API")
    monkeypatch.setenv("DEBUG", "true")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Test API"
    assert settings.debug is True
