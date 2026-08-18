import asyncio

import pytest

from app.rag.models import (
    CitationSource,
    DocumentChunk,
    RAGPrompt,
    RAGStreamComplete,
    RAGStreamDelta,
    RAGStreamError,
    RAGStreamSources,
)
from app.rag.prompt import RAGPromptBuilder
from app.rag.service import RAGService, RAGServiceError
from app.search.models import SearchResult
from app.vectorstores.models import ScoredDocumentChunk
from app.web.models import Document


def search_result() -> SearchResult:
    return SearchResult(
        title="Search result",
        url="https://example.com/source",
        snippet="Search snippet",
    )


def document() -> Document:
    return Document(
        content="Document content",
        source_url="https://example.com/source",
        final_url="https://example.com/source",
        title="Document title",
    )


def chunk(content: str = "Chunk content") -> DocumentChunk:
    return DocumentChunk(
        content=content,
        source_url="https://example.com/source",
        final_url="https://example.com/source",
        title="Document title",
        index=0,
    )


def scored_chunk() -> ScoredDocumentChunk:
    return ScoredDocumentChunk(chunk=chunk(), score=0.9)


class FakeSearchService:
    def __init__(self, events: list[str], results: list[SearchResult] | Exception) -> None:
        self.events = events
        self.results = results
        self.queries: list[str] = []

    async def search(self, query: str) -> list[SearchResult]:
        self.events.append("search")
        self.queries.append(query)
        if isinstance(self.results, Exception):
            raise self.results
        return self.results


class FakeIngestionService:
    def __init__(self, events: list[str], documents: list[Document] | Exception) -> None:
        self.events = events
        self.documents = documents
        self.results: list[list[SearchResult]] = []

    async def ingest(self, results: list[SearchResult]) -> list[Document]:
        self.events.append("ingest")
        self.results.append(results)
        if isinstance(self.documents, Exception):
            raise self.documents
        return self.documents


class FakeChunker:
    def __init__(self, events: list[str], chunks: list[DocumentChunk] | Exception) -> None:
        self.events = events
        self.chunks = chunks
        self.documents: list[Document] = []

    def chunk(self, value: Document) -> list[DocumentChunk]:
        self.events.append("chunk")
        self.documents.append(value)
        if isinstance(self.chunks, Exception):
            raise self.chunks
        return self.chunks


class FakeRetrievalService:
    def __init__(self, events: list[str], retrieved: list[ScoredDocumentChunk] | Exception) -> None:
        self.events = events
        self.retrieved = retrieved
        self.indexed_chunks: list[list[DocumentChunk]] = []
        self.index_scope_ids: list[str] = []
        self.retrieve_calls: list[tuple[str, str, int]] = []
        self.index_error: Exception | None = None

    async def index(self, chunks: list[DocumentChunk], scope_id: str) -> None:
        self.events.append("index")
        self.indexed_chunks.append(chunks)
        self.index_scope_ids.append(scope_id)
        if self.index_error is not None:
            raise self.index_error

    async def retrieve(
        self, query: str, scope_id: str, top_k: int
    ) -> list[ScoredDocumentChunk]:
        self.events.append("retrieve")
        self.retrieve_calls.append((query, scope_id, top_k))
        if isinstance(self.retrieved, Exception):
            raise self.retrieved
        return self.retrieved


class FakePromptBuilder:
    def __init__(self, events: list[str], prompt: RAGPrompt | Exception) -> None:
        self.events = events
        self.prompt = prompt
        self.calls: list[tuple[str, list[ScoredDocumentChunk]]] = []

    def build(self, query: str, chunks: list[ScoredDocumentChunk]) -> RAGPrompt:
        self.events.append("prompt")
        self.calls.append((query, chunks))
        if isinstance(self.prompt, Exception):
            raise self.prompt
        return self.prompt


class FakeLLMProvider:
    def __init__(self, events: list[str], answer: str | Exception) -> None:
        self.events = events
        self.answer = answer
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.events.append("generate")
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    async def stream(self, prompt: str):
        self.events.append("stream")
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        yield "Generated "
        yield "answer [1]."


def create_service(
    *,
    search_results: list[SearchResult] | Exception | None = None,
    documents: list[Document] | Exception | None = None,
    chunks: list[DocumentChunk] | Exception | None = None,
    retrieved: list[ScoredDocumentChunk] | Exception | None = None,
    generated_answer: str | Exception = "Generated answer [1].",
):
    events: list[str] = []
    search = FakeSearchService(events, search_results if search_results is not None else [search_result()])
    ingestion = FakeIngestionService(events, documents if documents is not None else [document()])
    chunker = FakeChunker(events, chunks if chunks is not None else [chunk()])
    retrieval = FakeRetrievalService(events, retrieved if retrieved is not None else [scored_chunk()])
    prompt = RAGPrompt(
        prompt="Grounded prompt",
        sources=[CitationSource(citation_number=1, url="https://example.com/source")],
    )
    prompt_builder = FakePromptBuilder(events, prompt)
    llm = FakeLLMProvider(events, generated_answer)
    service = RAGService(search, ingestion, chunker, retrieval, prompt_builder, llm, retrieval_top_k=3)
    return service, events, search, ingestion, chunker, retrieval, prompt_builder, llm


def test_answer_runs_the_pipeline_in_order_and_preserves_citation_sources():
    service, events, search, ingestion, chunker, retrieval, prompt_builder, llm = create_service()

    answer = asyncio.run(service.answer("What happened?"))

    assert events == ["search", "ingest", "chunk", "index", "retrieve", "prompt", "generate"]
    assert search.queries == ["What happened?"]
    assert ingestion.results == [[search_result()]]
    assert chunker.documents == [document()]
    assert retrieval.indexed_chunks == [[chunk()]]
    assert len(retrieval.index_scope_ids) == 1
    assert retrieval.retrieve_calls == [("What happened?", retrieval.index_scope_ids[0], 3)]
    assert prompt_builder.calls == [("What happened?", [scored_chunk()])]
    assert llm.prompts == ["Grounded prompt"]
    assert answer.query == "What happened?"
    assert answer.answer == "Generated answer [1]."
    assert answer.sources == prompt_builder.prompt.sources


def test_answer_uses_a_distinct_scope_for_each_request():
    service, _, *_, retrieval, _, _ = create_service()

    asyncio.run(service.answer("First question"))
    asyncio.run(service.answer("Second question"))

    assert len(set(retrieval.index_scope_ids)) == 2
    assert [call[1] for call in retrieval.retrieve_calls] == retrieval.index_scope_ids


@pytest.mark.parametrize("query", ["", "  ", "\n\t"])
def test_answer_rejects_whitespace_query(query: str):
    service, events, *_ = create_service()

    with pytest.raises(RAGServiceError, match="query must not be empty"):
        asyncio.run(service.answer(query))

    assert events == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"search_results": []}, "search returned no results"),
        ({"documents": []}, "ingestion returned no documents"),
        ({"chunks": []}, "chunking returned no chunks"),
        ({"retrieved": []}, "retrieval returned no context"),
        ({"generated_answer": RuntimeError("provider secret")}, "answer generation failed"),
    ],
)
def test_answer_converts_empty_pipeline_results_and_failures_to_safe_errors(kwargs, message):
    service, _, *_ = create_service(**kwargs)

    with pytest.raises(RAGServiceError, match=message) as exc_info:
        asyncio.run(service.answer("Question"))

    assert "provider secret" not in str(exc_info.value)


def test_answer_converts_retrieval_index_failure_to_a_safe_error():
    service, _, *_, retrieval, _, _ = create_service()
    retrieval.index_error = RuntimeError("vector secret")

    with pytest.raises(RAGServiceError, match="indexing failed") as exc_info:
        asyncio.run(service.answer("Question"))

    assert "vector secret" not in str(exc_info.value)


def test_stream_answer_emits_ordered_progress_deltas_sources_and_complete():
    service, events, search, _, _, retrieval, prompt_builder, llm = create_service()

    async def collect():
        return [event async for event in service.stream_answer("What happened?")]

    stream_events = asyncio.run(collect())

    assert [(event.type, getattr(event, "stage", None)) for event in stream_events] == [
        ("progress", "searching"),
        ("progress", "ingesting"),
        ("progress", "retrieving"),
        ("progress", "generating"),
        ("delta", None),
        ("delta", None),
        ("sources", None),
        ("complete", None),
    ]
    assert [event.text for event in stream_events if isinstance(event, RAGStreamDelta)] == [
        "Generated ",
        "answer [1].",
    ]
    assert isinstance(stream_events[-2], RAGStreamSources)
    assert stream_events[-2].sources == prompt_builder.prompt.sources
    assert isinstance(stream_events[-1], RAGStreamComplete)
    assert events == ["search", "ingest", "chunk", "index", "retrieve", "prompt", "stream"]
    assert search.queries == ["What happened?"]
    assert retrieval.retrieve_calls[0][0] == "What happened?"
    assert llm.prompts == ["Grounded prompt"]


def test_stream_answer_emits_safe_error_without_complete_on_pipeline_or_provider_failure():
    service, _, *_ = create_service(generated_answer=RuntimeError("provider secret"))

    async def collect():
        return [event async for event in service.stream_answer("Question")]

    stream_events = asyncio.run(collect())

    assert isinstance(stream_events[-1], RAGStreamError)
    assert stream_events[-1].message == "RAG answer is unavailable."
    assert not any(isinstance(event, RAGStreamComplete) for event in stream_events)


def test_stream_answer_forwards_the_citation_aware_prompt_and_source_mapping():
    events: list[str] = []
    search = FakeSearchService(events, [search_result()])
    ingestion = FakeIngestionService(events, [document()])
    chunker = FakeChunker(events, [chunk()])
    retrieval = FakeRetrievalService(events, [scored_chunk()])
    llm = FakeLLMProvider(events, "Generated answer [1].")
    service = RAGService(
        search,
        ingestion,
        chunker,
        retrieval,
        RAGPromptBuilder(),
        llm,
        retrieval_top_k=3,
    )

    async def collect():
        return [event async for event in service.stream_answer("What happened?")]

    stream_events = asyncio.run(collect())

    assert "For factual claims, cite supporting sources with [1], [2], and so on." in llm.prompts[0]
    sources_event = next(event for event in stream_events if isinstance(event, RAGStreamSources))
    assert sources_event.sources == [
        CitationSource(
            citation_number=1,
            url="https://example.com/source",
            title="Document title",
        )
    ]
