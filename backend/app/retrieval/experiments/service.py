from collections.abc import Sequence

from app.retrieval.evaluation.evaluator import RetrievalEvaluator
from app.retrieval.evaluation.metrics import validate_k
from app.retrieval.evaluation.models import (
    EvaluationCase,
    EvaluationCaseResult,
    RetrievalSummary,
)
from app.retrieval.experiments.models import (
    QueryRewriteCaseComparison,
    QueryRewriteComparisonReport,
    QueryRewriteComparisonSummary,
)
from app.retrieval.experiments.provider import RankedRetriever
from app.retrieval.rewriting.provider import QueryRewriter


class QueryRewriteRetrievalExperiment:
    """Compare original and rewritten queries using only offline collaborators.

    Case outcomes use lexicographic metric priority: hit rate, then recall, then MRR.
    Therefore a higher-priority metric determines the outcome when metrics conflict.
    """

    def __init__(
        self,
        query_rewriter: QueryRewriter,
        ranked_retriever: RankedRetriever,
        evaluator: RetrievalEvaluator,
    ) -> None:
        self._query_rewriter = query_rewriter
        self._ranked_retriever = ranked_retriever
        self._evaluator = evaluator

    async def run(
        self, cases: Sequence[EvaluationCase], k: int
    ) -> QueryRewriteComparisonReport:
        validate_k(k)
        baseline_results = {}
        rewritten_results = {}
        rewritten_queries = {}
        rewrite_changed = {}

        for case in cases:
            baseline_results[case.id] = await self._ranked_retriever.retrieve(case.query, k)
            rewrite_result = await self._query_rewriter.rewrite(case.query)
            rewritten_queries[case.id] = rewrite_result.rewritten_query
            rewrite_changed[case.id] = rewrite_result.changed
            rewritten_results[case.id] = await self._ranked_retriever.retrieve(
                rewrite_result.rewritten_query, k
            )

        baseline_report = self._evaluator.evaluate(cases, baseline_results, k)
        rewritten_report = self._evaluator.evaluate(cases, rewritten_results, k)
        comparisons = [
            QueryRewriteCaseComparison(
                case_id=case.id,
                original_query=case.query,
                rewritten_query=rewritten_queries[case.id],
                rewrite_changed=rewrite_changed[case.id],
                baseline=baseline_result,
                rewritten=rewritten_result,
                outcome=_classify_outcome(baseline_result, rewritten_result),
            )
            for case, baseline_result, rewritten_result in zip(
                cases,
                baseline_report.case_results,
                rewritten_report.case_results,
                strict=True,
            )
        ]
        return QueryRewriteComparisonReport(
            k=k,
            case_comparisons=comparisons,
            summary=_summarize(comparisons, baseline_report.summary, rewritten_report.summary),
        )


def _classify_outcome(
    baseline: EvaluationCaseResult, rewritten: EvaluationCaseResult
) -> str:
    baseline_metrics = (baseline.hit_rate_at_k, baseline.recall_at_k, baseline.reciprocal_rank)
    rewritten_metrics = (
        rewritten.hit_rate_at_k,
        rewritten.recall_at_k,
        rewritten.reciprocal_rank,
    )
    if rewritten_metrics > baseline_metrics:
        return "improved"
    if rewritten_metrics < baseline_metrics:
        return "regressed"
    return "unchanged"


def _summarize(
    comparisons: Sequence[QueryRewriteCaseComparison],
    baseline: RetrievalSummary,
    rewritten: RetrievalSummary,
) -> QueryRewriteComparisonSummary:
    baseline_hit_rate = baseline.mean_hit_rate_at_k
    rewritten_hit_rate = rewritten.mean_hit_rate_at_k
    baseline_recall = baseline.mean_recall_at_k
    rewritten_recall = rewritten.mean_recall_at_k
    baseline_mrr = baseline.mean_reciprocal_rank
    rewritten_mrr = rewritten.mean_reciprocal_rank
    return QueryRewriteComparisonSummary(
        evaluated_case_count=len(comparisons),
        baseline_mean_hit_rate_at_k=baseline_hit_rate,
        rewritten_mean_hit_rate_at_k=rewritten_hit_rate,
        hit_rate_delta=rewritten_hit_rate - baseline_hit_rate,
        baseline_mean_recall_at_k=baseline_recall,
        rewritten_mean_recall_at_k=rewritten_recall,
        recall_delta=rewritten_recall - baseline_recall,
        baseline_mean_reciprocal_rank=baseline_mrr,
        rewritten_mean_reciprocal_rank=rewritten_mrr,
        reciprocal_rank_delta=rewritten_mrr - baseline_mrr,
        improved_case_count=sum(item.outcome == "improved" for item in comparisons),
        unchanged_case_count=sum(item.outcome == "unchanged" for item in comparisons),
        regressed_case_count=sum(item.outcome == "regressed" for item in comparisons),
    )
