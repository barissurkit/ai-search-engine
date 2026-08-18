from collections.abc import Mapping, Sequence

from app.retrieval.evaluation.metrics import (
    hit_rate_at_k,
    recall_at_k,
    reciprocal_rank,
    validate_k,
)
from app.retrieval.evaluation.models import (
    EvaluationCase,
    EvaluationCaseResult,
    RetrievalEvaluationReport,
    RetrievalObservation,
    RetrievalSummary,
)
from app.vectorstores.models import ScoredDocumentChunk


class RetrievalEvaluator:
    """Evaluate ranked retrieval observations without invoking retrieval providers."""

    def evaluate(
        self,
        cases: Sequence[EvaluationCase],
        results_by_case: Mapping[str, Sequence[RetrievalObservation]],
        k: int,
    ) -> RetrievalEvaluationReport:
        validate_k(k)
        case_results = [
            self._evaluate_case(case, results_by_case.get(case.id, ()), k) for case in cases
        ]
        return RetrievalEvaluationReport(
            k=k,
            case_results=case_results,
            summary=_summarize(case_results),
        )

    @staticmethod
    def normalize_scored_document_chunks(
        results: Sequence[ScoredDocumentChunk],
    ) -> list[RetrievalObservation]:
        """Normalize existing retrieval results using their canonical final URL."""
        return [
            RetrievalObservation(source_identifier=result.chunk.final_url) for result in results
        ]

    @staticmethod
    def _evaluate_case(
        case: EvaluationCase,
        observations: Sequence[RetrievalObservation],
        k: int,
    ) -> EvaluationCaseResult:
        retrieved_sources = [observation.source_identifier for observation in observations]
        return EvaluationCaseResult(
            case_id=case.id,
            hit_rate_at_k=hit_rate_at_k(retrieved_sources, case.relevant_sources, k),
            recall_at_k=recall_at_k(retrieved_sources, case.relevant_sources, k),
            reciprocal_rank=reciprocal_rank(retrieved_sources, case.relevant_sources),
        )


def _summarize(case_results: Sequence[EvaluationCaseResult]) -> RetrievalSummary:
    count = len(case_results)
    if count == 0:
        return RetrievalSummary(
            evaluated_case_count=0,
            mean_hit_rate_at_k=0.0,
            mean_recall_at_k=0.0,
            mean_reciprocal_rank=0.0,
        )
    return RetrievalSummary(
        evaluated_case_count=count,
        mean_hit_rate_at_k=sum(result.hit_rate_at_k for result in case_results) / count,
        mean_recall_at_k=sum(result.recall_at_k for result in case_results) / count,
        mean_reciprocal_rank=sum(result.reciprocal_rank for result in case_results) / count,
    )
