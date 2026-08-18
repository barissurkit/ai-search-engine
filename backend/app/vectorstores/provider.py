from typing import Protocol, runtime_checkable

from app.rag.models import DocumentChunk
from app.vectorstores.models import ScoredDocumentChunk


@runtime_checkable
class VectorStore(Protocol):
    @property
    def dimensions(self) -> int: ...

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
