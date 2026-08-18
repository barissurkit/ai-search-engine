import asyncio

import pytest

from app.rag.models import DocumentChunk
from app.retrieval.service import RetrievalService, RetrievalServiceError
from app.vectorstores.models import ScoredDocumentChunk


class FakeEmbeddingProvider:
    def __init__(
        self,
        *,
        dimensions: int = 3,
        batch_vectors: list[list[float]] | Exception | None = None,
        query_vector: list[float] | Exception | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.batch_vectors = batch_vectors if batch_vectors is not None else []
        self.query_vector = query_vector if query_vector is not None else [0.1, 0.2, 0.3]
        self.batch_calls: list[list[str]] = []
        self.embed_calls: list[str] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls.append(texts)
        if isinstance(self.batch_vectors, Exception):
            raise self.batch_vectors
        return self.batch_vectors

    async def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        if isinstance(self.query_vector, Exception):
            raise self.query_vector
        return self.query_vector


class FakeVectorStore:
    def __init__(
        self,
        *,
        dimensions: int = 3,
        search_results: list[ScoredDocumentChunk] | Exception | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.search_results = search_results if search_results is not None else []
        self.initialize_calls = 0
        self.upsert_calls: list[tuple[list[DocumentChunk], list[list[float]], str]] = []
        self.search_calls: list[tuple[list[float], int, str]] = []
        self.initialize_error: Exception | None = None
        self.upsert_error: Exception | None = None

    async def initialize_collection(self) -> None:
        self.initialize_calls += 1
        if self.initialize_error is not None:
            raise self.initialize_error

    async def upsert(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        scope_id: str,
    ) -> None:
        self.upsert_calls.append((chunks, vectors, scope_id))
        if self.upsert_error is not None:
            raise self.upsert_error

    async def search(
        self,
        query_vector: list[float],
        limit: int,
        scope_id: str,
    ) -> list[ScoredDocumentChunk]:
        self.search_calls.append((query_vector, limit, scope_id))
        if isinstance(self.search_results, Exception):
            raise self.search_results
        return self.search_results


def chunks() -> list[DocumentChunk]:
    return [
        DocumentChunk(
            content="First chunk",
            source_url="https://example.com/first",
            final_url="https://example.com/first",
            title="First",
            index=0,
        ),
        DocumentChunk(
            content="Second chunk",
            source_url="https://example.com/second",
            final_url="https://example.com/second",
            title="Second",
            index=1,
        ),
    ]


def test_index_embeds_chunk_content_once_and_preserves_vector_pairing():
    embedding_provider = FakeEmbeddingProvider(
        batch_vectors=[[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]]
    )
    vector_store = FakeVectorStore()
    service = RetrievalService(embedding_provider, vector_store)

    chunk_list = chunks()
    asyncio.run(service.index(chunk_list, scope_id="scope-one"))

    assert embedding_provider.batch_calls == [["First chunk", "Second chunk"]]
    assert vector_store.initialize_calls == 1
    assert vector_store.upsert_calls == [
        (chunk_list, [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0]], "scope-one")
    ]


def test_index_with_no_chunks_does_not_call_provider_or_store():
    embedding_provider = FakeEmbeddingProvider()
    vector_store = FakeVectorStore()

    asyncio.run(RetrievalService(embedding_provider, vector_store).index([], "scope-one"))

    assert embedding_provider.batch_calls == []
    assert vector_store.initialize_calls == 0
    assert vector_store.upsert_calls == []


def test_index_rejects_mismatched_embedding_count():
    embedding_provider = FakeEmbeddingProvider(batch_vectors=[[1.0, 1.0, 1.0]])

    with pytest.raises(RetrievalServiceError, match="count did not match"):
        asyncio.run(RetrievalService(embedding_provider, FakeVectorStore()).index(chunks(), "scope-one"))


def test_retrieve_embeds_query_searches_and_preserves_scored_result():
    result = ScoredDocumentChunk(chunk=chunks()[0], score=0.87)
    embedding_provider = FakeEmbeddingProvider(query_vector=[0.4, 0.5, 0.6])
    vector_store = FakeVectorStore(search_results=[result])
    service = RetrievalService(embedding_provider, vector_store, default_top_k=4)

    results = asyncio.run(service.retrieve("user query", "scope-one", top_k=7))

    assert embedding_provider.embed_calls == ["user query"]
    assert vector_store.initialize_calls == 1
    assert vector_store.search_calls == [([0.4, 0.5, 0.6], 7, "scope-one")]
    assert results == [result]


def test_retrieve_uses_default_top_k_and_initializes_once():
    embedding_provider = FakeEmbeddingProvider()
    vector_store = FakeVectorStore()
    service = RetrievalService(embedding_provider, vector_store, default_top_k=6)

    asyncio.run(service.retrieve("first query", "scope-one"))
    asyncio.run(service.retrieve("second query", "scope-two"))

    assert vector_store.search_calls == [
        ([0.1, 0.2, 0.3], 6, "scope-one"),
        ([0.1, 0.2, 0.3], 6, "scope-two"),
    ]
    assert vector_store.initialize_calls == 1


@pytest.mark.parametrize("query", ["", "  ", "\n\t"])
def test_retrieve_rejects_whitespace_query(query: str):
    embedding_provider = FakeEmbeddingProvider()
    vector_store = FakeVectorStore()

    with pytest.raises(RetrievalServiceError, match="must not be empty"):
        asyncio.run(RetrievalService(embedding_provider, vector_store).retrieve(query, "scope-one"))

    assert embedding_provider.embed_calls == []
    assert vector_store.search_calls == []


def test_retrieve_rejects_invalid_top_k():
    with pytest.raises(RetrievalServiceError, match="top_k"):
        asyncio.run(
            RetrievalService(FakeEmbeddingProvider(), FakeVectorStore()).retrieve(
                "query", "scope-one", 0
            )
        )


def test_provider_and_store_errors_become_safe_service_errors():
    with pytest.raises(RetrievalServiceError, match="embedding failed") as embedding_error:
        asyncio.run(
            RetrievalService(
                FakeEmbeddingProvider(query_vector=RuntimeError("provider secret")),
                FakeVectorStore(),
            ).retrieve("query", "scope-one")
        )
    assert "provider secret" not in str(embedding_error.value)

    with pytest.raises(RetrievalServiceError, match="search failed") as store_error:
        asyncio.run(
            RetrievalService(
                FakeEmbeddingProvider(),
                FakeVectorStore(search_results=RuntimeError("store secret")),
            ).retrieve("query", "scope-one")
        )
    assert "store secret" not in str(store_error.value)


def test_constructor_rejects_dimension_mismatch():
    with pytest.raises(RetrievalServiceError, match="dimensions must match"):
        RetrievalService(FakeEmbeddingProvider(dimensions=3), FakeVectorStore(dimensions=4))
