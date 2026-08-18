import asyncio
from importlib import import_module

import httpx

from app.core.config import get_settings


def test_health_endpoint(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    get_settings.cache_clear()

    app = import_module("app.main").app
    response = asyncio.run(_get_health(app))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def _get_health(app: object) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/health")
