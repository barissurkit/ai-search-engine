from app.embeddings.provider import EmbeddingProvider
from app.rag.models import DocumentChunk
from app.vectorstores.models import ScoredDocumentChunk
from app.vectorstores.provider import VectorStore


class RetrievalServiceError(Exception):
    """Raised when semantic retrieval cannot be completed safely."""


class RetrievalService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        default_top_k: int = 5,
    ) -> None:
        if embedding_provider.dimensions != vector_store.dimensions:
            raise RetrievalServiceError(
                "Embedding provider and vector store dimensions must match."
            )
        if default_top_k < 1:
            raise RetrievalServiceError("Default top_k must be at least 1.")

        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._default_top_k = default_top_k
        self._collection_initialized = False

    async def index(self, chunks: list[DocumentChunk], scope_id: str) -> None:
        if not chunks:
            return
        self._validate_scope_id(scope_id)

        try:
            vectors = await self._embedding_provider.embed_batch(
                [chunk.content for chunk in chunks]
            )
        except Exception as exc:
            raise RetrievalServiceError("Document chunk embedding failed.") from exc

        if len(vectors) != len(chunks):
            raise RetrievalServiceError(
                "Document chunk embedding count did not match chunk count."
            )
        for vector in vectors:
            self._validate_vector(vector)

        await self._ensure_collection()
        try:
            await self._vector_store.upsert(chunks, vectors, scope_id)
        except Exception as exc:
            raise RetrievalServiceError("Document chunk indexing failed.") from exc

    async def retrieve(
        self,
        query: str,
        scope_id: str,
        top_k: int | None = None,
    ) -> list[ScoredDocumentChunk]:
        if not query.strip():
            raise RetrievalServiceError("Retrieval query must not be empty.")
        self._validate_scope_id(scope_id)

        limit = self._default_top_k if top_k is None else top_k
        if limit < 1:
            raise RetrievalServiceError("top_k must be at least 1.")

        try:
            query_vector = await self._embedding_provider.embed(query)
        except Exception as exc:
            raise RetrievalServiceError("Retrieval query embedding failed.") from exc

        self._validate_vector(query_vector)
        await self._ensure_collection()
        try:
            return await self._vector_store.search(query_vector, limit, scope_id)
        except Exception as exc:
            raise RetrievalServiceError("Semantic retrieval search failed.") from exc

    async def _ensure_collection(self) -> None:
        if self._collection_initialized:
            return

        try:
            await self._vector_store.initialize_collection()
        except Exception as exc:
            raise RetrievalServiceError("Vector store initialization failed.") from exc
        self._collection_initialized = True

    def _validate_vector(self, vector: list[float]) -> None:
        if (
            not isinstance(vector, list)
            or len(vector) != self._embedding_provider.dimensions
            or any(
                not isinstance(value, (int, float)) or isinstance(value, bool)
                for value in vector
            )
        ):
            raise RetrievalServiceError("Embedding vector was invalid.")

    @staticmethod
    def _validate_scope_id(scope_id: str) -> None:
        if not isinstance(scope_id, str) or not scope_id.strip():
            raise RetrievalServiceError("Retrieval scope id must not be empty.")
