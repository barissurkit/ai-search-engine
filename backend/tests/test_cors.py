import asyncio
from importlib import import_module, reload

import httpx

from app.core.config import get_settings


def app_with_origins(monkeypatch, origins: str):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)
    get_settings.cache_clear()
    return reload(import_module("app.main")).app


async def request(app: object, method: str, path: str, **kwargs: object) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def test_cors_allows_configured_origin_preflight_and_post(monkeypatch):
    app = app_with_origins(monkeypatch, "https://web.test")
    origin_headers = {"Origin": "https://web.test"}
    preflight = asyncio.run(
        request(
            app,
            "OPTIONS",
            "/api/v1/answer",
            headers={
                **origin_headers,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    )
    post = asyncio.run(
        request(
            app,
            "POST",
            "/api/v1/answer",
            headers=origin_headers,
            json={"query": "x"},
        )
    )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://web.test"
    assert "POST" in preflight.headers["access-control-allow-methods"]
    assert "content-type" in preflight.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in preflight.headers
    assert post.headers["access-control-allow-origin"] == "https://web.test"


def test_cors_does_not_allow_unconfigured_origin(monkeypatch):
    app = app_with_origins(monkeypatch, "https://web.test")
    response = asyncio.run(
        request(
            app,
            "OPTIONS",
            "/api/v1/answer",
            headers={
                "Origin": "https://other.test",
                "Access-Control-Request-Method": "POST",
            },
        )
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_production_origin_document_delete_preflight(monkeypatch):
    origin = "https://ai-search-engine-wine-three.vercel.app"
    app = app_with_origins(monkeypatch, origin)

    response = asyncio.run(
        request(
            app,
            "OPTIONS",
            "/api/v1/documents?conversation_id=conversation",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "DELETE",
            },
        )
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_cors_preserves_production_origin_upload_preflight(monkeypatch):
    origin = "https://ai-search-engine-wine-three.vercel.app"
    app = app_with_origins(monkeypatch, origin)

    response = asyncio.run(
        request(
            app,
            "OPTIONS",
            "/api/v1/documents",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]
