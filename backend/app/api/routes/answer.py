from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.dependencies.rag import get_rag_service
from app.api.sse import serialize_rag_stream_event
from app.rag.models import RAGAnswer
from app.rag.service import RAGService, RAGServiceError
from app.search.models import SearchRequest

router = APIRouter(prefix="/api/v1", tags=["answer"])


@router.post("/answer", response_model=RAGAnswer, status_code=status.HTTP_200_OK)
async def answer(
    request: SearchRequest,
    service: Annotated[RAGService, Depends(get_rag_service)],
) -> RAGAnswer:
    try:
        return await service.answer(request.query)
    except RAGServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="RAG answer is unavailable.",
        ) from exc


@router.post("/answer/stream", status_code=status.HTTP_200_OK)
async def stream_answer(
    request: SearchRequest,
    service: Annotated[RAGService, Depends(get_rag_service)],
) -> StreamingResponse:
    if not service.supports_streaming:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG streaming is unavailable.",
        )

    async def event_stream() -> AsyncIterator[str]:
        async for event in service.stream_answer(request.query):
            yield serialize_rag_stream_event(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
