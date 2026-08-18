import asyncio
import logging

from app.search.models import SearchResult
from app.web.extractor import ContentExtractionError, ContentExtractor
from app.web.fetcher import WebFetcher, WebFetchError
from app.web.models import Document

logger = logging.getLogger(__name__)


class WebIngestionError(Exception):
    """Raised when no search result can be ingested into a document."""


class WebIngestionService:
    def __init__(
        self,
        fetcher: WebFetcher,
        extractor: ContentExtractor,
        max_concurrency: int,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1.")

        self._fetcher = fetcher
        self._extractor = extractor
        self._max_concurrency = max_concurrency

    async def ingest(self, results: list[SearchResult]) -> list[Document]:
        if not results:
            return []

        semaphore = asyncio.Semaphore(self._max_concurrency)
        documents = await asyncio.gather(
            *(self._ingest_result(result, semaphore) for result in results)
        )
        successful_documents = [document for document in documents if document is not None]

        if not successful_documents:
            raise WebIngestionError("No search results could be ingested.")

        return successful_documents

    async def _ingest_result(
        self,
        result: SearchResult,
        semaphore: asyncio.Semaphore,
    ) -> Document | None:
        try:
            async with semaphore:
                page = await self._fetcher.fetch(str(result.url))
                content = self._extractor.extract(page.html)
            return Document(
                content=content,
                source_url=page.source_url,
                final_url=page.final_url,
            )
        except (WebFetchError, ContentExtractionError):
            logger.warning("Web ingestion failed for a search result.")
            return None
