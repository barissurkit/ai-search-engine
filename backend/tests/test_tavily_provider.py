import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.search.provider import SearchProvider
from app.search.tavily import (
    TavilyConfigurationError,
    TavilyProviderError,
    TavilySearchProvider,
)


def create_provider(handler, api_key="tvly-test-secret"):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(_env_file=None, debug=False, tavily_api_key=api_key)
    return TavilySearchProvider(settings, client), client


def test_search_normalizes_tavily_response_and_sends_expected_request():
    captured_request = None
    authorization_is_expected = False

    def handler(request):
        nonlocal authorization_is_expected, captured_request
        captured_request = request
        authorization_is_expected = (
            request.headers.get("Authorization") == "Bearer tvly-test-secret"
        )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Example result",
                        "url": "https://example.com/article",
                        "content": "Example snippet.",
                        "score": 0.95,
                    }
                ]
            },
        )

    provider, client = create_provider(handler)
    try:
        results = asyncio.run(provider.search("artificial intelligence"))
    finally:
        asyncio.run(client.aclose())

    assert isinstance(provider, SearchProvider)
    assert results[0].title == "Example result"
    assert str(results[0].url) == "https://example.com/article"
    assert results[0].snippet == "Example snippet."
    assert captured_request.url == "https://api.tavily.com/search"
    assert authorization_is_expected
    assert json.loads(captured_request.content) == {
        "query": "artificial intelligence",
        "search_depth": "basic",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": False,
    }


def test_provider_rejects_missing_api_key():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: None))
    settings = Settings(_env_file=None, debug=False)
    try:
        with pytest.raises(TavilyConfigurationError, match="TAVILY_API_KEY"):
            TavilySearchProvider(settings, client)
    finally:
        asyncio.run(client.aclose())


def test_search_converts_unsuccessful_response_to_provider_error():
    provider, client = create_provider(
        lambda request: httpx.Response(401, request=request)
    )
    try:
        with pytest.raises(TavilyProviderError, match="unsuccessful"):
            asyncio.run(provider.search("test query"))
    finally:
        asyncio.run(client.aclose())


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("connection failed"), httpx.ReadTimeout("timed out")],
)
def test_search_converts_network_errors_to_provider_error(error):
    def handler(request):
        raise error

    provider, client = create_provider(handler)
    try:
        with pytest.raises(TavilyProviderError):
            asyncio.run(provider.search("test query"))
    finally:
        asyncio.run(client.aclose())


def test_search_rejects_response_without_results():
    provider, client = create_provider(
        lambda request: httpx.Response(200, json={"query": "test query"})
    )
    try:
        with pytest.raises(TavilyProviderError, match="did not contain results"):
            asyncio.run(provider.search("test query"))
    finally:
        asyncio.run(client.aclose())
