from app.rag.evaluation.benchmark import (
    CITATION_BENCHMARK_QUERIES,
    CitationBenchmarkCaseResult,
    summarize_citation_benchmark,
)
from app.rag.models import CitationSource, RAGAnswer


def successful_case(
    query: str = "query",
    answer: str = "Answer [1].",
    source_count: int = 2,
) -> CitationBenchmarkCaseResult:
    sources = [
        CitationSource(citation_number=index, url=f"https://example.test/{index}")
        for index in range(1, source_count + 1)
    ]
    return CitationBenchmarkCaseResult.from_rag_answer(
        RAGAnswer(query=query, answer=answer, sources=sources)
    )


def test_benchmark_query_set_has_exactly_the_required_eight_queries():
    assert CITATION_BENCHMARK_QUERIES == (
        "What is Retrieval-Augmented Generation and why is it useful?",
        "How does vector similarity search work?",
        "Compare Docker containers and virtual machines.",
        "How does HTTPS protect data in transit?",
        "What are the main benefits and limitations of solar energy?",
        "Explain the CAP theorem and its practical implications.",
        "What causes inflation and how do central banks respond to it?",
        "Compare PostgreSQL and MongoDB for modern application development.",
    )


def test_all_valid_cases_need_no_change():
    summary = summarize_citation_benchmark([successful_case() for _ in range(8)])

    assert summary.decision == "NO CHANGE NEEDED"
    assert summary.aggregate_valid_citation_rate == 1.0


def test_one_citation_free_successful_case_needs_prompt_reliability_improvement():
    summary = summarize_citation_benchmark(
        [successful_case(), successful_case(answer="Answer without a marker.")]
    )

    assert summary.decision == "PROMPT RELIABILITY IMPROVEMENT NEEDED"
    assert summary.cases_without_citation == 1


def test_invalid_citation_requires_validation():
    summary = summarize_citation_benchmark([successful_case(answer="Invalid [3].")])

    assert summary.decision == "CITATION VALIDATION NEEDED"
    assert summary.total_invalid_citation_markers == 1


def test_invalid_citation_has_priority_over_missing_citation():
    summary = summarize_citation_benchmark(
        [successful_case(answer="No citation."), successful_case(answer="Invalid [3].")]
    )

    assert summary.decision == "CITATION VALIDATION NEEDED"


def test_aggregate_marker_rate_and_average_coverage_are_calculated_from_successes():
    summary = summarize_citation_benchmark(
        [
            successful_case(answer="[1] [2]", source_count=2),
            successful_case(answer="[1] [3]", source_count=2),
        ]
    )

    assert summary.aggregate_valid_citation_rate == 0.75
    assert summary.average_unique_valid_sources_cited == 1.5
    assert summary.average_source_coverage == 0.75


def test_failed_cases_do_not_count_as_citation_free_successes_and_block_the_run():
    summary = summarize_citation_benchmark(
        [successful_case(), CitationBenchmarkCaseResult.failed("failed", "RAG pipeline failed.")]
    )

    assert summary.successful_cases == 1
    assert summary.failed_cases == 1
    assert summary.cases_without_citation == 0
    assert summary.decision == "BLOCKED"
