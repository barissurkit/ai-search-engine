import asyncio
from collections.abc import AsyncIterator
from typing import Literal

from app.llm.provider import LLMProvider, StreamingLLMProvider
from app.rag.chunking import DocumentChunker
from app.rag.conversation import bound_history, compose_search_query
from app.rag.models import (
    RAGAnswer,
    RAGPrompt,
    RAGStreamComplete,
    RAGStreamDelta,
    RAGStreamError,
    RAGStreamEvent,
    RAGStreamProgress,
    RAGStreamSources,
)
from app.rag.prompt import RAGPromptBuilder
from app.retrieval.service import RetrievalService
from app.search.models import ConversationTurn
from app.search.service import SearchService
from app.web.ingestion import WebIngestionService


class RAGServiceError(Exception):
    """Raised when a retrieval-grounded answer cannot be produced safely."""


class RAGService:
    def __init__(
        self,
        search_service: SearchService,
        ingestion_service: WebIngestionService,
        chunker: DocumentChunker,
        retrieval_service: RetrievalService,
        prompt_builder: RAGPromptBuilder,
        llm_provider: LLMProvider,
        retrieval_top_k: int = 5,
    ) -> None:
        if retrieval_top_k < 1:
            raise RAGServiceError("RAG retrieval top_k must be at least 1.")

        self._search_service = search_service
        self._ingestion_service = ingestion_service
        self._chunker = chunker
        self._retrieval_service = retrieval_service
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider
        self._retrieval_top_k = retrieval_top_k

    async def answer(self, query: str, history: list[ConversationTurn] | None = None) -> RAGAnswer:
        prompt = await self._prepare_prompt(query, history)
        generated_answer = await self._generate(prompt.prompt)

        return RAGAnswer(
            query=query,
            answer=generated_answer,
            sources=prompt.sources,
        )

    @property
    def supports_streaming(self) -> bool:
        return isinstance(self._llm_provider, StreamingLLMProvider)

    async def stream_answer(self, query: str, history: list[ConversationTurn] | None = None) -> AsyncIterator[RAGStreamEvent]:
        """Run the normal RAG pipeline while exposing provider-independent events."""
        try:
            async for stage, prompt in self._prepare_prompt_stages(query, history):
                yield RAGStreamProgress(stage=stage)

            assert prompt is not None
            if not self.supports_streaming:
                raise RAGServiceError("Streaming answer generation is unavailable.")
            async for text in self._llm_provider.stream(prompt.prompt):
                if text:
                    yield RAGStreamDelta(text=text)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - provider implementations are intentionally opaque
            yield RAGStreamError(message="RAG answer is unavailable.")
            return

        yield RAGStreamSources(sources=prompt.sources)
        yield RAGStreamComplete()

    async def _prepare_prompt(self, query: str, history: list[ConversationTurn] | None = None) -> RAGPrompt:
        prompt: RAGPrompt | None = None
        async for _, prompt in self._prepare_prompt_stages(query, history):
            pass
        assert prompt is not None
        return prompt

    async def _prepare_prompt_stages(
        self, query: str, history: list[ConversationTurn] | None = None
    ) -> AsyncIterator[tuple[Literal["searching", "ingesting", "retrieving", "generating"], RAGPrompt | None]]:
        if not isinstance(query, str) or not query.strip():
            raise RAGServiceError("RAG query must not be empty.")

        bounded_history = bound_history(history)
        search_query = compose_search_query(query, bounded_history)
        yield "searching", None
        search_results = await self._search(search_query)
        yield "ingesting", None
        documents = await self._ingest(search_results)
        chunks = self._chunk_documents(documents)
        yield "retrieving", None
        scope_id = str(uuid4())
        await self._index(chunks, scope_id)
        retrieved_chunks = await self._retrieve(search_query, scope_id)
        prompt = self._build_prompt(query, retrieved_chunks, bounded_history)
        yield "generating", prompt

    async def _search(self, query: str):
        try:
            results = await self._search_service.search(query)
        except Exception as exc:
            raise RAGServiceError("RAG web search failed.") from exc
        if not results:
            raise RAGServiceError("RAG web search returned no results.")
        return results

    async def _ingest(self, search_results):
        try:
            documents = await self._ingestion_service.ingest(search_results)
        except Exception as exc:
            raise RAGServiceError("RAG web ingestion failed.") from exc
        if not documents:
            raise RAGServiceError("RAG web ingestion returned no documents.")
        return documents

    def _chunk_documents(self, documents):
        try:
            chunks = [
                chunk
                for document in documents
                for chunk in self._chunker.chunk(document)
            ]
        except Exception as exc:
            raise RAGServiceError("RAG document chunking failed.") from exc
        if not chunks:
            raise RAGServiceError("RAG document chunking returned no chunks.")
        return chunks

    async def _index(self, chunks, scope_id: str) -> None:
        try:
            await self._retrieval_service.index(chunks, scope_id=scope_id)
        except Exception as exc:
            raise RAGServiceError("RAG document indexing failed.") from exc

    async def _retrieve(self, query: str, scope_id: str):
        try:
            chunks = await self._retrieval_service.retrieve(
                query,
                scope_id=scope_id,
                top_k=self._retrieval_top_k,
            )
        except Exception as exc:
            raise RAGServiceError("RAG retrieval failed.") from exc
        if not chunks:
            raise RAGServiceError("RAG retrieval returned no context.")
        return chunks

    def _build_prompt(self, query: str, retrieved_chunks, history: list[ConversationTurn]):
        try:
            if history:
                return self._prompt_builder.build(query, retrieved_chunks, history)
            return self._prompt_builder.build(query, retrieved_chunks)
        except Exception as exc:
            raise RAGServiceError("RAG prompt building failed.") from exc

    async def _generate(self, prompt: str) -> str:
        try:
            return await self._llm_provider.generate(prompt)
        except Exception as exc:
            raise RAGServiceError("RAG answer generation failed.") from exc
from uuid import uuid4
