import asyncio
from types import SimpleNamespace

import pytest

import app.vectorstores.qdrant as qdrant_module
from app.core.config import Settings
from app.rag.models import DocumentChunk
from app.vectorstores.models import ScoredDocumentChunk
from app.vectorstores.provider import VectorStore
from app.vectorstores.qdrant import (
    QdrantVectorStore,
    VectorStoreConfigurationError,
    VectorStoreError,
)


class FakeQdrantClient:
    def __init__(
        self,
        *,
        exists: bool = False,
        collection: object | None = None,
        query_response: object | None = None,
    ) -> None:
        self.exists = exists
        self.collection = collection
        self.query_response = query_response or SimpleNamespace(points=[])
        self.create_calls: list[dict[str, object]] = []
        self.upsert_calls: list[dict[str, object]] = []
        self.query_calls: list[dict[str, object]] = []
        self.payload_index_calls: list[dict[str, object]] = []

    async def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    async def get_collection(self, collection_name: str) -> object:
        if self.collection is None:
            raise RuntimeError("collection was unavailable")
        return self.collection

    async def create_collection(self, **kwargs: object) -> bool:
        self.create_calls.append(kwargs)
        return True

    async def create_payload_index(self, **kwargs: object) -> None:
        self.payload_index_calls.append(kwargs)

    async def upsert(self, **kwargs: object) -> None:
        self.upsert_calls.append(kwargs)

    async def query_points(self, **kwargs: object) -> object:
        self.query_calls.append(kwargs)
        return self.query_response


def collection_with_dimensions(dimensions: int) -> object:
    return SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=dimensions)))
    )


def chunk() -> DocumentChunk:
    return DocumentChunk(
        content="A useful document chunk.",
        source_url="https://example.com/source",
        final_url="https://example.com/final",
        title="Example",
        index=2,
    )


def create_store(client: FakeQdrantClient, dimensions: int = 3) -> QdrantVectorStore:
    settings = Settings(
        _env_file=None,
        debug=False,
        qdrant_collection_name="test_chunks",
    )
    return QdrantVectorStore(settings, dimensions=dimensions, client=client)


def test_initialize_creates_cosine_collection_with_given_dimension():
    client = FakeQdrantClient()
    store = create_store(client)

    asyncio.run(store.initialize_collection())

    assert isinstance(store, VectorStore)
    assert store.dimensions == 3
    config = client.create_calls[0]["vectors_config"]
    assert config.size == 3
    assert config.distance.value == "Cosine"
    assert client.payload_index_calls == [{
        "collection_name": "test_chunks",
        "field_name": "retrieval_scope_id",
        "field_schema": qdrant_module.models.PayloadSchemaType.KEYWORD,
    }]


def test_client_composition_preserves_local_url_without_an_api_key(monkeypatch):
    calls: list[dict[str, object]] = []

    class CapturingClient:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(qdrant_module, "AsyncQdrantClient", CapturingClient)
    settings = Settings(_env_file=None, qdrant_url="http://localhost:6333")

    QdrantVectorStore(settings, dimensions=3)

    assert calls == [{"url": "http://localhost:6333"}]


def test_client_composition_passes_api_key_for_remote_qdrant(monkeypatch):
    calls: list[dict[str, object]] = []

    class CapturingClient:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(qdrant_module, "AsyncQdrantClient", CapturingClient)
    settings = Settings(
        _env_file=None,
        qdrant_url="https://qdrant.test",
        qdrant_api_key="qdrant-test-secret",
    )

    QdrantVectorStore(settings, dimensions=3)

    assert calls == [{"url": "https://qdrant.test", "api_key": "qdrant-test-secret"}]


def test_cloud_inference_composition_and_document_paths_preserve_text_and_scope(monkeypatch):
    calls: list[dict[str, object]] = []

    class CapturingClient(FakeQdrantClient):
        def __init__(self, **kwargs: object) -> None:
            super().__init__()
            calls.append(kwargs)

    monkeypatch.setattr(qdrant_module, "AsyncQdrantClient", CapturingClient)
    settings = Settings(_env_file=None, qdrant_url="https://qdrant.test", qdrant_api_key="key", qdrant_cloud_inference_enabled=True, qdrant_inference_model="intfloat/multilingual-e5-small", qdrant_inference_dimensions=384)
    store = QdrantVectorStore(settings, dimensions=settings.qdrant_inference_dimensions)
    client = store._client

    asyncio.run(store.upsert_with_inference([chunk()], "scope-one"))
    asyncio.run(store.search_with_inference("question text", 7, "scope-one"))

    assert calls == [{"url": "https://qdrant.test", "api_key": "key", "cloud_inference": True}]
    point = client.upsert_calls[0]["points"][0]
    assert point.vector.text == "A useful document chunk."
    assert point.vector.model == "intfloat/multilingual-e5-small"
    assert point.payload["retrieval_scope_id"] == "scope-one"
    query = client.query_calls[0]["query"]
    assert query.text == "question text"
    assert query.model == "intfloat/multilingual-e5-small"
    assert client.query_calls[0]["limit"] == 7


def test_initialize_keeps_an_existing_compatible_collection():
    client = FakeQdrantClient(exists=True, collection=collection_with_dimensions(3))

    asyncio.run(create_store(client).initialize_collection())

    assert client.create_calls == []


def test_initialize_rejects_an_existing_incompatible_collection():
    client = FakeQdrantClient(exists=True, collection=collection_with_dimensions(4))

    with pytest.raises(VectorStoreConfigurationError, match="does not match"):
        asyncio.run(create_store(client).initialize_collection())


def test_upsert_preserves_chunk_metadata_and_scope_in_payload_with_stable_id():
    client = FakeQdrantClient()
    store = create_store(client)

    asyncio.run(store.upsert([chunk()], [[0.1, 0.2, 0.3]], "scope-one"))
    asyncio.run(store.upsert([chunk()], [[0.1, 0.2, 0.3]], "scope-one"))

    first_point = client.upsert_calls[0]["points"][0]
    second_point = client.upsert_calls[1]["points"][0]
    assert first_point.id == second_point.id
    assert first_point.payload == {
        "content": "A useful document chunk.",
        "source_url": "https://example.com/source",
        "final_url": "https://example.com/final",
        "title": "Example",
        "chunk_index": 2,
        "retrieval_scope_id": "scope-one",
    }


def test_upsert_uses_different_point_ids_for_different_scopes():
    client = FakeQdrantClient()
    store = create_store(client)

    asyncio.run(store.upsert([chunk()], [[0.1, 0.2, 0.3]], "scope-one"))
    asyncio.run(store.upsert([chunk()], [[0.1, 0.2, 0.3]], "scope-two"))

    assert client.upsert_calls[0]["points"][0].id != client.upsert_calls[1]["points"][0].id


def test_upsert_rejects_vector_dimension_mismatch_before_client_call():
    client = FakeQdrantClient()

    with pytest.raises(VectorStoreError, match="dimension"):
        asyncio.run(create_store(client).upsert([chunk()], [[0.1, 0.2]], "scope-one"))

    assert client.upsert_calls == []


def test_search_passes_top_k_and_normalizes_scored_chunks():
    client = FakeQdrantClient(
        query_response=SimpleNamespace(
            points=[
                SimpleNamespace(
                    score=0.91,
                    payload={
                        "content": "Retrieved chunk",
                        "source_url": "https://example.com/source",
                        "final_url": "https://example.com/final",
                        "title": "Retrieved",
                        "chunk_index": 4,
                        "retrieval_scope_id": "scope-one",
                    },
                )
            ]
        )
    )

    results = asyncio.run(create_store(client).search([0.1, 0.2, 0.3], limit=7, scope_id="scope-one"))

    assert client.query_calls[0]["limit"] == 7
    condition = client.query_calls[0]["query_filter"].must[0]
    assert condition.key == "retrieval_scope_id"
    assert condition.match.value == "scope-one"
    assert results == [
        ScoredDocumentChunk(
            chunk=DocumentChunk(
                content="Retrieved chunk",
                source_url="https://example.com/source",
                final_url="https://example.com/final",
                title="Retrieved",
                index=4,
            ),
            score=0.91,
        )
    ]


def test_search_rejects_malformed_payload():
    client = FakeQdrantClient(
        query_response=SimpleNamespace(
            points=[SimpleNamespace(score=0.8, payload={"retrieval_scope_id": "scope-one"})]
        )
    )

    with pytest.raises(VectorStoreError, match="response was invalid"):
        asyncio.run(create_store(client).search([0.1, 0.2, 0.3], limit=1, scope_id="scope-one"))


def test_search_excludes_points_from_another_scope():
    client = FakeQdrantClient(
        query_response=SimpleNamespace(
            points=[
                SimpleNamespace(
                    score=0.9,
                    payload={
                        "content": "Other scope",
                        "source_url": "https://example.com/source",
                        "final_url": "https://example.com/final",
                        "title": "Other",
                        "chunk_index": 1,
                        "retrieval_scope_id": "scope-two",
                    },
                )
            ]
        )
    )

    results = asyncio.run(create_store(client).search([0.1, 0.2, 0.3], 1, "scope-one"))

    assert results == []


def test_client_error_becomes_safe_store_error():
    client = FakeQdrantClient()

    async def fail(collection_name: str) -> bool:
        raise RuntimeError("qdrant-secret connection failed")

    client.collection_exists = fail
    with pytest.raises(VectorStoreError, match="initialization failed") as exc_info:
        asyncio.run(create_store(client).initialize_collection())

    assert "qdrant-secret" not in str(exc_info.value)
