from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.retrieval.evaluation.models import RetrievalObservation


@runtime_checkable
class RankedRetriever(Protocol):
    """Retrieves provider-neutral ranked observations for offline experiments."""

    async def retrieve(self, query: str, top_k: int) -> Sequence[RetrievalObservation]: ...
