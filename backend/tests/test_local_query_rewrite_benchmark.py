import asyncio
import runpy
from pathlib import Path

from app.rag.models import DocumentChunk
from app.retrieval.benchmark.fixtures import (
    BENCHMARK_CANDIDATE_POOL_K,
    BENCHMARK_CASES,
    BENCHMARK_CHUNKS,
)
from app.retrieval.benchmark.reporting import recommendation
from app.retrieval.benchmark.retriever import ScopedRetrievalServiceRetriever
from app.retrieval.evaluation.models import EvaluationCaseResult
from app.retrieval.experiments.models import (
    QueryRewriteCaseComparison,
    QueryRewriteComparisonReport,
    QueryRewriteComparisonSummary,
)
from app.vectorstores.models import ScoredDocumentChunk


class FakeRetrievalService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    async def retrieve(self, query: str, scope_id: str, top_k: int) -> list[ScoredDocumentChunk]:
        self.calls.append((query, scope_id, top_k))
        return [
            ScoredDocumentChunk(
                chunk=DocumentChunk(
                    content="benchmark result",
                    source_url="https://benchmark.local/source",
                    final_url="https://benchmark.local/final",
                    index=0,
                ),
                score=0.9,
            )
        ]


def test_benchmark_fixtures_are_stable_and_have_relevant_urls():
    assert len(BENCHMARK_CHUNKS) == 18
    assert BENCHMARK_CANDIDATE_POOL_K > 3
    assert 8 <= len(BENCHMARK_CASES) <= 12
    assert len({case.id for case in BENCHMARK_CASES}) == len(BENCHMARK_CASES)
    assert all(case.relevant_sources for case in BENCHMARK_CASES)
    assert all(source.startswith("https://benchmark.local/") for case in BENCHMARK_CASES for source in case.relevant_sources)
    chunk_count_by_source = {}
    for chunk in BENCHMARK_CHUNKS:
        chunk_count_by_source[chunk.final_url] = chunk_count_by_source.get(chunk.final_url, 0) + 1
    assert all(count == 2 for count in chunk_count_by_source.values())


def test_scoped_retriever_preserves_scope_and_top_k_and_normalizes_results():
    service = FakeRetrievalService()

    observations = asyncio.run(
        ScopedRetrievalServiceRetriever(service, "benchmark-scope").retrieve("query", 3)
    )

    assert service.calls == [("query", "benchmark-scope", 3)]
    assert observations[0].source_identifier == "https://benchmark.local/final"


def test_recommendation_is_conservative_when_metrics_regress_or_are_unchanged():
    baseline = EvaluationCaseResult(
        case_id="case", hit_rate_at_k=1.0, recall_at_k=1.0, reciprocal_rank=1.0
    )
    comparison = QueryRewriteCaseComparison(
        case_id="case",
        original_query="original",
        rewritten_query="rewritten",
        rewrite_changed=True,
        baseline=baseline,
        rewritten=baseline,
        outcome="unchanged",
    )
    unchanged_report = QueryRewriteComparisonReport(
        k=3,
        case_comparisons=[comparison],
        summary=QueryRewriteComparisonSummary(
            evaluated_case_count=1,
            baseline_mean_hit_rate_at_k=1.0,
            rewritten_mean_hit_rate_at_k=1.0,
            hit_rate_delta=0.0,
            baseline_mean_recall_at_k=1.0,
            rewritten_mean_recall_at_k=1.0,
            recall_delta=0.0,
            baseline_mean_reciprocal_rank=1.0,
            rewritten_mean_reciprocal_rank=1.0,
            reciprocal_rank_delta=0.0,
            improved_case_count=0,
            unchanged_case_count=1,
            regressed_case_count=0,
        ),
    )

    assert recommendation(unchanged_report) == "DO NOT INTEGRATE YET"


def test_benchmark_script_is_importable_when_run_directly():
    script_path = Path(__file__).parents[1] / "scripts" / "run_local_query_rewrite_benchmark.py"

    namespace = runpy.run_path(script_path)

    assert callable(namespace["main"])
