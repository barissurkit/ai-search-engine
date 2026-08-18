import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.search.models import SearchResult


class TavilyConfigurationError(ValueError):
    """Raised when Tavily provider configuration is invalid."""


class TavilyProviderError(Exception):
    """Raised when a Tavily search request cannot be completed."""


class TavilySearchProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        api_key = settings.tavily_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise TavilyConfigurationError(
                "TAVILY_API_KEY is required to use TavilySearchProvider."
            )

        self._api_key = api_key
        self._base_url = settings.tavily_base_url.rstrip("/")
        self._client = client

    async def search(self, query: str) -> list[SearchResult]:
        try:
            response = await self._client.post(
                f"{self._base_url}/search",
                headers={
                    "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                },
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TavilyProviderError("Tavily search request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise TavilyProviderError(
                "Tavily search request returned an unsuccessful response."
            ) from exc
        except httpx.RequestError as exc:
            raise TavilyProviderError("Tavily search request failed.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TavilyProviderError("Tavily search response was not valid JSON.") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise TavilyProviderError("Tavily search response did not contain results.")

        try:
            return [
                SearchResult(
                    title=result["title"],
                    url=result["url"],
                    snippet=result["content"],
                )
                for result in payload["results"]
            ]
        except (KeyError, TypeError, ValidationError) as exc:
            raise TavilyProviderError(
                "Tavily search response contained an invalid result."
            ) from exc
