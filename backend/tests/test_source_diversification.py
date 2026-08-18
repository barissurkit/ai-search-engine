import pytest

from app.rag.models import DocumentChunk
from app.retrieval.benchmark.diversification import (
    SourceDiversificationCaseResult,
    SourceDiversificationReport,
    SourceDiversificationSummary,
    diversification_recommendation,
)
from app.retrieval.diversification import SourceDiversificationError, SourceDiversifier
from app.retrieval.evaluation.models import EvaluationCaseResult
from app.vectorstores.models import ScoredDocumentChunk


def result(source: str, index: int, score: float) -> ScoredDocumentChunk:
    return ScoredDocumentChunk(
        chunk=DocumentChunk(
            content=f"content {index}",
            source_url=f"https://example.test/{source}",
            final_url=f"https://example.test/{source}",
            index=index,
        ),
        score=score,
    )


def test_all_distinct_sources_keep_order_scores_and_top_k():
    ranked = [result("a", 0, 0.9), result("b", 1, 0.8), result("c", 2, 0.7)]

    diversified = SourceDiversifier(1).diversify(ranked, top_k=2)

    assert diversified == ranked[:2]
    assert [item.score for item in diversified] == [0.9, 0.8]


def test_duplicate_leaders_make_room_for_later_sources_deterministically():
    ranked = [
        result("a", 0, 0.9),
        result("a", 1, 0.8),
        result("b", 0, 0.7),
        result("c", 0, 0.6),
    ]

    diversified = SourceDiversifier(1).diversify(ranked, top_k=3)

    assert diversified == [ranked[0], ranked[2], ranked[3]]


def test_max_chunks_per_source_two_retains_two_ranked_chunks_from_one_source():
    ranked = [result("a", 0, 0.9), result("a", 1, 0.8), result("a", 2, 0.7), result("b", 0, 0.6)]

    diversified = SourceDiversifier(2).diversify(ranked, top_k=4)

    assert diversified == [ranked[0], ranked[1], ranked[3]]


def test_empty_and_short_inputs_are_safe():
    assert SourceDiversifier(1).diversify([], top_k=3) == []
    ranked = [result("a", 0, 0.9)]
    assert SourceDiversifier(1).diversify(ranked, top_k=3) == ranked


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_source_limit_is_rejected(limit: int):
    with pytest.raises(SourceDiversificationError, match="positive integer"):
        SourceDiversifier(limit)


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_invalid_top_k_is_rejected(top_k: int):
    with pytest.raises(SourceDiversificationError, match="positive integer"):
        SourceDiversifier(1).diversify([], top_k)


def test_missing_or_invalid_final_urls_are_not_grouped_together():
    first = result("a", 0, 0.9).model_copy(update={"chunk": result("a", 0, 0.9).chunk.model_copy(update={"final_url": ""})})
    second = result("b", 0, 0.8).model_copy(update={"chunk": result("b", 0, 0.8).chunk.model_copy(update={"final_url": " "})})

    assert SourceDiversifier(1).diversify([first, second], top_k=2) == [first, second]


def test_diversity_benefit_without_relevance_regression_recommends_integration():
    metrics = EvaluationCaseResult(
        case_id="case", hit_rate_at_k=1.0, recall_at_k=1.0, reciprocal_rank=1.0
    )
    report = SourceDiversificationReport(
        k=3,
        case_results=[
            SourceDiversificationCaseResult(
                case_id="case",
                baseline=metrics,
                diversified=metrics,
                baseline_unique_sources=2,
                diversified_unique_sources=3,
                raw_source_sequence=["source-a", "source-a", "source-b"],
                diversified_source_sequence=["source-a", "source-b", "source-c"],
                outcome="unchanged",
            )
        ],
        summary=SourceDiversificationSummary(
            evaluated_case_count=1,
            baseline_mean_hit_rate_at_k=1.0,
            diversified_mean_hit_rate_at_k=1.0,
            hit_rate_delta=0.0,
            baseline_mean_recall_at_k=1.0,
            diversified_mean_recall_at_k=1.0,
            recall_delta=0.0,
            baseline_mean_reciprocal_rank=1.0,
            diversified_mean_reciprocal_rank=1.0,
            reciprocal_rank_delta=0.0,
            baseline_mean_unique_sources_at_k=2.0,
            diversified_mean_unique_sources_at_k=3.0,
            unique_sources_delta=1.0,
            improved_case_count=0,
            unchanged_case_count=1,
            regressed_case_count=0,
        ),
    )

    assert diversification_recommendation(report) == "INTEGRATE"
