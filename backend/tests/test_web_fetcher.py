import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.web.fetcher import WebFetcher, WebFetchError


def create_fetcher(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = Settings(
        _env_file=None,
        debug=False,
        web_fetch_timeout_seconds=3.5,
        web_fetch_user_agent="AI-Search-Engine-Test/1.0",
    )
    return WebFetcher(settings, client), client


def test_fetch_returns_html_and_sends_expected_request():
    captured_request = None

    def handler(request):
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            text="<html><body>Example</body></html>",
            request=request,
        )

    fetcher, client = create_fetcher(handler)
    try:
        page = asyncio.run(fetcher.fetch("https://example.com/article"))
    finally:
        asyncio.run(client.aclose())

    assert page.source_url == "https://example.com/article"
    assert page.final_url == "https://example.com/article"
    assert page.html == "<html><body>Example</body></html>"
    assert captured_request.url == "https://example.com/article"
    assert captured_request.headers["User-Agent"] == "AI-Search-Engine-Test/1.0"


def test_fetch_follows_redirects():
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(
                302,
                headers={"Location": "https://example.com/final"},
                request=request,
            )
        return httpx.Response(200, text="<html>Final</html>", request=request)

    fetcher, client = create_fetcher(handler)
    try:
        page = asyncio.run(fetcher.fetch("https://example.com/start"))
    finally:
        asyncio.run(client.aclose())

    assert page.source_url == "https://example.com/start"
    assert page.final_url == "https://example.com/final"
    assert page.html == "<html>Final</html>"


def test_fetch_converts_unsuccessful_response_to_web_fetch_error():
    fetcher, client = create_fetcher(
        lambda request: httpx.Response(404, request=request)
    )
    try:
        with pytest.raises(WebFetchError, match="unsuccessful"):
            asyncio.run(fetcher.fetch("https://example.com/missing"))
    finally:
        asyncio.run(client.aclose())


def test_fetch_converts_timeout_to_web_fetch_error():
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    fetcher, client = create_fetcher(handler)
    try:
        with pytest.raises(WebFetchError, match="timed out"):
            asyncio.run(fetcher.fetch("https://example.com/slow"))
    finally:
        asyncio.run(client.aclose())


def test_fetch_converts_network_error_to_web_fetch_error():
    def handler(request):
        raise httpx.ConnectError("connection failed", request=request)

    fetcher, client = create_fetcher(handler)
    try:
        with pytest.raises(WebFetchError, match="failed"):
            asyncio.run(fetcher.fetch("https://example.com/unreachable"))
    finally:
        asyncio.run(client.aclose())
