import asyncio

import pytest

from app.rag.models import CitationSource, DocumentChunk, RAGPrompt
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
        self.retrieve_calls: list[tuple[str, int]] = []
        self.index_error: Exception | None = None

    async def index(self, chunks: list[DocumentChunk]) -> None:
        self.events.append("index")
        self.indexed_chunks.append(chunks)
        if self.index_error is not None:
            raise self.index_error

    async def retrieve(self, query: str, top_k: int) -> list[ScoredDocumentChunk]:
        self.events.append("retrieve")
        self.retrieve_calls.append((query, top_k))
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
    assert retrieval.retrieve_calls == [("What happened?", 3)]
    assert prompt_builder.calls == [("What happened?", [scored_chunk()])]
    assert llm.prompts == ["Grounded prompt"]
    assert answer.query == "What happened?"
    assert answer.answer == "Generated answer [1]."
    assert answer.sources == prompt_builder.prompt.sources


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
