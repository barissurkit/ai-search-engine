from itertools import pairwise

import pytest
from pydantic import ValidationError

from app.rag.chunking import DocumentChunker
from app.rag.models import DocumentChunk
from app.web.models import Document


def document(content: str) -> Document:
    return Document(
        content=content,
        source_url="https://example.com/source",
        final_url="https://example.com/final",
        title="Example title",
    )


def test_short_document_becomes_one_chunk():
    chunks = DocumentChunker(chunk_size=100, chunk_overlap=20).chunk(document("Short text."))

    assert [chunk.content for chunk in chunks] == ["Short text."]
    assert [chunk.index for chunk in chunks] == [0]


def test_long_document_becomes_multiple_bounded_chunks():
    chunks = DocumentChunker(chunk_size=20, chunk_overlap=5).chunk(
        document("one two three four five six seven eight nine ten")
    )

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 20 for chunk in chunks)


def test_overlap_is_carried_from_the_end_of_one_chunk_to_the_next():
    chunks = DocumentChunker(chunk_size=15, chunk_overlap=5).chunk(
        document("alpha beta gamma delta epsilon zeta")
    )

    assert all(
        following.content.startswith(previous.content[-5:])
        for previous, following in pairwise(chunks)
    )


def test_metadata_and_indices_are_preserved_deterministically():
    chunks = DocumentChunker(chunk_size=12, chunk_overlap=3).chunk(
        document("alpha beta gamma delta epsilon")
    )

    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.source_url == "https://example.com/source" for chunk in chunks)
    assert all(chunk.final_url == "https://example.com/final" for chunk in chunks)
    assert all(chunk.title == "Example title" for chunk in chunks)


def test_chunking_does_not_lose_text_when_overlap_is_removed():
    content = "alpha beta gamma delta epsilon zeta eta theta"
    overlap = 6
    chunks = DocumentChunker(chunk_size=18, chunk_overlap=overlap).chunk(document(content))

    reconstructed = chunks[0].content + "".join(
        chunk.content[overlap:] for chunk in chunks[1:]
    )

    assert reconstructed == content


def test_empty_document_and_chunk_are_rejected():
    with pytest.raises(ValidationError):
        document("")
    with pytest.raises(ValidationError):
        DocumentChunk(
            content="",
            source_url="https://example.com/source",
            final_url="https://example.com/final",
            index=0,
        )


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(10, 10), (10, 11), (1, 1)],
)
def test_invalid_overlap_is_rejected(chunk_size: int, chunk_overlap: int):
    with pytest.raises(ValueError, match="smaller than chunk_size"):
        DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
