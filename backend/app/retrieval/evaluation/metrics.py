from collections.abc import Sequence


def hit_rate_at_k(
    retrieved_source_identifiers: Sequence[str], relevant_source_identifiers: Sequence[str], k: int
) -> float:
    """Return whether at least one relevant source occurs in the first *k* results."""
    relevant_sources = _relevant_sources(relevant_source_identifiers)
    validate_k(k)
    return float(bool(relevant_sources.intersection(retrieved_source_identifiers[:k])))


def recall_at_k(
    retrieved_source_identifiers: Sequence[str], relevant_source_identifiers: Sequence[str], k: int
) -> float:
    """Return the fraction of unique relevant sources found in the first *k* results."""
    relevant_sources = _relevant_sources(relevant_source_identifiers)
    validate_k(k)
    if not relevant_sources:
        return 0.0
    found_sources = relevant_sources.intersection(retrieved_source_identifiers[:k])
    return len(found_sources) / len(relevant_sources)


def reciprocal_rank(
    retrieved_source_identifiers: Sequence[str], relevant_source_identifiers: Sequence[str]
) -> float:
    """Return the reciprocal rank of the first relevant result, or zero when absent."""
    relevant_sources = _relevant_sources(relevant_source_identifiers)
    for rank, source_identifier in enumerate(retrieved_source_identifiers, start=1):
        if source_identifier in relevant_sources:
            return 1.0 / rank
    return 0.0


def _relevant_sources(source_identifiers: Sequence[str]) -> set[str]:
    return set(source_identifiers)


def validate_k(k: int) -> None:
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer.")
