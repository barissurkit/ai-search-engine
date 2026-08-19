from collections.abc import AsyncIterator, Sequence
from typing import Literal, Protocol

from pydantic import BaseModel

from app.rag.evaluation.evaluator import audit_rag_answer
from app.rag.models import (
    RAGAnswer,
    RAGStreamComplete,
    RAGStreamDelta,
    RAGStreamError,
    RAGStreamEvent,
    RAGStreamSources,
)

CITATION_BENCHMARK_QUERIES = (
    "What is Retrieval-Augmented Generation and why is it useful?",
    "How does vector similarity search work?",
    "Compare Docker containers and virtual machines.",
    "How does HTTPS protect data in transit?",
    "What are the main benefits and limitations of solar energy?",
    "Explain the CAP theorem and its practical implications.",
    "What causes inflation and how do central banks respond to it?",
    "Compare PostgreSQL and MongoDB for modern application development.",
)

CitationBenchmarkDecision = Literal[
    "NO CHANGE NEEDED",
    "PROMPT RELIABILITY IMPROVEMENT NEEDED",
    "CITATION VALIDATION NEEDED",
    "BLOCKED",
]


class StreamingRAGService(Protocol):
    def stream_answer(self, query: str) -> AsyncIterator[RAGStreamEvent]: ...


class CitationBenchmarkCaseResult(BaseModel):
    """One read-only citation audit result, or a safely represented pipeline failure."""

    query: str
    succeeded: bool
    failure_reason: str | None = None
    answer_length: int | None = None
    available_source_count: int | None = None
    total_citation_markers: int | None = None
    valid_citation_markers: int | None = None
    invalid_citation_markers: int | None = None
    valid_citation_rate: float | None = None
    unique_valid_sources_cited: int | None = None
    source_coverage: float | None = None
    has_any_citation: bool | None = None
    has_any_invalid_citation: bool | None = None

    @classmethod
    def from_rag_answer(cls, answer: RAGAnswer) -> "CitationBenchmarkCaseResult":
        audit = audit_rag_answer(answer)
        return cls(
            query=answer.query,
            succeeded=True,
            answer_length=len(answer.answer),
            available_source_count=audit.available_source_count,
            total_citation_markers=audit.total_marker_count,
            valid_citation_markers=audit.valid_marker_count,
            invalid_citation_markers=audit.invalid_marker_count,
            valid_citation_rate=audit.valid_citation_rate,
            unique_valid_sources_cited=audit.unique_valid_source_count,
            source_coverage=audit.source_coverage,
            has_any_citation=audit.has_any_citation,
            has_any_invalid_citation=audit.has_any_invalid_citation,
        )

    @classmethod
    def failed(cls, query: str, reason: str) -> "CitationBenchmarkCaseResult":
        return cls(query=query, succeeded=False, failure_reason=reason)


class CitationBenchmarkSummary(BaseModel):
    """Small-sample citation syntax baseline, not a factual-correctness evaluation."""

    total_cases: int
    successful_cases: int
    failed_cases: int
    cases_with_any_citation: int
    cases_without_citation: int
    cases_with_invalid_citation: int
    total_citation_markers: int
    total_valid_citation_markers: int
    total_invalid_citation_markers: int
    aggregate_valid_citation_rate: float
    average_unique_valid_sources_cited: float
    average_source_coverage: float
    decision: CitationBenchmarkDecision


class CitationBenchmarkReport(BaseModel):
    case_results: list[CitationBenchmarkCaseResult]
    summary: CitationBenchmarkSummary


class CitationBenchmarkRunner:
    """Run the normal streaming RAG path and audit its completed answers offline."""

    async def run(
        self, rag_service: StreamingRAGService, queries: Sequence[str] = CITATION_BENCHMARK_QUERIES
    ) -> CitationBenchmarkReport:
        case_results = [await self._run_case(rag_service, query) for query in queries]
        return CitationBenchmarkReport(
            case_results=case_results,
            summary=summarize_citation_benchmark(case_results),
        )

    async def _run_case(
        self, rag_service: StreamingRAGService, query: str
    ) -> CitationBenchmarkCaseResult:
        answer_parts: list[str] = []
        sources = None
        completed = False
        try:
            async for event in rag_service.stream_answer(query):
                if isinstance(event, RAGStreamDelta):
                    answer_parts.append(event.text)
                elif isinstance(event, RAGStreamSources):
                    sources = event.sources
                elif isinstance(event, RAGStreamError):
                    return CitationBenchmarkCaseResult.failed(query, event.message)
                elif isinstance(event, RAGStreamComplete):
                    completed = True
        except Exception:  # noqa: BLE001 - provider failures must remain opaque
            return CitationBenchmarkCaseResult.failed(query, "RAG pipeline failed.")

        if not completed or sources is None:
            return CitationBenchmarkCaseResult.failed(query, "RAG stream did not complete.")
        return CitationBenchmarkCaseResult.from_rag_answer(
            RAGAnswer(query=query, answer="".join(answer_parts), sources=sources)
        )


def summarize_citation_benchmark(
    case_results: Sequence[CitationBenchmarkCaseResult],
) -> CitationBenchmarkSummary:
    """Aggregate only successful cases; infrastructure failures make the run blocked."""
    successful_cases = [result for result in case_results if result.succeeded]
    total_markers = sum(result.total_citation_markers or 0 for result in successful_cases)
    valid_markers = sum(result.valid_citation_markers or 0 for result in successful_cases)
    invalid_markers = sum(result.invalid_citation_markers or 0 for result in successful_cases)
    cases_with_citations = sum(bool(result.has_any_citation) for result in successful_cases)
    cases_with_invalid = sum(bool(result.has_any_invalid_citation) for result in successful_cases)
    successful_count = len(successful_cases)

    return CitationBenchmarkSummary(
        total_cases=len(case_results),
        successful_cases=successful_count,
        failed_cases=len(case_results) - successful_count,
        cases_with_any_citation=cases_with_citations,
        cases_without_citation=successful_count - cases_with_citations,
        cases_with_invalid_citation=cases_with_invalid,
        total_citation_markers=total_markers,
        total_valid_citation_markers=valid_markers,
        total_invalid_citation_markers=invalid_markers,
        aggregate_valid_citation_rate=(valid_markers / total_markers) if total_markers else 0.0,
        average_unique_valid_sources_cited=(
            sum(result.unique_valid_sources_cited or 0 for result in successful_cases)
            / successful_count
            if successful_count
            else 0.0
        ),
        average_source_coverage=(
            sum(result.source_coverage or 0.0 for result in successful_cases) / successful_count
            if successful_count
            else 0.0
        ),
        decision=_classify(successful_cases, invalid_markers, len(case_results)),
    )


def _classify(
    successful_cases: Sequence[CitationBenchmarkCaseResult],
    invalid_markers: int,
    total_cases: int,
) -> CitationBenchmarkDecision:
    if len(successful_cases) != total_cases:
        return "BLOCKED"
    if invalid_markers:
        return "CITATION VALIDATION NEEDED"
    if any(not result.has_any_citation for result in successful_cases):
        return "PROMPT RELIABILITY IMPROVEMENT NEEDED"
    return "NO CHANGE NEEDED"


def format_citation_benchmark_report(report: CitationBenchmarkReport) -> str:
    """Format concise diagnostics without rendering answer or source content."""
    lines = []
    for index, result in enumerate(report.case_results, start=1):
        lines.append(f"[{index}/{report.summary.total_cases}] {result.query}")
        if not result.succeeded:
            lines.append(f"Failed: {result.failure_reason}")
            continue
        lines.append(
            "Sources: "
            f"{result.available_source_count} | Cited: {result.unique_valid_sources_cited} | "
            f"Markers: {result.total_citation_markers} | Valid: {result.valid_citation_markers} | "
            f"Invalid: {result.invalid_citation_markers} | Coverage: {result.source_coverage:.2f}"
        )

    summary = report.summary
    lines.extend(
        [
            "",
            f"Successful cases: {summary.successful_cases}/{summary.total_cases}",
            f"Cases with citations: {summary.cases_with_any_citation}/{summary.successful_cases}",
            f"Cases without citations: {summary.cases_without_citation}",
            f"Invalid citations: {summary.total_invalid_citation_markers}",
            f"Aggregate validity: {summary.aggregate_valid_citation_rate:.3f}",
            f"Average unique cited sources: {summary.average_unique_valid_sources_cited:.2f}",
            f"Average coverage: {summary.average_source_coverage:.3f}",
            f"Decision: {summary.decision}",
            "Caveat: this eight-query run is an engineering signal and regression baseline, not a production SLA or factual-correctness evaluation.",
        ]
    )
    return "\n".join(lines)
