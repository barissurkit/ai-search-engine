import pytest

from app.rag.models import DocumentChunk
from app.retrieval.evaluation.evaluator import RetrievalEvaluator
from app.retrieval.evaluation.metrics import hit_rate_at_k, recall_at_k, reciprocal_rank
from app.retrieval.evaluation.models import EvaluationCase, RetrievalObservation
from app.vectorstores.models import ScoredDocumentChunk


def test_hit_rate_at_one_and_later_rank_hit():
    retrieved = ["https://example.test/other", "https://example.test/relevant"]

    assert hit_rate_at_k(retrieved, ["https://example.test/relevant"], 1) == 0.0
    assert hit_rate_at_k(retrieved, ["https://example.test/relevant"], 2) == 1.0


def test_recall_at_k_deduplicates_chunks_from_the_same_source():
    retrieved = ["https://example.test/a", "https://example.test/a", "https://example.test/b"]
    relevant = ["https://example.test/a", "https://example.test/b"]

    assert recall_at_k(retrieved, relevant, 2) == 0.5
    assert recall_at_k(retrieved, relevant, 3) == 1.0


def test_mrr_handles_rank_one_later_rank_and_no_hit():
    relevant = ["https://example.test/relevant"]

    assert reciprocal_rank([relevant[0]], relevant) == 1.0
    assert reciprocal_rank(["https://example.test/other", relevant[0]], relevant) == 0.5
    assert reciprocal_rank(["https://example.test/other"], relevant) == 0.0


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_metrics_reject_non_positive_or_non_integer_k(k: int):
    with pytest.raises(ValueError, match="positive integer"):
        hit_rate_at_k([], [], k)


def test_evaluator_produces_case_metrics_and_aggregate_averages():
    cases = [
        EvaluationCase(
            id="rank-one", query="first", relevant_sources=["https://example.test/a"]
        ),
        EvaluationCase(
            id="later-rank", query="second", relevant_sources=["https://example.test/b"]
        ),
        EvaluationCase(
            id="no-hit", query="third", relevant_sources=["https://example.test/c"]
        ),
        EvaluationCase(
            id="multiple-relevant",
            query="fourth",
            relevant_sources=["https://example.test/d", "https://example.test/e"],
        ),
    ]
    observations = {
        "rank-one": [RetrievalObservation(source_identifier="https://example.test/a")],
        "later-rank": [
            RetrievalObservation(source_identifier="https://example.test/x"),
            RetrievalObservation(source_identifier="https://example.test/b"),
        ],
        "no-hit": [RetrievalObservation(source_identifier="https://example.test/x")],
        "multiple-relevant": [
            RetrievalObservation(source_identifier="https://example.test/d"),
            RetrievalObservation(source_identifier="https://example.test/d"),
            RetrievalObservation(source_identifier="https://example.test/e"),
        ],
    }

    report = RetrievalEvaluator().evaluate(cases, observations, k=2)

    assert [result.hit_rate_at_k for result in report.case_results] == [1.0, 1.0, 0.0, 1.0]
    assert [result.recall_at_k for result in report.case_results] == [1.0, 1.0, 0.0, 0.5]
    assert [result.reciprocal_rank for result in report.case_results] == [1.0, 0.5, 0.0, 1.0]
    assert report.summary.evaluated_case_count == 4
    assert report.summary.mean_hit_rate_at_k == 0.75
    assert report.summary.mean_recall_at_k == 0.625
    assert report.summary.mean_reciprocal_rank == 0.625


def test_evaluator_treats_missing_or_empty_results_as_no_results():
    case = EvaluationCase(
        id="empty", query="query", relevant_sources=["https://example.test/relevant"]
    )

    report = RetrievalEvaluator().evaluate([case], {}, k=1)

    assert report.case_results[0].hit_rate_at_k == 0.0
    assert report.case_results[0].recall_at_k == 0.0
    assert report.case_results[0].reciprocal_rank == 0.0


def test_evaluator_handles_an_empty_suite_without_division_by_zero():
    report = RetrievalEvaluator().evaluate([], {}, k=1)

    assert report.case_results == []
    assert report.summary.model_dump() == {
        "evaluated_case_count": 0,
        "mean_hit_rate_at_k": 0.0,
        "mean_recall_at_k": 0.0,
        "mean_reciprocal_rank": 0.0,
    }


def test_evaluator_rejects_invalid_k_even_for_an_empty_suite():
    with pytest.raises(ValueError, match="positive integer"):
        RetrievalEvaluator().evaluate([], {}, k=0)


def test_existing_scored_document_chunks_normalize_without_provider_types():
    scored = ScoredDocumentChunk(
        chunk=DocumentChunk(
            content="content",
            source_url="https://source.example.test/original",
            final_url="https://source.example.test/final",
            index=0,
        ),
        score=0.9,
    )

    observations = RetrievalEvaluator.normalize_scored_document_chunks([scored])

    assert observations == [
        RetrievalObservation(source_identifier="https://source.example.test/final")
    ]
