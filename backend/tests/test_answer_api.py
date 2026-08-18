import asyncio
from importlib import import_module

import httpx

from app.api.dependencies.rag import get_rag_service
from app.rag.models import CitationSource, RAGAnswer
from app.rag.service import RAGServiceError


async def post_answer(app: object, json: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/answer", json=json)


def test_answer_endpoint_returns_rag_answer():
    class FakeRAGService:
        async def answer(self, query: str) -> RAGAnswer:
            assert query == "What is RAG?"
            return RAGAnswer(
                query=query,
                answer="A retrieval approach [1].",
                sources=[CitationSource(citation_number=1, url="https://example.com/source")],
            )

    async def get_fake_rag_service() -> FakeRAGService:
        return FakeRAGService()

    app = import_module("app.main").app
    app.dependency_overrides[get_rag_service] = get_fake_rag_service
    try:
        response = asyncio.run(post_answer(app, {"query": "What is RAG?"}))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "query": "What is RAG?",
        "answer": "A retrieval approach [1].",
        "sources": [
            {
                "citation_number": 1,
                "url": "https://example.com/source",
                "title": None,
            }
        ],
    }


def test_answer_endpoint_maps_rag_errors_to_a_safe_response():
    class FailingRAGService:
        async def answer(self, query: str) -> RAGAnswer:
            raise RAGServiceError("sensitive provider detail")

    async def get_failing_rag_service() -> FailingRAGService:
        return FailingRAGService()

    app = import_module("app.main").app
    app.dependency_overrides[get_rag_service] = get_failing_rag_service
    try:
        response = asyncio.run(post_answer(app, {"query": "Question"}))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {"detail": "RAG answer is unavailable."}
