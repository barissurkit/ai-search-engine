import httpx

from app.core.config import Settings
from app.web.models import FetchedPage


class WebFetchError(Exception):
    """Raised when a web page cannot be fetched safely."""


class WebFetcher:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._client = client
        self._timeout = httpx.Timeout(settings.web_fetch_timeout_seconds)
        self._headers = {"User-Agent": settings.web_fetch_user_agent}

    async def fetch(self, url: str) -> FetchedPage:
        try:
            response = await self._client.get(
                url,
                headers=self._headers,
                follow_redirects=True,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise WebFetchError("Web fetch request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise WebFetchError(
                "Web fetch request returned an unsuccessful response."
            ) from exc
        except httpx.RequestError as exc:
            raise WebFetchError("Web fetch request failed.") from exc

        return FetchedPage(source_url=url, final_url=str(response.url), html=response.text)
