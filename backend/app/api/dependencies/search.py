from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.search.service import SearchService
from app.search.tavily import TavilyConfigurationError, TavilySearchProvider


async def get_search_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[SearchService]:
    try:
        async with httpx.AsyncClient() as client:
            provider = TavilySearchProvider(settings, client)
            yield SearchService(provider)
    except TavilyConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search provider is not configured.",
        ) from exc
