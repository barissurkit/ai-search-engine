import pytest

from app.rag.evaluation import (
    CitationAuditor,
    audit_rag_answer,
    extract_citation_markers,
)
from app.rag.models import CitationSource, RAGAnswer


def sources(count: int) -> list[CitationSource]:
    return [
        CitationSource(citation_number=index, url=f"https://example.test/{index}")
        for index in range(1, count + 1)
    ]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("", []),
        ("No citations here.", []),
        ("One [1].", [1]),
        ("Repeated [2] then [1] and [2].", [2, 1, 2]),
        ("Malformed [abc] [-1] [1a] [] [ 1] are ignored.", []),
        ("Multi-digit [12].", [12]),
        ("Unicode 【12】 then [1].", [12, 1]),
        ("Grouped [1, 2] and 【3,4】.", [1, 2, 3, 4]),
        ("Duplicates [1,1] and zero [0,2].", [1, 1, 0, 2]),
        ("Malformed 【abc】 【-1】 【1a】 【】.", []),
    ],
)
def test_extract_citation_markers_recognizes_only_strict_numeric_markers_in_order(
    answer: str, expected: list[int]
):
    assert extract_citation_markers(answer) == expected


def test_audit_empty_or_citation_free_answer_uses_deterministic_zero_metrics():
    audit = CitationAuditor().audit("", sources(4))

    assert audit.model_dump() == {
        "citation_markers": [],
        "invalid_reference_numbers": [],
        "total_marker_count": 0,
        "valid_marker_count": 0,
        "invalid_marker_count": 0,
        "valid_citation_rate": 0.0,
        "unique_valid_source_count": 0,
        "available_source_count": 4,
        "source_coverage": 0.0,
        "has_any_citation": False,
        "has_any_invalid_citation": False,
    }


def test_audit_counts_duplicate_valid_markers_but_deduplicates_source_coverage():
    audit = CitationAuditor().audit("Claim [2]. Attribution [1] [2].", sources(4))

    assert audit.citation_markers == [2, 1, 2]
    assert audit.total_marker_count == 3
    assert audit.valid_marker_count == 3
    assert audit.invalid_marker_count == 0
    assert audit.valid_citation_rate == 1.0
    assert audit.unique_valid_source_count == 2
    assert audit.source_coverage == 0.5
    assert audit.has_any_citation is True
    assert audit.has_any_invalid_citation is False


def test_audit_all_sources_cited_has_full_coverage():
    audit = CitationAuditor().audit("[1] [2] [3]", sources(3))

    assert audit.unique_valid_source_count == 3
    assert audit.source_coverage == 1.0


def test_audit_mixed_unicode_markers_preserves_validity_and_coverage():
    audit = CitationAuditor().audit("A [1]. B 【2】. C [1]. Bad 【7】.", sources(2))

    assert audit.citation_markers == [1, 2, 1, 7]
    assert audit.valid_marker_count == 3
    assert audit.invalid_reference_numbers == [7]
    assert audit.valid_citation_rate == 0.75
    assert audit.source_coverage == 1.0


def test_audit_grouped_markers_uses_each_reference_for_metrics():
    audit = CitationAuditor().audit("A [1,2]. B 【2, 3】.", sources(3))

    assert audit.citation_markers == [1, 2, 2, 3]
    assert audit.valid_marker_count == 4
    assert audit.unique_valid_source_count == 3
    assert audit.source_coverage == 1.0


@pytest.mark.parametrize("marker", [0, 7])
def test_audit_treats_out_of_range_markers_as_invalid(marker: int):
    audit = CitationAuditor().audit(f"Bad [{marker}].", sources(4))

    assert audit.valid_marker_count == 0
    assert audit.invalid_marker_count == 1
    assert audit.invalid_reference_numbers == [marker]
    assert audit.valid_citation_rate == 0.0
    assert audit.has_any_invalid_citation is True


def test_audit_mixed_and_repeated_invalid_markers_preserves_counts_and_order():
    audit = CitationAuditor().audit("[1] [7] [0] [7] [2]", sources(4))

    assert audit.total_marker_count == 5
    assert audit.valid_marker_count == 2
    assert audit.invalid_marker_count == 3
    assert audit.invalid_reference_numbers == [7, 0, 7]
    assert audit.valid_citation_rate == 0.4
    assert audit.unique_valid_source_count == 2
    assert audit.source_coverage == 0.5


def test_audit_with_no_sources_treats_every_numeric_marker_as_invalid():
    audit = CitationAuditor().audit("[1] [12]", [])

    assert audit.available_source_count == 0
    assert audit.valid_marker_count == 0
    assert audit.invalid_marker_count == 2
    assert audit.source_coverage == 0.0


def test_rag_answer_adapter_audits_without_mutating_the_answer():
    rag_answer = RAGAnswer(
        query="Question",
        answer="Markdown **claim** [1]. Invalid [3].",
        sources=sources(2),
    )

    audit = audit_rag_answer(rag_answer)

    assert rag_answer.answer == "Markdown **claim** [1]. Invalid [3]."
    assert audit.valid_marker_count == 1
    assert audit.invalid_reference_numbers == [3]
