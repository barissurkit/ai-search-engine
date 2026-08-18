import asyncio

from app.search.models import SearchResult
from app.search.service import SearchService


def test_search_service_calls_provider_with_query_and_returns_results():
    class FakeSearchProvider:
        def __init__(self) -> None:
            self.query = None
            self.results = [
                SearchResult(
                    title="Example result",
                    url="https://example.com/result",
                    snippet="Example snippet.",
                )
            ]

        async def search(self, query: str) -> list[SearchResult]:
            self.query = query
            return self.results

    provider = FakeSearchProvider()
    service = SearchService(provider)

    results = asyncio.run(service.search("artificial intelligence"))

    assert provider.query == "artificial intelligence"
    assert results == provider.results
