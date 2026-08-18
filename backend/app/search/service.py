from app.search.models import SearchResult
from app.search.provider import SearchProvider


class SearchService:
    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    async def search(self, query: str) -> list[SearchResult]:
        return await self._provider.search(query)
