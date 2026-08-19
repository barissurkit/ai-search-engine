"""Offline, provider-independent citation marker evaluation primitives."""

from app.rag.evaluation.benchmark import (
    CITATION_BENCHMARK_QUERIES,
    CitationBenchmarkRunner,
    format_citation_benchmark_report,
    summarize_citation_benchmark,
)
from app.rag.evaluation.evaluator import CitationAuditor, audit_rag_answer
from app.rag.evaluation.extractor import extract_citation_markers
from app.rag.evaluation.models import CitationAudit

__all__ = [
    "CITATION_BENCHMARK_QUERIES",
    "CitationAudit",
    "CitationAuditor",
    "CitationBenchmarkRunner",
    "audit_rag_answer",
    "extract_citation_markers",
    "format_citation_benchmark_report",
    "summarize_citation_benchmark",
]
