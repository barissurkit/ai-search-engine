from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.dependencies.rag import get_rag_service
from app.core.config import get_settings
from app.documents.extractor import extract_document
from app.documents.models import DocumentExtractionError
from app.rag.service import RAGService, RAGServiceError

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


class UploadedDocument(BaseModel):
    id: str
    conversation_id: str
    filename: str
    media_type: str
    page_count: int | None
    chunk_count: int
    status: str = "ready"


@router.post("", response_model=UploadedDocument, status_code=status.HTTP_201_CREATED)
async def upload_document(conversation_id: Annotated[str, Form()], file: Annotated[UploadFile, File()], service: Annotated[RAGService, Depends(get_rag_service)]) -> UploadedDocument:
    settings = get_settings()
    content = await file.read(settings.document_max_upload_bytes + 1)
    if len(content) > settings.document_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File is too large.")
    try:
        extracted = extract_document(file.filename or "upload", content, settings.document_max_extracted_characters, settings.document_max_pdf_pages)
    except DocumentExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    document_id = str(uuid4())
    try:
        chunk_count = await service.index_file(document_id, conversation_id, extracted.filename, extracted.pages)
    except RAGServiceError as exc:
        raise HTTPException(status_code=502, detail="Document could not be indexed.") from exc
    return UploadedDocument(id=document_id, conversation_id=conversation_id, filename=extracted.filename, media_type=extracted.media_type, page_count=len(extracted.pages) if extracted.media_type == "application/pdf" else None, chunk_count=chunk_count)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, conversation_id: str, service: Annotated[RAGService, Depends(get_rag_service)]) -> None:
    try:
        await service.delete_file(conversation_id, document_id)
    except RAGServiceError as exc:
        raise HTTPException(status_code=502, detail="Document cleanup failed.") from exc


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation_documents(conversation_id: str, service: Annotated[RAGService, Depends(get_rag_service)]) -> None:
    try:
        await service.delete_file(conversation_id)
    except RAGServiceError as exc:
        raise HTTPException(status_code=502, detail="Document cleanup failed.") from exc
