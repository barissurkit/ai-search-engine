import asyncio
import json
from importlib import import_module

import httpx

from app.api.dependencies.rag import get_rag_service
from app.rag.models import (
    CitationSource,
    RAGAnswer,
    RAGStreamComplete,
    RAGStreamDelta,
    RAGStreamError,
    RAGStreamProgress,
    RAGStreamSources,
)
from app.rag.service import RAGServiceError


async def post_answer(app: object, json: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/answer", json=json)


async def post_stream_answer(app: object, json: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post("/api/v1/answer/stream", json=json)


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


def test_stream_answer_endpoint_serializes_ordered_events():
    class FakeStreamingRAGService:
        supports_streaming = True

        async def stream_answer(self, query: str):
            assert query == "What is RAG?"
            yield RAGStreamProgress(stage="searching")
            yield RAGStreamProgress(stage="ingesting")
            yield RAGStreamProgress(stage="retrieving")
            yield RAGStreamProgress(stage="generating")
            yield RAGStreamDelta(text="A retrieval ")
            yield RAGStreamDelta(text="approach [1].")
            yield RAGStreamSources(
                sources=[CitationSource(citation_number=1, url="https://example.com/source")]
            )
            yield RAGStreamComplete()

    async def get_fake_rag_service() -> FakeStreamingRAGService:
        return FakeStreamingRAGService()

    app = import_module("app.main").app
    app.dependency_overrides[get_rag_service] = get_fake_rag_service
    try:
        response = asyncio.run(post_stream_answer(app, {"query": "What is RAG?"}))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    messages = response.text.strip().split("\n\n")
    assert [message.split("\n", maxsplit=1)[0] for message in messages] == [
        "event: progress",
        "event: progress",
        "event: progress",
        "event: progress",
        "event: delta",
        "event: delta",
        "event: sources",
        "event: complete",
    ]
    assert [
        message.split("data: ", maxsplit=1)[1]
        for message in messages[4:6]
    ] == ['{"text":"A retrieval "}', '{"text":"approach [1]."}']
    assert json.loads(messages[-2].split("data: ", maxsplit=1)[1]) == {
        "sources": [
            {"citation_number": 1, "url": "https://example.com/source", "title": None}
        ]
    }


def test_stream_answer_endpoint_serializes_safe_error_without_complete():
    class FailingStreamingRAGService:
        supports_streaming = True

        async def stream_answer(self, query: str):
            yield RAGStreamProgress(stage="searching")
            yield RAGStreamError(message="RAG answer is unavailable.")

    async def get_failing_rag_service() -> FailingStreamingRAGService:
        return FailingStreamingRAGService()

    app = import_module("app.main").app
    app.dependency_overrides[get_rag_service] = get_failing_rag_service
    try:
        response = asyncio.run(post_stream_answer(app, {"query": "Question"}))
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "event: error\ndata: {\"message\":\"RAG answer is unavailable.\"}" in response.text
    assert "event: complete" not in response.text
    assert "secret" not in response.text


def test_stream_answer_endpoint_rejects_unsupported_provider_and_invalid_query():
    class NonStreamingRAGService:
        supports_streaming = False

    async def get_non_streaming_rag_service() -> NonStreamingRAGService:
        return NonStreamingRAGService()

    app = import_module("app.main").app
    app.dependency_overrides[get_rag_service] = get_non_streaming_rag_service
    try:
        unsupported = asyncio.run(post_stream_answer(app, {"query": "Question"}))
        invalid = asyncio.run(post_stream_answer(app, {"query": "  "}))
    finally:
        app.dependency_overrides.clear()

    assert unsupported.status_code == 503
    assert unsupported.json() == {"detail": "RAG streaming is unavailable."}
    assert invalid.status_code == 422
