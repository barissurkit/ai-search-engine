from collections.abc import Sequence

from app.rag.evaluation.extractor import extract_citation_markers
from app.rag.evaluation.models import CitationAudit
from app.rag.models import CitationSource, RAGAnswer


class CitationAuditor:
    """Audit citation markers without providers, network calls, or answer changes."""

    def audit(self, answer: str, sources: Sequence[CitationSource]) -> CitationAudit:
        """Measure marker range validity and source-reference coverage.

        Validity uses the established one-indexed source-list convention. Coverage
        means the fraction of available sources referenced at least once; it is
        not evidence that the cited sources support the answer.
        """
        markers = extract_citation_markers(answer)
        available_source_count = len(sources)
        valid_markers = [
            marker for marker in markers if 1 <= marker <= available_source_count
        ]
        invalid_markers = [
            marker for marker in markers if marker < 1 or marker > available_source_count
        ]
        unique_valid_sources = set(valid_markers)
        total_marker_count = len(markers)

        return CitationAudit(
            citation_markers=markers,
            invalid_reference_numbers=invalid_markers,
            total_marker_count=total_marker_count,
            valid_marker_count=len(valid_markers),
            invalid_marker_count=len(invalid_markers),
            valid_citation_rate=(len(valid_markers) / total_marker_count)
            if total_marker_count
            else 0.0,
            unique_valid_source_count=len(unique_valid_sources),
            available_source_count=available_source_count,
            source_coverage=(len(unique_valid_sources) / available_source_count)
            if available_source_count
            else 0.0,
            has_any_citation=bool(markers),
            has_any_invalid_citation=bool(invalid_markers),
        )


def audit_rag_answer(answer: RAGAnswer) -> CitationAudit:
    """Audit an existing RAG answer without changing it or its sources."""
    return CitationAuditor().audit(answer.answer, answer.sources)
