from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.search import get_search_service
from app.search.models import SearchRequest, SearchResponse
from app.search.service import SearchService
from app.search.tavily import TavilyProviderError

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search(
    request: SearchRequest,
    service: Annotated[SearchService, Depends(get_search_service)],
) -> SearchResponse:
    try:
        results = await service.search(request.query)
    except TavilyProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Search provider is unavailable.",
        ) from exc

    return SearchResponse(query=request.query, results=results)
