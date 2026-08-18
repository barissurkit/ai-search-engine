from collections.abc import Sequence

from app.retrieval.evaluation.evaluator import RetrievalEvaluator
from app.retrieval.evaluation.models import RetrievalObservation
from app.retrieval.service import RetrievalService


class ScopedRetrievalServiceRetriever:
    """Adapt an isolated RetrievalService scope to the offline experiment contract."""

    def __init__(self, retrieval_service: RetrievalService, scope_id: str) -> None:
        self._retrieval_service = retrieval_service
        self._scope_id = scope_id

    async def retrieve(self, query: str, top_k: int) -> Sequence[RetrievalObservation]:
        results = await self._retrieval_service.retrieve(query, self._scope_id, top_k)
        return RetrievalEvaluator.normalize_scored_document_chunks(results)
