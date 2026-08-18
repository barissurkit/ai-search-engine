import pytest

from app.rag.models import DocumentChunk
from app.retrieval.diversification import SourceDiversificationError, SourceDiversifier
from app.vectorstores.models import ScoredDocumentChunk


def result(source: str, index: int, score: float) -> ScoredDocumentChunk:
    return ScoredDocumentChunk(
        chunk=DocumentChunk(
            content=f"content {index}",
            source_url=f"https://example.test/{source}",
            final_url=f"https://example.test/{source}",
            index=index,
        ),
        score=score,
    )


def test_all_distinct_sources_keep_order_scores_and_top_k():
    ranked = [result("a", 0, 0.9), result("b", 1, 0.8), result("c", 2, 0.7)]

    diversified = SourceDiversifier(1).diversify(ranked, top_k=2)

    assert diversified == ranked[:2]
    assert [item.score for item in diversified] == [0.9, 0.8]


def test_duplicate_leaders_make_room_for_later_sources_deterministically():
    ranked = [
        result("a", 0, 0.9),
        result("a", 1, 0.8),
        result("b", 0, 0.7),
        result("c", 0, 0.6),
    ]

    diversified = SourceDiversifier(1).diversify(ranked, top_k=3)

    assert diversified == [ranked[0], ranked[2], ranked[3]]


def test_max_chunks_per_source_two_retains_two_ranked_chunks_from_one_source():
    ranked = [result("a", 0, 0.9), result("a", 1, 0.8), result("a", 2, 0.7), result("b", 0, 0.6)]

    diversified = SourceDiversifier(2).diversify(ranked, top_k=4)

    assert diversified == [ranked[0], ranked[1], ranked[3]]


def test_empty_and_short_inputs_are_safe():
    assert SourceDiversifier(1).diversify([], top_k=3) == []
    ranked = [result("a", 0, 0.9)]
    assert SourceDiversifier(1).diversify(ranked, top_k=3) == ranked


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_invalid_source_limit_is_rejected(limit: int):
    with pytest.raises(SourceDiversificationError, match="positive integer"):
        SourceDiversifier(limit)


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_invalid_top_k_is_rejected(top_k: int):
    with pytest.raises(SourceDiversificationError, match="positive integer"):
        SourceDiversifier(1).diversify([], top_k)


def test_missing_or_invalid_final_urls_are_not_grouped_together():
    first = result("a", 0, 0.9).model_copy(update={"chunk": result("a", 0, 0.9).chunk.model_copy(update={"final_url": ""})})
    second = result("b", 0, 0.8).model_copy(update={"chunk": result("b", 0, 0.8).chunk.model_copy(update={"final_url": " "})})

    assert SourceDiversifier(1).diversify([first, second], top_k=2) == [first, second]
