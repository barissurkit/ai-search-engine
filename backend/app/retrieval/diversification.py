from collections.abc import Sequence

from app.vectorstores.models import ScoredDocumentChunk


class SourceDiversificationError(ValueError):
    """Raised when source diversification is configured with an invalid limit."""


class SourceDiversifier:
    """Limit repeated final URLs while preserving ranked result order and scores.

    Chunks with a missing or blank final URL are retained without source grouping so unrelated
    malformed metadata cannot suppress one another.
    """

    def __init__(self, max_chunks_per_source: int) -> None:
        _validate_positive_integer(max_chunks_per_source, "max_chunks_per_source")
        self._max_chunks_per_source = max_chunks_per_source

    def diversify(
        self, results: Sequence[ScoredDocumentChunk], top_k: int
    ) -> list[ScoredDocumentChunk]:
        _validate_positive_integer(top_k, "top_k")
        selected: list[ScoredDocumentChunk] = []
        chunks_per_source: dict[str, int] = {}

        for result in results:
            source_identifier = _source_identifier(result)
            if source_identifier is not None:
                source_count = chunks_per_source.get(source_identifier, 0)
                if source_count >= self._max_chunks_per_source:
                    continue
                chunks_per_source[source_identifier] = source_count + 1

            selected.append(result)
            if len(selected) == top_k:
                break
        return selected


def _source_identifier(result: ScoredDocumentChunk) -> str | None:
    final_url = result.chunk.final_url
    if not isinstance(final_url, str) or not (normalized_url := final_url.strip()):
        return None
    return normalized_url


def _validate_positive_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SourceDiversificationError(f"{name} must be a positive integer.")
