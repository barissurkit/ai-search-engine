from typing import Protocol, runtime_checkable

from app.rag.models import DocumentChunk
from app.vectorstores.models import ScoredDocumentChunk


@runtime_checkable
class VectorStore(Protocol):
    @property
    def dimensions(self) -> int: ...

    @property
    def uses_cloud_inference(self) -> bool: ...

    async def initialize_collection(self) -> None: ...

    async def upsert(
        self,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
        scope_id: str,
    ) -> None: ...

    async def search(
        self,
        query_vector: list[float],
        limit: int,
        scope_id: str,
    ) -> list[ScoredDocumentChunk]: ...

    async def upsert_with_inference(self, chunks: list[DocumentChunk], scope_id: str) -> None: ...

    async def search_with_inference(
        self, query: str, limit: int, scope_id: str
    ) -> list[ScoredDocumentChunk]: ...

    async def delete_files(self, conversation_id: str, document_id: str | None = None) -> None: ...
    async def delete_scope(self, scope_id: str) -> None: ...

    async def search_files(self, query_vector: list[float], limit: int, conversation_id: str, document_ids: list[str]) -> list[ScoredDocumentChunk]: ...

    async def search_files_with_inference(self, query: str, limit: int, conversation_id: str, document_ids: list[str]) -> list[ScoredDocumentChunk]: ...
