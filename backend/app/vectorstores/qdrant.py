from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import AsyncQdrantClient, models

from app.core.config import Settings
from app.rag.models import DocumentChunk
from app.vectorstores.models import ScoredDocumentChunk


class VectorStoreConfigurationError(ValueError):
    """Raised when vector store configuration is invalid."""


class VectorStoreError(Exception):
    """Raised when a vector store operation cannot be completed safely."""


class AsyncQdrantClientProtocol(Protocol):
    async def collection_exists(self, collection_name: str) -> bool: ...

    async def get_collection(self, collection_name: str) -> object: ...

    async def create_collection(
        self,
        *,
        collection_name: str,
        vectors_config: models.VectorParams,
    ) -> bool: ...

    async def create_payload_index(
        self, *, collection_name: str, field_name: str, field_schema: object
    ) -> object: ...

    async def upsert(
        self,
        *,
        collection_name: str,
        points: list[models.PointStruct],
    ) -> object: ...

    async def query_points(
        self,
        *,
        collection_name: str,
        query: list[float] | models.Document,
        limit: int,
        with_payload: bool,
        with_vectors: bool,
        query_filter: models.Filter,
    ) -> object: ...

    async def delete(self, *, collection_name: str, points_selector: object) -> object: ...


class QdrantVectorStore:
    def __init__(
        self,
        settings: Settings,
        dimensions: int,
        client: AsyncQdrantClientProtocol | None = None,
    ) -> None:
        if dimensions < 1:
            raise VectorStoreConfigurationError("Vector dimensions must be at least 1.")
        if not settings.qdrant_collection_name.strip():
            raise VectorStoreConfigurationError("QDRANT_COLLECTION_NAME must not be empty.")

        self._collection_name = settings.qdrant_collection_name
        self._dimensions = dimensions
        self._uses_cloud_inference = settings.qdrant_cloud_inference_enabled
        self._inference_model = settings.qdrant_inference_model
        self._client = client or self._create_client(settings)

    @staticmethod
    def _create_client(settings: Settings) -> AsyncQdrantClient:
        api_key = settings.qdrant_api_key
        kwargs: dict[str, object] = {"url": settings.qdrant_url}
        if api_key is not None and api_key.get_secret_value().strip():
            kwargs["api_key"] = api_key.get_secret_value()
        if settings.qdrant_cloud_inference_enabled:
            kwargs["cloud_inference"] = True
        return AsyncQdrantClient(**kwargs)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def uses_cloud_inference(self) -> bool:
        return self._uses_cloud_inference

    async def initialize_collection(self) -> None:
        try:
            collection_exists = await self._client.collection_exists(
                self._collection_name
            )
        except Exception as exc:
            raise VectorStoreError("Qdrant collection initialization failed.") from exc

        if not collection_exists:
            try:
                await self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=models.VectorParams(
                        size=self._dimensions,
                        distance=models.Distance.COSINE,
                    ),
                )
            except Exception as exc:
                raise VectorStoreError("Qdrant collection initialization failed.") from exc
        else:
            try:
                collection = await self._client.get_collection(self._collection_name)
                collection_dimensions = self._collection_dimensions(collection)
            except VectorStoreError:
                raise
            except Exception as exc:
                raise VectorStoreError("Qdrant collection initialization failed.") from exc

            if collection_dimensions != self._dimensions:
                raise VectorStoreConfigurationError(
                    "Qdrant collection vector dimension does not match expected dimension."
                )
        try:
            await self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name="retrieval_scope_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            raise VectorStoreError("Qdrant collection initialization failed.") from exc

    async def upsert(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        scope_id: str,
    ) -> None:
        if len(chunks) != len(vectors):
            raise VectorStoreError("Each document chunk requires one embedding vector.")
        if not chunks:
            return
        self._validate_scope_id(scope_id)
        for vector in vectors:
            self._validate_vector(vector)

        points = [
            models.PointStruct(
                id=self._point_id(chunk, scope_id),
                vector=vector,
                payload=self._payload(chunk, scope_id),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        try:
            await self._client.upsert(
                collection_name=self._collection_name,
                points=points,
            )
        except Exception as exc:
            raise VectorStoreError("Qdrant vector upsert failed.") from exc

    async def search(
        self,
        query_vector: list[float],
        limit: int,
        scope_id: str,
    ) -> list[ScoredDocumentChunk]:
        self._validate_vector(query_vector)
        if limit < 1:
            raise VectorStoreError("Search limit must be at least 1.")
        self._validate_scope_id(scope_id)

        try:
            response = await self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                limit=limit,
                with_payload=True,
                with_vectors=False,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="retrieval_scope_id",
                            match=models.MatchValue(value=scope_id),
                        )
                    ]
                ),
            )
        except Exception as exc:
            raise VectorStoreError("Qdrant similarity search failed.") from exc

        points = getattr(response, "points", None)
        if not isinstance(points, list):
            raise VectorStoreError("Qdrant similarity search response was invalid.")

        return [
            self._to_scored_chunk(point)
            for point in points
            if self._point_has_scope(point, scope_id)
        ]

    async def upsert_with_inference(self, chunks: list[DocumentChunk], scope_id: str) -> None:
        if not self._uses_cloud_inference:
            raise VectorStoreConfigurationError("Qdrant cloud inference is not enabled.")
        self._validate_scope_id(scope_id)
        points = [
            models.PointStruct(
                id=self._point_id(chunk, scope_id),
                vector=models.Document(text=chunk.content, model=self._inference_model),
                payload=self._payload(chunk, scope_id),
            )
            for chunk in chunks
        ]
        try:
            await self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            raise VectorStoreError("Qdrant vector upsert failed.") from exc

    async def search_with_inference(self, query: str, limit: int, scope_id: str) -> list[ScoredDocumentChunk]:
        if not self._uses_cloud_inference:
            raise VectorStoreConfigurationError("Qdrant cloud inference is not enabled.")
        self._validate_scope_id(scope_id)
        return await self._search(models.Document(text=query, model=self._inference_model), limit, scope_id)

    async def search_files(self, query_vector: list[float], limit: int, conversation_id: str, document_ids: list[str]) -> list[ScoredDocumentChunk]:
        self._validate_vector(query_vector)
        return await self._search_files(query_vector, limit, conversation_id, document_ids)

    async def search_files_with_inference(self, query: str, limit: int, conversation_id: str, document_ids: list[str]) -> list[ScoredDocumentChunk]:
        if not self._uses_cloud_inference:
            raise VectorStoreConfigurationError("Qdrant cloud inference is not enabled.")
        return await self._search_files(models.Document(text=query, model=self._inference_model), limit, conversation_id, document_ids)

    async def _search_files(self, query: list[float] | models.Document, limit: int, conversation_id: str, document_ids: list[str]) -> list[ScoredDocumentChunk]:
        if not conversation_id.strip() or not document_ids:
            raise VectorStoreError("File retrieval requires a conversation and selected documents.")
        query_filter = models.Filter(must=[models.FieldCondition(key="source_type", match=models.MatchValue(value="file")), models.FieldCondition(key="conversation_id", match=models.MatchValue(value=conversation_id)), models.FieldCondition(key="document_id", match=models.MatchAny(any=document_ids))])
        try:
            response = await self._client.query_points(collection_name=self._collection_name, query=query, limit=limit, with_payload=True, with_vectors=False, query_filter=query_filter)
        except Exception as exc:
            raise VectorStoreError("Qdrant file similarity search failed.") from exc
        points = getattr(response, "points", None)
        if not isinstance(points, list):
            raise VectorStoreError("Qdrant similarity search response was invalid.")
        return [self._to_scored_chunk(point) for point in points]

    async def _search(self, query: list[float] | models.Document, limit: int, scope_id: str) -> list[ScoredDocumentChunk]:
        try:
            response = await self._client.query_points(collection_name=self._collection_name, query=query, limit=limit, with_payload=True, with_vectors=False, query_filter=models.Filter(must=[models.FieldCondition(key="retrieval_scope_id", match=models.MatchValue(value=scope_id))]))
        except Exception as exc:
            raise VectorStoreError("Qdrant similarity search failed.") from exc
        points = getattr(response, "points", None)
        if not isinstance(points, list):
            raise VectorStoreError("Qdrant similarity search response was invalid.")
        return [self._to_scored_chunk(point) for point in points if self._point_has_scope(point, scope_id)]

    def _validate_vector(self, vector: list[float]) -> None:
        if (
            not isinstance(vector, list)
            or len(vector) != self._dimensions
            or any(
                not isinstance(value, (int, float)) or isinstance(value, bool)
                for value in vector
            )
        ):
            raise VectorStoreError("Vector dimension or values were invalid.")

    @staticmethod
    def _payload(chunk: DocumentChunk, scope_id: str) -> dict[str, object]:
        payload = {"content": chunk.content, "source_url": chunk.source_url, "final_url": chunk.final_url, "title": chunk.title, "chunk_index": chunk.index, "retrieval_scope_id": scope_id}
        if chunk.source_type == "file":
            payload.update({"source_type": "file", "conversation_id": chunk.conversation_id, "document_id": chunk.document_id, "filename": chunk.filename, "page_number": chunk.page_number})
        return payload

    async def delete_files(self, conversation_id: str, document_id: str | None = None) -> None:
        conditions = [models.FieldCondition(key="source_type", match=models.MatchValue(value="file")), models.FieldCondition(key="conversation_id", match=models.MatchValue(value=conversation_id))]
        if document_id:
            conditions.append(models.FieldCondition(key="document_id", match=models.MatchValue(value=document_id)))
        try:
            await self._client.delete(collection_name=self._collection_name, points_selector=models.FilterSelector(filter=models.Filter(must=conditions)))
        except Exception as exc:
            raise VectorStoreError("Qdrant file deletion failed.") from exc

    @staticmethod
    def _collection_dimensions(collection: object) -> int:
        vectors = getattr(
            getattr(getattr(collection, "config", None), "params", None),
            "vectors",
            None,
        )
        size = getattr(vectors, "size", None)
        if not isinstance(size, int):
            raise VectorStoreError("Qdrant collection configuration was invalid.")
        return size

    @staticmethod
    def _validate_scope_id(scope_id: str) -> None:
        if not isinstance(scope_id, str) or not scope_id.strip():
            raise VectorStoreError("Retrieval scope id must not be empty.")

    @staticmethod
    def _point_id(chunk: DocumentChunk, scope_id: str) -> str:
        identity = "|".join(
            [scope_id, chunk.source_url, chunk.final_url, str(chunk.index), chunk.content]
        )
        return str(uuid5(NAMESPACE_URL, identity))

    @staticmethod
    def _point_has_scope(point: object, scope_id: str) -> bool:
        payload = getattr(point, "payload", None)
        return isinstance(payload, dict) and payload.get("retrieval_scope_id") == scope_id

    @staticmethod
    def _to_scored_chunk(point: object) -> ScoredDocumentChunk:
        payload = getattr(point, "payload", None)
        score = getattr(point, "score", None)
        if not isinstance(payload, dict) or not isinstance(score, (int, float)):
            raise VectorStoreError("Qdrant similarity search response was invalid.")

        try:
            chunk = DocumentChunk(
                content=payload["content"],
                source_url=payload["source_url"],
                final_url=payload["final_url"],
                title=payload.get("title"),
                index=payload["chunk_index"],
                source_type=payload.get("source_type"), conversation_id=payload.get("conversation_id"), document_id=payload.get("document_id"), filename=payload.get("filename"), page_number=payload.get("page_number"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise VectorStoreError("Qdrant similarity search response was invalid.") from exc

        return ScoredDocumentChunk(chunk=chunk, score=float(score))
