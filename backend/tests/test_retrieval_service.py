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
        cloud_inference: bool = False,
    ) -> None:
        self.dimensions = dimensions
        self.search_results = search_results if search_results is not None else []
        self.initialize_calls = 0
        self.upsert_calls: list[tuple[list[DocumentChunk], list[list[float]], str]] = []
        self.search_calls: list[tuple[list[float], int, str]] = []
        self.initialize_error: Exception | None = None
        self.upsert_error: Exception | None = None
        self.cloud_inference = cloud_inference
        self.cloud_upsert_calls: list[tuple[list[DocumentChunk], str]] = []
        self.cloud_search_calls: list[tuple[str, int, str]] = []

    @property
    def uses_cloud_inference(self) -> bool:
        return self.cloud_inference

    async def upsert_with_inference(self, chunks: list[DocumentChunk], scope_id: str) -> None:
        self.cloud_upsert_calls.append((chunks, scope_id))

    async def search_with_inference(self, query: str, limit: int, scope_id: str) -> list[ScoredDocumentChunk]:
        self.cloud_search_calls.append((query, limit, scope_id))
        if isinstance(self.search_results, Exception):
            raise self.search_results
        return self.search_results

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


def test_cloud_retrieval_uses_text_path_and_preserves_candidate_pool_and_diversification():
    first = ScoredDocumentChunk(chunk=chunks()[0], score=0.9)
    same_source = ScoredDocumentChunk(chunk=chunks()[0].model_copy(update={"index": 2}), score=0.8)
    second_source = ScoredDocumentChunk(
        chunk=chunks()[1].model_copy(update={"source_url": "https://example.com/other"}), score=0.7
    )
    store = FakeVectorStore(cloud_inference=True, search_results=[first, same_source, second_source])
    service = RetrievalService(None, store, candidate_multiplier=3, max_chunks_per_source=1)

    asyncio.run(service.index(chunks(), "scope-one"))
    results = asyncio.run(service.retrieve("query text", "scope-one", top_k=2))

    assert store.cloud_upsert_calls == [(chunks(), "scope-one")]
    assert store.cloud_search_calls == [("query text", 6, "scope-one")]
    assert len(results) == 2


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
    assert vector_store.search_calls == [([0.4, 0.5, 0.6], 21, "scope-one")]
    assert results == [result]


def test_retrieve_uses_default_top_k_and_initializes_once():
    embedding_provider = FakeEmbeddingProvider()
    vector_store = FakeVectorStore()
    service = RetrievalService(embedding_provider, vector_store, default_top_k=6)

    asyncio.run(service.retrieve("first query", "scope-one"))
    asyncio.run(service.retrieve("second query", "scope-two"))

    assert vector_store.search_calls == [
        ([0.1, 0.2, 0.3], 18, "scope-one"),
        ([0.1, 0.2, 0.3], 18, "scope-two"),
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


def test_retrieve_diversifies_candidate_pool_without_leaking_candidate_limit():
    source_a = DocumentChunk(
        content="A first",
        source_url="https://example.test/a",
        final_url="https://example.test/a",
        index=0,
    )
    source_a_second = source_a.model_copy(update={"content": "A second", "index": 1})
    source_b = source_a.model_copy(
        update={
            "content": "B first",
            "source_url": "https://example.test/b",
            "final_url": "https://example.test/b",
        }
    )
    source_c = source_a.model_copy(
        update={
            "content": "C first",
            "source_url": "https://example.test/c",
            "final_url": "https://example.test/c",
        }
    )
    candidates = [
        ScoredDocumentChunk(chunk=source_a, score=0.9),
        ScoredDocumentChunk(chunk=source_a_second, score=0.8),
        ScoredDocumentChunk(chunk=source_b, score=0.7),
        ScoredDocumentChunk(chunk=source_c, score=0.6),
    ]
    vector_store = FakeVectorStore(search_results=candidates)
    service = RetrievalService(
        FakeEmbeddingProvider(),
        vector_store,
        candidate_multiplier=3,
        max_chunks_per_source=1,
    )

    results = asyncio.run(service.retrieve("query", "request-scope", top_k=3))

    assert vector_store.search_calls == [([0.1, 0.2, 0.3], 9, "request-scope")]
    assert results == [candidates[0], candidates[2], candidates[3]]
    assert [result.score for result in results] == [0.9, 0.7, 0.6]


def test_retrieve_returns_short_list_when_candidate_pool_has_too_few_sources():
    source = chunks()[0]
    candidates = [
        ScoredDocumentChunk(chunk=source, score=0.9),
        ScoredDocumentChunk(chunk=source.model_copy(update={"index": 1}), score=0.8),
    ]
    service = RetrievalService(
        FakeEmbeddingProvider(),
        FakeVectorStore(search_results=candidates),
        candidate_multiplier=3,
        max_chunks_per_source=1,
    )

    results = asyncio.run(service.retrieve("query", "scope-one", top_k=3))

    assert results == [candidates[0]]


@pytest.mark.parametrize(
    ("candidate_multiplier", "max_chunks_per_source"),
    [(0, 1), (-1, 1), (True, 1), (1, 0), (1, -1), (1, True)],
)
def test_constructor_rejects_invalid_diversification_configuration(
    candidate_multiplier: int, max_chunks_per_source: int
):
    with pytest.raises(RetrievalServiceError, match="at least 1"):
        RetrievalService(
            FakeEmbeddingProvider(),
            FakeVectorStore(),
            candidate_multiplier=candidate_multiplier,
            max_chunks_per_source=max_chunks_per_source,
        )
