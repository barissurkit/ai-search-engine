from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

from pydantic import BaseModel

from app.retrieval.diversification import SourceDiversifier
from app.retrieval.evaluation.evaluator import RetrievalEvaluator
from app.retrieval.evaluation.metrics import validate_k
from app.retrieval.evaluation.models import (
    EvaluationCase,
    EvaluationCaseResult,
    RetrievalSummary,
)
from app.vectorstores.models import ScoredDocumentChunk


class ScoredRankedRetriever(Protocol):
    async def retrieve(self, query: str, top_k: int) -> Sequence[ScoredDocumentChunk]: ...


class SourceDiversificationCaseResult(BaseModel):
    case_id: str
    baseline: EvaluationCaseResult
    diversified: EvaluationCaseResult
    baseline_unique_sources: int
    diversified_unique_sources: int
    outcome: Literal["improved", "unchanged", "regressed"]


class SourceDiversificationSummary(BaseModel):
    evaluated_case_count: int
    baseline_mean_hit_rate_at_k: float
    diversified_mean_hit_rate_at_k: float
    hit_rate_delta: float
    baseline_mean_recall_at_k: float
    diversified_mean_recall_at_k: float
    recall_delta: float
    baseline_mean_reciprocal_rank: float
    diversified_mean_reciprocal_rank: float
    reciprocal_rank_delta: float
    baseline_mean_unique_sources_at_k: float
    diversified_mean_unique_sources_at_k: float
    unique_sources_delta: float
    improved_case_count: int
    unchanged_case_count: int
    regressed_case_count: int


class SourceDiversificationReport(BaseModel):
    k: int
    case_results: list[SourceDiversificationCaseResult]
    summary: SourceDiversificationSummary


class SourceDiversificationBenchmark:
    """Compare raw and diversified views of the same ranked retrieval candidates."""

    def __init__(
        self,
        retriever: ScoredRankedRetriever,
        diversifier: SourceDiversifier,
        evaluator: RetrievalEvaluator,
    ) -> None:
        self._retriever = retriever
        self._diversifier = diversifier
        self._evaluator = evaluator

    async def run(self, cases: Sequence[EvaluationCase], k: int) -> SourceDiversificationReport:
        validate_k(k)
        raw_results: Mapping[str, Sequence[ScoredDocumentChunk]] = {
            case.id: await self._retriever.retrieve(case.query, k) for case in cases
        }
        diversified_results = {
            case_id: self._diversifier.diversify(results, k)
            for case_id, results in raw_results.items()
        }
        baseline_report = self._evaluate(cases, raw_results, k)
        diversified_report = self._evaluate(cases, diversified_results, k)
        case_results = [
            SourceDiversificationCaseResult(
                case_id=case.id,
                baseline=baseline,
                diversified=diversified,
                baseline_unique_sources=_unique_sources(raw_results[case.id], k),
                diversified_unique_sources=_unique_sources(diversified_results[case.id], k),
                outcome=_outcome(baseline, diversified),
            )
            for case, baseline, diversified in zip(
                cases,
                baseline_report.case_results,
                diversified_report.case_results,
                strict=True,
            )
        ]
        return SourceDiversificationReport(
            k=k,
            case_results=case_results,
            summary=_summary(case_results, baseline_report.summary, diversified_report.summary),
        )

    def _evaluate(
        self,
        cases: Sequence[EvaluationCase],
        results: Mapping[str, Sequence[ScoredDocumentChunk]],
        k: int,
    ) -> object:
        observations = {
            case_id: RetrievalEvaluator.normalize_scored_document_chunks(scored_results)
            for case_id, scored_results in results.items()
        }
        return self._evaluator.evaluate(cases, observations, k)


def diversification_recommendation(report: SourceDiversificationReport) -> str:
    """Recommend integration only for an observed, non-regressing diversity benefit."""
    summary = report.summary
    if (
        summary.hit_rate_delta >= 0.0
        and summary.recall_delta >= 0.0
        and summary.reciprocal_rank_delta >= 0.0
        and summary.unique_sources_delta > 0.0
        and summary.improved_case_count > summary.regressed_case_count
    ):
        return "INTEGRATE"
    return "DO NOT INTEGRATE YET"


def format_diversification_report(report: SourceDiversificationReport) -> str:
    lines = ["Local source diversification benchmark"]
    for result in report.case_results:
        lines.append(
            f"{result.case_id} | "
            f"baseline=H:{result.baseline.hit_rate_at_k:.3f},R:{result.baseline.recall_at_k:.3f},MRR:{result.baseline.reciprocal_rank:.3f},U:{result.baseline_unique_sources} | "
            f"diversified=H:{result.diversified.hit_rate_at_k:.3f},R:{result.diversified.recall_at_k:.3f},MRR:{result.diversified.reciprocal_rank:.3f},U:{result.diversified_unique_sources} | "
            f"classification={result.outcome}"
        )
    summary = report.summary
    lines.extend(
        [
            f"Aggregate: cases={summary.evaluated_case_count}, improved={summary.improved_case_count}, unchanged={summary.unchanged_case_count}, regressed={summary.regressed_case_count}",
            f"Hit Rate: {summary.baseline_mean_hit_rate_at_k:.3f} -> {summary.diversified_mean_hit_rate_at_k:.3f}",
            f"Recall: {summary.baseline_mean_recall_at_k:.3f} -> {summary.diversified_mean_recall_at_k:.3f}",
            f"MRR: {summary.baseline_mean_reciprocal_rank:.3f} -> {summary.diversified_mean_reciprocal_rank:.3f}",
            f"Unique sources: {summary.baseline_mean_unique_sources_at_k:.3f} -> {summary.diversified_mean_unique_sources_at_k:.3f}",
            f"Decision: {diversification_recommendation(report)}",
        ]
    )
    return "\n".join(lines)


def _unique_sources(results: Sequence[ScoredDocumentChunk], k: int) -> int:
    return len(
        {
            result.chunk.final_url
            for result in results[:k]
            if isinstance(result.chunk.final_url, str) and result.chunk.final_url.strip()
        }
    )


def _outcome(baseline: EvaluationCaseResult, diversified: EvaluationCaseResult) -> str:
    baseline_metrics = (baseline.hit_rate_at_k, baseline.recall_at_k, baseline.reciprocal_rank)
    diversified_metrics = (
        diversified.hit_rate_at_k,
        diversified.recall_at_k,
        diversified.reciprocal_rank,
    )
    if diversified_metrics > baseline_metrics:
        return "improved"
    if diversified_metrics < baseline_metrics:
        return "regressed"
    return "unchanged"


def _summary(
    case_results: Sequence[SourceDiversificationCaseResult],
    baseline: RetrievalSummary,
    diversified: RetrievalSummary,
) -> SourceDiversificationSummary:
    baseline_unique_sources = sum(item.baseline_unique_sources for item in case_results) / len(case_results) if case_results else 0.0
    diversified_unique_sources = sum(item.diversified_unique_sources for item in case_results) / len(case_results) if case_results else 0.0
    return SourceDiversificationSummary(
        evaluated_case_count=len(case_results),
        baseline_mean_hit_rate_at_k=baseline.mean_hit_rate_at_k,
        diversified_mean_hit_rate_at_k=diversified.mean_hit_rate_at_k,
        hit_rate_delta=diversified.mean_hit_rate_at_k - baseline.mean_hit_rate_at_k,
        baseline_mean_recall_at_k=baseline.mean_recall_at_k,
        diversified_mean_recall_at_k=diversified.mean_recall_at_k,
        recall_delta=diversified.mean_recall_at_k - baseline.mean_recall_at_k,
        baseline_mean_reciprocal_rank=baseline.mean_reciprocal_rank,
        diversified_mean_reciprocal_rank=diversified.mean_reciprocal_rank,
        reciprocal_rank_delta=diversified.mean_reciprocal_rank - baseline.mean_reciprocal_rank,
        baseline_mean_unique_sources_at_k=baseline_unique_sources,
        diversified_mean_unique_sources_at_k=diversified_unique_sources,
        unique_sources_delta=diversified_unique_sources - baseline_unique_sources,
        improved_case_count=sum(item.outcome == "improved" for item in case_results),
        unchanged_case_count=sum(item.outcome == "unchanged" for item in case_results),
        regressed_case_count=sum(item.outcome == "regressed" for item in case_results),
    )
