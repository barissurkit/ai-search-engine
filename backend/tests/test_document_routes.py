import asyncio

import httpx
import pytest

from app.api.dependencies.rag import get_rag_service
from app.main import app
from app.rag.models import DocumentChunk
from app.rag.service import RAGService, RAGServiceError
from app.retrieval.service import RetrievalServiceError
from app.web.models import Document


class DocumentService:
    def __init__(self, *, fail_index: bool = False, fail_delete: bool = False) -> None:
        self.fail_index = fail_index
        self.fail_delete = fail_delete
        self.index_calls: list[tuple[str, str, str]] = []
        self.delete_calls: list[tuple[str, str | None]] = []

    async def index_file(self, document_id, conversation_id, filename, _pages):
        self.index_calls.append((document_id, conversation_id, filename))
        if self.fail_index:
            raise RAGServiceError("persistence failed")
        return 2

    async def delete_file(self, conversation_id, document_id=None):
        self.delete_calls.append((conversation_id, document_id))
        if self.fail_delete:
            raise RAGServiceError("persistence failed")


class FailingRetrieval:
    async def index(self, _chunks, scope_id):
        raise RetrievalServiceError(f"index failed for {scope_id}")

    async def delete_files(self, _conversation_id, _document_id=None):
        raise RetrievalServiceError("delete failed")


class Chunker:
    def chunk(self, document: Document):
        return [DocumentChunk(content=document.content, source_url=document.source_url, final_url=document.final_url, index=0)]


class FailingChunker:
    def chunk(self, _document: Document):
        raise RuntimeError("chunking failed")


async def request(method: str, path: str, **kwargs: object) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


def with_service(service: DocumentService):
    app.dependency_overrides[get_rag_service] = lambda: service


def clear_service() -> None:
    app.dependency_overrides.clear()


def test_text_upload_returns_ready_metadata_after_successful_indexing():
    service = DocumentService()
    with_service(service)
    try:
        response = asyncio.run(
            request(
                "POST",
                "/api/v1/documents",
                data={"conversation_id": "conversation"},
                files={"file": ("report.txt", b"Revenue grew 15 percent.", "text/plain")},
            )
        )
    finally:
        clear_service()

    assert response.status_code == 201
    assert response.json() == {
        "id": service.index_calls[0][0],
        "conversation_id": "conversation",
        "filename": "report.txt",
        "media_type": "text/plain",
        "page_count": None,
        "chunk_count": 2,
        "status": "ready",
    }


def test_extraction_failure_does_not_index_or_return_ready_metadata():
    service = DocumentService()
    with_service(service)
    try:
        response = asyncio.run(
            request(
                "POST",
                "/api/v1/documents",
                data={"conversation_id": "conversation"},
                files={"file": ("empty.txt", b"", "text/plain")},
            )
        )
    finally:
        clear_service()

    assert response.status_code == 422
    assert service.index_calls == []


def test_index_failure_is_safe_and_does_not_return_document_metadata():
    service = DocumentService(fail_index=True)
    with_service(service)
    try:
        response = asyncio.run(
            request(
                "POST",
                "/api/v1/documents",
                data={"conversation_id": "conversation"},
                files={"file": ("report.txt", b"Revenue grew 15 percent.", "text/plain")},
            )
        )
    finally:
        clear_service()

    assert response.status_code == 502
    assert response.json() == {"detail": "Document could not be indexed."}
    assert len(service.index_calls) == 1


def test_conversation_cleanup_is_idempotent_and_scoped():
    service = DocumentService()
    with_service(service)
    try:
        first = asyncio.run(request("DELETE", "/api/v1/documents?conversation_id=conversation-a"))
        second = asyncio.run(request("DELETE", "/api/v1/documents?conversation_id=conversation-a"))
    finally:
        clear_service()

    assert first.status_code == second.status_code == 204
    assert service.delete_calls == [("conversation-a", None), ("conversation-a", None)]


def test_individual_and_conversation_cleanup_failures_are_safe_gateway_errors():
    service = DocumentService(fail_delete=True)
    with_service(service)
    try:
        individual = asyncio.run(request("DELETE", "/api/v1/documents/document-a?conversation_id=conversation-a"))
        conversation = asyncio.run(request("DELETE", "/api/v1/documents?conversation_id=conversation-a"))
    finally:
        clear_service()

    assert individual.status_code == conversation.status_code == 502
    assert individual.json() == conversation.json() == {"detail": "Document cleanup failed."}
    assert service.delete_calls == [("conversation-a", "document-a"), ("conversation-a", None)]


def test_rag_document_boundary_converts_retrieval_failures_to_safe_errors():
    service = RAGService(None, None, Chunker(), FailingRetrieval(), None, None)

    with pytest.raises(RAGServiceError, match="Document could not be indexed"):
        asyncio.run(service.index_file("document", "conversation", "report.txt", [(None, "Revenue grew 15 percent.")]))
    with pytest.raises(RAGServiceError, match="Document cleanup failed"):
        asyncio.run(service.delete_file("conversation", "document"))


def test_rag_document_boundary_converts_chunking_failures_to_safe_errors():
    service = RAGService(None, None, FailingChunker(), FailingRetrieval(), None, None)

    with pytest.raises(RAGServiceError, match="Document could not be indexed"):
        asyncio.run(service.index_file("document", "conversation", "report.txt", [(None, "Revenue grew 15 percent.")]))
