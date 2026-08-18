import asyncio
from types import SimpleNamespace

import pytest

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

    async def collection_exists(self, collection_name: str) -> bool:
        return self.exists

    async def get_collection(self, collection_name: str) -> object:
        if self.collection is None:
            raise RuntimeError("collection was unavailable")
        return self.collection

    async def create_collection(self, **kwargs: object) -> bool:
        self.create_calls.append(kwargs)
        return True

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


def test_initialize_keeps_an_existing_compatible_collection():
    client = FakeQdrantClient(exists=True, collection=collection_with_dimensions(3))

    asyncio.run(create_store(client).initialize_collection())

    assert client.create_calls == []


def test_initialize_rejects_an_existing_incompatible_collection():
    client = FakeQdrantClient(exists=True, collection=collection_with_dimensions(4))

    with pytest.raises(VectorStoreConfigurationError, match="does not match"):
        asyncio.run(create_store(client).initialize_collection())


def test_upsert_preserves_chunk_metadata_in_payload_with_stable_id():
    client = FakeQdrantClient()
    store = create_store(client)

    asyncio.run(store.upsert([chunk()], [[0.1, 0.2, 0.3]]))
    asyncio.run(store.upsert([chunk()], [[0.1, 0.2, 0.3]]))

    first_point = client.upsert_calls[0]["points"][0]
    second_point = client.upsert_calls[1]["points"][0]
    assert first_point.id == second_point.id
    assert first_point.payload == {
        "content": "A useful document chunk.",
        "source_url": "https://example.com/source",
        "final_url": "https://example.com/final",
        "title": "Example",
        "chunk_index": 2,
    }


def test_upsert_rejects_vector_dimension_mismatch_before_client_call():
    client = FakeQdrantClient()

    with pytest.raises(VectorStoreError, match="dimension"):
        asyncio.run(create_store(client).upsert([chunk()], [[0.1, 0.2]]))

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
                    },
                )
            ]
        )
    )

    results = asyncio.run(create_store(client).search([0.1, 0.2, 0.3], limit=7))

    assert client.query_calls[0]["limit"] == 7
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
        query_response=SimpleNamespace(points=[SimpleNamespace(score=0.8, payload={})])
    )

    with pytest.raises(VectorStoreError, match="response was invalid"):
        asyncio.run(create_store(client).search([0.1, 0.2, 0.3], limit=1))


def test_client_error_becomes_safe_store_error():
    client = FakeQdrantClient()

    async def fail(collection_name: str) -> bool:
        raise RuntimeError("qdrant-secret connection failed")

    client.collection_exists = fail
    with pytest.raises(VectorStoreError, match="initialization failed") as exc_info:
        asyncio.run(create_store(client).initialize_collection())

    assert "qdrant-secret" not in str(exc_info.value)
