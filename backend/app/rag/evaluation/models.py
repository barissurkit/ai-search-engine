from pydantic import BaseModel


class CitationAudit(BaseModel):
    """Read-only audit of citation marker syntax, range validity, and coverage.

    This does not determine whether a citation supports a claim, whether the
    answer is factual, or whether an available source is trustworthy.
    """

    citation_markers: list[int]
    invalid_reference_numbers: list[int]
    total_marker_count: int
    valid_marker_count: int
    invalid_marker_count: int
    valid_citation_rate: float
    unique_valid_source_count: int
    available_source_count: int
    source_coverage: float
    has_any_citation: bool
    has_any_invalid_citation: bool
