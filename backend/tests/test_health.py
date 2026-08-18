from importlib import import_module

from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_health_endpoint(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()

    app = import_module("app.main").app
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
