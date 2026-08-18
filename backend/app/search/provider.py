from typing import Protocol, runtime_checkable

from app.search.models import SearchResult


@runtime_checkable
class SearchProvider(Protocol):
    async def search(self, query: str) -> list[SearchResult]: ...
