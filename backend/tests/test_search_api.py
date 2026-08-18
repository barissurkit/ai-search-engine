from importlib import import_module

from fastapi.testclient import TestClient

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

    app = import_module("app.main").app
    app.dependency_overrides[get_search_service] = lambda: SearchService(
        FakeSearchProvider()
    )
    try:
        response = TestClient(app).post(
            "/api/v1/search", json={"query": "artificial intelligence"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert SearchResponse.model_validate(response.json()).query == "artificial intelligence"


def test_search_endpoint_rejects_blank_query():
    class FakeSearchProvider:
        async def search(self, query: str) -> list[SearchResult]:
            raise AssertionError("Provider should not be called for an invalid request.")

    app = import_module("app.main").app
    app.dependency_overrides[get_search_service] = lambda: SearchService(
        FakeSearchProvider()
    )
    try:
        response = TestClient(app).post("/api/v1/search", json={"query": "   "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_search_endpoint_maps_provider_error_to_safe_response():
    class FailingSearchProvider:
        async def search(self, query: str) -> list[SearchResult]:
            raise TavilyProviderError("sensitive upstream detail")

    app = import_module("app.main").app
    app.dependency_overrides[get_search_service] = lambda: SearchService(
        FailingSearchProvider()
    )
    try:
        response = TestClient(app).post("/api/v1/search", json={"query": "test"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "Search provider is unavailable."}
