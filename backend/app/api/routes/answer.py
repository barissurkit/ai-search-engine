from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies.rag import get_rag_service
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
