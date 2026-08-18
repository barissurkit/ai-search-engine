import asyncio
from collections.abc import Sequence

import pytest

from app.retrieval.evaluation.evaluator import RetrievalEvaluator
from app.retrieval.evaluation.models import EvaluationCase, RetrievalObservation
from app.retrieval.experiments.provider import RankedRetriever
from app.retrieval.experiments.service import QueryRewriteRetrievalExperiment
from app.retrieval.rewriting.models import QueryRewriteResult
from app.retrieval.rewriting.provider import QueryRewriter


class FakeQueryRewriter:
    def __init__(self, rewrites: dict[str, QueryRewriteResult]) -> None:
        self.rewrites = rewrites
        self.queries: list[str] = []

    async def rewrite(self, query: str) -> QueryRewriteResult:
        self.queries.append(query)
        return self.rewrites[query]


class FakeRankedRetriever:
    def __init__(self, results: dict[str, Sequence[RetrievalObservation]]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    async def retrieve(self, query: str, top_k: int) -> Sequence[RetrievalObservation]:
        self.calls.append((query, top_k))
        return self.results.get(query, ())


def observation(source: str) -> RetrievalObservation:
    return RetrievalObservation(source_identifier=f"https://example.test/{source}")


def test_experiment_compares_baseline_and_rewritten_queries_across_offline_cases():
    cases = [
        EvaluationCase(id="improved", query="original improved", relevant_sources=[observation("a").source_identifier]),
        EvaluationCase(id="unchanged", query="original unchanged", relevant_sources=[observation("b").source_identifier]),
        EvaluationCase(id="regressed", query="original regressed", relevant_sources=[observation("c").source_identifier]),
        EvaluationCase(
            id="multi-source",
            query="original multi",
            relevant_sources=[observation("d").source_identifier, observation("e").source_identifier],
        ),
    ]
    rewriter = FakeQueryRewriter(
        {
            "original improved": QueryRewriteResult(original_query="original improved", rewritten_query="rewritten improved"),
            "original unchanged": QueryRewriteResult(original_query="original unchanged", rewritten_query="original unchanged"),
            "original regressed": QueryRewriteResult(original_query="original regressed", rewritten_query="rewritten regressed"),
            "original multi": QueryRewriteResult(original_query="original multi", rewritten_query="rewritten multi"),
        }
    )
    retriever = FakeRankedRetriever(
        {
            "original improved": [observation("x")],
            "rewritten improved": [observation("a")],
            "original unchanged": [observation("b")],
            "original regressed": [observation("c")],
            "rewritten regressed": [observation("x")],
            "original multi": [observation("d"), observation("d")],
            "rewritten multi": [observation("d"), observation("e")],
        }
    )

    report = asyncio.run(
        QueryRewriteRetrievalExperiment(rewriter, retriever, RetrievalEvaluator()).run(cases, k=2)
    )

    assert retriever.calls == [
        ("original improved", 2),
        ("rewritten improved", 2),
        ("original unchanged", 2),
        ("original unchanged", 2),
        ("original regressed", 2),
        ("rewritten regressed", 2),
        ("original multi", 2),
        ("rewritten multi", 2),
    ]
    assert [comparison.outcome for comparison in report.case_comparisons] == [
        "improved",
        "unchanged",
        "regressed",
        "improved",
    ]
    assert report.case_comparisons[3].baseline.recall_at_k == 0.5
    assert report.case_comparisons[3].rewritten.recall_at_k == 1.0
    assert report.summary.model_dump() == {
        "evaluated_case_count": 4,
        "baseline_mean_hit_rate_at_k": 0.75,
        "rewritten_mean_hit_rate_at_k": 0.75,
        "hit_rate_delta": 0.0,
        "baseline_mean_recall_at_k": 0.625,
        "rewritten_mean_recall_at_k": 0.75,
        "recall_delta": 0.125,
        "baseline_mean_reciprocal_rank": 0.75,
        "rewritten_mean_reciprocal_rank": 0.75,
        "reciprocal_rank_delta": 0.0,
        "improved_case_count": 2,
        "unchanged_case_count": 1,
        "regressed_case_count": 1,
    }


def test_fallback_rewrite_that_keeps_original_query_runs_a_safe_comparison():
    case = EvaluationCase(id="fallback", query="original", relevant_sources=[observation("a").source_identifier])
    rewriter = FakeQueryRewriter(
        {"original": QueryRewriteResult(original_query="original", rewritten_query="original")}
    )
    retriever = FakeRankedRetriever({"original": [observation("a")]})

    report = asyncio.run(
        QueryRewriteRetrievalExperiment(rewriter, retriever, RetrievalEvaluator()).run([case], k=1)
    )

    assert report.case_comparisons[0].rewrite_changed is False
    assert report.case_comparisons[0].outcome == "unchanged"
    assert retriever.calls == [("original", 1), ("original", 1)]


def test_conflicting_metrics_use_hit_rate_then_recall_then_mrr_priority():
    case = EvaluationCase(
        id="conflict",
        query="original",
        relevant_sources=[observation("a").source_identifier, observation("b").source_identifier],
    )
    rewriter = FakeQueryRewriter(
        {"original": QueryRewriteResult(original_query="original", rewritten_query="rewritten")}
    )
    retriever = FakeRankedRetriever(
        {
            "original": [observation("a"), observation("b")],
            "rewritten": [observation("a"), observation("x")],
        }
    )

    report = asyncio.run(
        QueryRewriteRetrievalExperiment(rewriter, retriever, RetrievalEvaluator()).run([case], k=2)
    )

    assert report.case_comparisons[0].outcome == "regressed"


def test_empty_suite_is_safe_and_invalid_k_is_rejected():
    rewriter = FakeQueryRewriter({})
    retriever = FakeRankedRetriever({})
    experiment = QueryRewriteRetrievalExperiment(rewriter, retriever, RetrievalEvaluator())

    report = asyncio.run(experiment.run([], k=1))

    assert report.case_comparisons == []
    assert report.summary.evaluated_case_count == 0
    assert report.summary.improved_case_count == 0
    with pytest.raises(ValueError, match="positive integer"):
        asyncio.run(experiment.run([], k=0))


def test_experiment_uses_only_provider_independent_contracts():
    rewriter = FakeQueryRewriter({})
    retriever = FakeRankedRetriever({})
    experiment = QueryRewriteRetrievalExperiment(rewriter, retriever, RetrievalEvaluator())

    assert isinstance(rewriter, QueryRewriter)
    assert isinstance(retriever, RankedRetriever)
    assert experiment is not None
