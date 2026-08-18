import asyncio

import pytest
from pydantic import ValidationError

from app.search.models import SearchRequest, SearchResponse, SearchResult
from app.search.provider import SearchProvider


def test_search_request_accepts_valid_query():
    request = SearchRequest(query="  artificial intelligence  ")

    assert request.query == "artificial intelligence"


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_search_request_rejects_blank_query(query):
    with pytest.raises(ValidationError):
        SearchRequest(query=query)


def test_search_result_accepts_expected_fields():
    result = SearchResult(
        title="Example result",
        url="https://example.com/article",
        snippet="An example search result.",
    )

    assert result.title == "Example result"
    assert str(result.url) == "https://example.com/article"
    assert result.snippet == "An example search result."


def test_search_response_carries_multiple_results():
    results = [
        SearchResult(
            title="First result",
            url="https://example.com/first",
            snippet="First snippet.",
        ),
        SearchResult(
            title="Second result",
            url="https://example.com/second",
            snippet="Second snippet.",
        ),
    ]

    response = SearchResponse(query="example query", results=results)

    assert response.query == "example query"
    assert response.results == results


def test_search_provider_contract_supports_async_search():
    class FakeSearchProvider:
        async def search(self, query: str) -> list[SearchResult]:
            return [
                SearchResult(
                    title="Fake result",
                    url="https://example.com/fake",
                    snippet=query,
                )
            ]

    provider = FakeSearchProvider()

    assert isinstance(provider, SearchProvider)
    results = asyncio.run(provider.search("test query"))
    assert results[0].snippet == "test query"
