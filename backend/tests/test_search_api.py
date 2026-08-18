import asyncio
from importlib import import_module

import httpx

from app.api.dependencies.search import get_search_service
from app.search.models import SearchResponse, SearchResult
from app.search.service import SearchService
from app.search.tavily import TavilyProviderError


def test_search_endpoint_returns_search_response():
    class FakeSearchProvider:
        async def search(self, query: str) -> list[SearchResult]:
            assert query == "artificial intelligence"
            return [
                SearchResult(
                    title="Example result",
                    url="https://example.com/result",
                    snippet="Example snippet.",
                )
            ]

    async def get_fake_search_service() -> SearchService:
        return SearchService(FakeSearchProvider())

    app = import_module("app.main").app
    app.dependency_overrides[get_search_service] = get_fake_search_service
    try:
        response = asyncio.run(
            _post(app, "/api/v1/search", {"query": "artificial intelligence"})
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert SearchResponse.model_validate(response.json()).query == "artificial intelligence"


def test_search_endpoint_rejects_blank_query():
    class FakeSearchProvider:
        async def search(self, query: str) -> list[SearchResult]:
            raise AssertionError("Provider should not be called for an invalid request.")

    async def get_fake_search_service() -> SearchService:
        return SearchService(FakeSearchProvider())

    app = import_module("app.main").app
    app.dependency_overrides[get_search_service] = get_fake_search_service
    try:
        response = asyncio.run(_post(app, "/api/v1/search", {"query": "   "}))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_search_endpoint_maps_provider_error_to_safe_response():
    class FailingSearchProvider:
        async def search(self, query: str) -> list[SearchResult]:
            raise TavilyProviderError("sensitive upstream detail")

    async def get_failing_search_service() -> SearchService:
        return SearchService(FailingSearchProvider())

    app = import_module("app.main").app
    app.dependency_overrides[get_search_service] = get_failing_search_service
    try:
        response = asyncio.run(_post(app, "/api/v1/search", {"query": "test"}))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "Search provider is unavailable."}


async def _post(app: object, path: str, json: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=json)
