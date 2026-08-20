import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from time import perf_counter
from typing import Literal
from uuid import uuid4

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
from app.rag.timing import PipelineTimings
from app.retrieval.service import RetrievalService
from app.search.models import ConversationTurn
from app.search.service import SearchService
from app.web.ingestion import WebIngestionService
from app.web.models import Document

logger = logging.getLogger(__name__)


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
        clock: Callable[[], float] = perf_counter,
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
        self._clock = clock

    async def answer(self, query: str, history: list[ConversationTurn] | None = None, source_mode: str = "web", conversation_id: str | None = None, document_ids: list[str] | None = None) -> RAGAnswer:
        timings = PipelineTimings(clock=self._clock)
        prompt: RAGPrompt | None = None
        status = "error"
        generation_started_at: float | None = None
        try:
            prompt = await self._prepare_prompt(query, history, source_mode, conversation_id, document_ids, timings)
            generation_started_at = timings.start_stage()
            generated_answer = await self._generate(prompt.prompt)
            timings.record("generation_ms", generation_started_at)
            generation_started_at = None
            status = "success"
            return RAGAnswer(
                query=query,
                answer=generated_answer,
                sources=prompt.sources,
            )
        finally:
            if generation_started_at is not None:
                timings.record("generation_ms", generation_started_at)
            scope_id = prompt.retrieval_scope_id if prompt is not None else None
            await self._cleanup_with_timing(scope_id, timings)
            self._log_pipeline_latency(source_mode, status, timings, scope_id)

    async def index_file(self, document_id: str, conversation_id: str, filename: str, pages: list[tuple[int | None, str]]) -> int:
        chunks = []
        for page_number, content in pages:
            document = Document(content=content, source_url=f"file://{document_id}", final_url=f"file://{document_id}", title=filename)
            chunks.extend(chunk.model_copy(update={"source_type": "file", "conversation_id": conversation_id, "document_id": document_id, "filename": filename, "page_number": page_number}) for chunk in self._chunker.chunk(document))
        await self._retrieval_service.index(chunks, scope_id=f"file:{conversation_id}:{document_id}")
        return len(chunks)

    async def delete_file(self, conversation_id: str, document_id: str | None = None) -> None:
        await self._retrieval_service.delete_files(conversation_id, document_id)

    @property
    def supports_streaming(self) -> bool:
        return isinstance(self._llm_provider, StreamingLLMProvider)

    async def stream_answer(self, query: str, history: list[ConversationTurn] | None = None, source_mode: str = "web", conversation_id: str | None = None, document_ids: list[str] | None = None) -> AsyncIterator[RAGStreamEvent]:
        """Run the normal RAG pipeline while exposing provider-independent events."""
        timings = PipelineTimings(clock=self._clock)
        prompt: RAGPrompt | None = None
        status = "aborted"
        generation_started_at: float | None = None
        try:
            async for stage, prompt in self._prepare_prompt_stages(query, history, source_mode, conversation_id, document_ids, timings):
                yield RAGStreamProgress(stage=stage)

            assert prompt is not None
            if not self.supports_streaming:
                raise RAGServiceError("Streaming answer generation is unavailable.")
            generation_started_at = timings.start_stage()
            async for text in self._llm_provider.stream(prompt.prompt):
                if text:
                    if not timings.has_stage("first_token_ms"):
                        timings.record_from_start("first_token_ms")
                    yield RAGStreamDelta(text=text)
            timings.record("generation_ms", generation_started_at)
            generation_started_at = None
            status = "success"
        except asyncio.CancelledError:
            status = "aborted"
            raise
        except GeneratorExit:
            status = "aborted"
            raise
        except Exception:  # noqa: BLE001 - provider implementations are intentionally opaque
            status = "error"
            yield RAGStreamError(message="RAG answer is unavailable.")
            return
        finally:
            if generation_started_at is not None:
                timings.record("generation_ms", generation_started_at)
            scope_id = prompt.retrieval_scope_id if prompt is not None else None
            await self._cleanup_with_timing(scope_id, timings)
            self._log_pipeline_latency(source_mode, status, timings, scope_id)

        yield RAGStreamSources(sources=prompt.sources)
        yield RAGStreamComplete()

    async def _prepare_prompt(self, query: str, history: list[ConversationTurn] | None = None, source_mode: str = "web", conversation_id: str | None = None, document_ids: list[str] | None = None, timings: PipelineTimings | None = None) -> RAGPrompt:
        prompt: RAGPrompt | None = None
        async for _, prompt in self._prepare_prompt_stages(query, history, source_mode, conversation_id, document_ids, timings):
            pass
        assert prompt is not None
        return prompt

    async def _prepare_prompt_stages(
        self, query: str, history: list[ConversationTurn] | None = None, source_mode: str = "web", conversation_id: str | None = None, document_ids: list[str] | None = None, timings: PipelineTimings | None = None
    ) -> AsyncIterator[tuple[Literal["searching", "ingesting", "retrieving", "generating"], RAGPrompt | None]]:
        if not isinstance(query, str) or not query.strip():
            raise RAGServiceError("RAG query must not be empty.")

        query_preparation_started_at = timings.start_stage() if timings else None
        bounded_history = bound_history(history)
        search_query = compose_search_query(query, bounded_history)
        if timings and query_preparation_started_at is not None:
            timings.record("query_preparation_ms", query_preparation_started_at)
        retrieved_chunks = []
        scope_id: str | None = None
        if source_mode in {"web", "hybrid"}:
            yield "searching", None
            web_search_started_at = timings.start_stage() if timings else None
            search_results = await self._search(search_query)
            if timings and web_search_started_at is not None:
                timings.record("web_search_ms", web_search_started_at)
            yield "ingesting", None
            web_pipeline_started_at = timings.start_stage() if timings else None
            chunks = self._chunk_documents(await self._ingest(search_results))
            yield "retrieving", None
            scope_id = str(uuid4()); await self._index(chunks, scope_id)
            retrieved_chunks.extend(await self._retrieve(search_query, scope_id))
            if timings and web_pipeline_started_at is not None:
                timings.record("web_retrieval_pipeline_ms", web_pipeline_started_at)
        if source_mode in {"files", "hybrid"}:
            if not conversation_id or not document_ids:
                raise RAGServiceError("File source modes require a conversation and documents.")
            yield "retrieving", None
            file_retrieval_started_at = timings.start_stage() if timings else None
            retrieved_chunks.extend(await self._retrieval_service.retrieve_file_chunks(search_query, conversation_id, document_ids, self._retrieval_top_k))
            if timings and file_retrieval_started_at is not None:
                timings.record("file_retrieval_ms", file_retrieval_started_at)
        if not retrieved_chunks:
            raise RAGServiceError("RAG retrieval returned no context.")
        prompt = self._build_prompt(query, retrieved_chunks, bounded_history)
        prompt.retrieval_scope_id = scope_id
        yield "generating", prompt

    async def _cleanup_scope(self, scope_id: str | None) -> None:
        if not scope_id:
            return
        try:
            await self._retrieval_service.delete_scope(scope_id)
        except Exception:  # noqa: BLE001 - cleanup must not mask the primary answer
            return

    async def _cleanup_with_timing(self, scope_id: str | None, timings: PipelineTimings) -> None:
        if not scope_id:
            return
        cleanup_started_at = timings.start_stage()
        await self._cleanup_scope(scope_id)
        timings.record("cleanup_ms", cleanup_started_at)

    def _log_pipeline_latency(self, source_mode: str, status: str, timings: PipelineTimings, scope_id: str | None) -> None:
        event: dict[str, str | float] = {
            "event": "rag_pipeline_latency",
            "source_mode": source_mode,
            "status": status,
            **timings.finish(),
        }
        if scope_id:
            event["retrieval_scope_id"] = scope_id
        try:
            logger.info("rag_pipeline_latency %s", event)
        except Exception:  # noqa: BLE001 - observability must not affect requests
            return

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
