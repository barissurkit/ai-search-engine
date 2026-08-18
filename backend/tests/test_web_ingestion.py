import asyncio
import logging

import pytest

from app.search.models import SearchResult
from app.web.extractor import ContentExtractionError
from app.web.fetcher import WebFetchError
from app.web.ingestion import WebIngestionError, WebIngestionService
from app.web.models import FetchedPage


def search_result(url: str) -> SearchResult:
    return SearchResult(title="Result", url=url, snippet="Snippet")


class FakeFetcher:
    def __init__(self, pages: dict[str, FetchedPage | Exception]) -> None:
        self._pages = pages

    async def fetch(self, url: str) -> FetchedPage:
        page = self._pages[url]
        if isinstance(page, Exception):
            raise page
        return page


class FakeExtractor:
    def extract(self, html: str) -> str:
        if html == "invalid":
            raise ContentExtractionError("meaningful content was unavailable")
        return f"Extracted: {html}"


def test_ingest_converts_search_results_to_documents_and_preserves_metadata():
    first_url = "https://example.com/first"
    second_url = "https://example.com/second"
    fetcher = FakeFetcher(
        {
            first_url: FetchedPage(
                source_url=first_url,
                final_url="https://www.example.com/first",
                html="First content",
            ),
            second_url: FetchedPage(
                source_url=second_url,
                final_url=second_url,
                html="Second content",
            ),
        }
    )
    service = WebIngestionService(fetcher, FakeExtractor(), max_concurrency=2)

    documents = asyncio.run(
        service.ingest([search_result(first_url), search_result(second_url)])
    )

    assert [document.content for document in documents] == [
        "Extracted: First content",
        "Extracted: Second content",
    ]
    assert documents[0].source_url == first_url
    assert documents[0].final_url == "https://www.example.com/first"
    assert documents[1].source_url == second_url
    assert documents[1].final_url == second_url


def test_ingest_keeps_successful_documents_when_some_results_fail(caplog):
    successful_url = "https://example.com/success"
    failed_url = "https://example.com/failed"
    fetcher = FakeFetcher(
        {
            successful_url: FetchedPage(
                source_url=successful_url,
                final_url=successful_url,
                html="Success",
            ),
            failed_url: WebFetchError("request failed"),
        }
    )
    service = WebIngestionService(fetcher, FakeExtractor(), max_concurrency=2)

    with caplog.at_level(logging.WARNING):
        documents = asyncio.run(
            service.ingest([search_result(successful_url), search_result(failed_url)])
        )

    assert [document.content for document in documents] == ["Extracted: Success"]
    assert "Web ingestion failed for a search result." in caplog.messages


def test_ingest_enforces_maximum_concurrency():
    urls = [f"https://example.com/{index}" for index in range(5)]

    class TrackingFetcher:
        def __init__(self) -> None:
            self.active_requests = 0
            self.max_active_requests = 0

        async def fetch(self, url: str) -> FetchedPage:
            self.active_requests += 1
            self.max_active_requests = max(
                self.max_active_requests,
                self.active_requests,
            )
            await asyncio.sleep(0)
            self.active_requests -= 1
            return FetchedPage(source_url=url, final_url=url, html=url)

    fetcher = TrackingFetcher()
    service = WebIngestionService(fetcher, FakeExtractor(), max_concurrency=2)

    asyncio.run(service.ingest([search_result(url) for url in urls]))

    assert fetcher.max_active_requests == 2


def test_ingest_raises_domain_error_when_all_results_fail():
    first_url = "https://example.com/failed-fetch"
    second_url = "https://example.com/failed-extraction"
    fetcher = FakeFetcher(
        {
            first_url: WebFetchError("request failed"),
            second_url: FetchedPage(
                source_url=second_url,
                final_url=second_url,
                html="invalid",
            ),
        }
    )
    service = WebIngestionService(fetcher, FakeExtractor(), max_concurrency=2)

    with pytest.raises(WebIngestionError, match="No search results"):
        asyncio.run(service.ingest([search_result(first_url), search_result(second_url)]))
