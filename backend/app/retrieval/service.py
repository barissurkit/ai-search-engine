from app.embeddings.provider import EmbeddingProvider
from app.rag.models import DocumentChunk
from app.retrieval.diversification import SourceDiversifier
from app.vectorstores.models import ScoredDocumentChunk
from app.vectorstores.provider import VectorStore


class RetrievalServiceError(Exception):
    """Raised when semantic retrieval cannot be completed safely."""


class RetrievalService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None,
        vector_store: VectorStore,
        default_top_k: int = 5,
        candidate_multiplier: int = 3,
        max_chunks_per_source: int = 1,
    ) -> None:
        if embedding_provider is not None and embedding_provider.dimensions != vector_store.dimensions:
            raise RetrievalServiceError(
                "Embedding provider and vector store dimensions must match."
            )
        if default_top_k < 1:
            raise RetrievalServiceError("Default top_k must be at least 1.")
        if (
            isinstance(candidate_multiplier, bool)
            or not isinstance(candidate_multiplier, int)
            or candidate_multiplier < 1
        ):
            raise RetrievalServiceError("Candidate multiplier must be at least 1.")
        if (
            isinstance(max_chunks_per_source, bool)
            or not isinstance(max_chunks_per_source, int)
            or max_chunks_per_source < 1
        ):
            raise RetrievalServiceError("Max chunks per source must be at least 1.")

        if embedding_provider is None and not vector_store.uses_cloud_inference:
            raise RetrievalServiceError("An embedding provider is required without cloud inference.")
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._default_top_k = default_top_k
        self._candidate_multiplier = candidate_multiplier
        self._source_diversifier = SourceDiversifier(max_chunks_per_source)
        self._collection_initialized = False

    async def index(self, chunks: list[DocumentChunk], scope_id: str) -> None:
        if not chunks:
            return
        self._validate_scope_id(scope_id)

        if self._vector_store.uses_cloud_inference:
            await self._ensure_collection()
            await self._vector_store.upsert_with_inference(chunks, scope_id)
            return

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

        if self._vector_store.uses_cloud_inference:
            await self._ensure_collection()
            try:
                candidates = await self._vector_store.search_with_inference(query, limit * self._candidate_multiplier, scope_id)
            except Exception as exc:
                raise RetrievalServiceError("Semantic retrieval search failed.") from exc
            return self._source_diversifier.diversify(candidates, top_k=limit)

        try:
            query_vector = await self._embedding_provider.embed(query)
        except Exception as exc:
            raise RetrievalServiceError("Retrieval query embedding failed.") from exc

        self._validate_vector(query_vector)
        await self._ensure_collection()
        try:
            candidates = await self._vector_store.search(
                query_vector,
                limit * self._candidate_multiplier,
                scope_id,
            )
        except Exception as exc:
            raise RetrievalServiceError("Semantic retrieval search failed.") from exc
        return self._source_diversifier.diversify(candidates, top_k=limit)

    async def delete_files(self, conversation_id: str, document_id: str | None = None) -> None:
        await self._ensure_collection()
        try:
            await self._vector_store.delete_files(conversation_id, document_id)
        except Exception as exc:
            raise RetrievalServiceError("Document cleanup failed.") from exc

    async def delete_scope(self, scope_id: str) -> None:
        await self._ensure_collection()
        try:
            await self._vector_store.delete_scope(scope_id)
        except Exception as exc:
            raise RetrievalServiceError("Web retrieval cleanup failed.") from exc

    async def retrieve_file_chunks(self, query: str, conversation_id: str, document_ids: list[str], top_k: int | None = None) -> list[ScoredDocumentChunk]:
        if not query.strip() or not conversation_id.strip() or not document_ids:
            raise RetrievalServiceError("File retrieval requires a query, conversation, and selected documents.")
        limit = self._default_top_k if top_k is None else top_k
        await self._ensure_collection()
        try:
            if self._vector_store.uses_cloud_inference:
                candidates = await self._vector_store.search_files_with_inference(query, limit * self._candidate_multiplier, conversation_id, document_ids)
            else:
                vector = await self._embedding_provider.embed(query)
                self._validate_vector(vector)
                candidates = await self._vector_store.search_files(vector, limit * self._candidate_multiplier, conversation_id, document_ids)
        except Exception as exc:
            raise RetrievalServiceError("File retrieval search failed.") from exc
        return self._source_diversifier.diversify(candidates, top_k=limit)

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
