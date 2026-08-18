from app.rag.models import DocumentChunk
from app.web.models import Document


class DocumentChunker:
    """Split documents into overlapping chunks measured in characters, not tokens."""

    def __init__(self, chunk_size: int = 1_000, chunk_overlap: int = 200) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1 character.")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative.")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk(self, document: Document) -> list[DocumentChunk]:
        """Return deterministic, overlapping character chunks for one document."""
        content = document.content
        chunks: list[DocumentChunk] = []
        start = 0

        while start < len(content):
            end = self._find_boundary(content, start)
            chunks.append(
                DocumentChunk(
                    content=content[start:end],
                    source_url=document.source_url,
                    final_url=document.final_url,
                    title=document.title,
                    index=len(chunks),
                )
            )

            if end == len(content):
                break
            start = end - self._chunk_overlap

        return chunks

    def _find_boundary(self, content: str, start: int) -> int:
        hard_end = min(start + self._chunk_size, len(content))
        if hard_end == len(content):
            return hard_end

        minimum_boundary = start + self._chunk_overlap + 1
        for position in range(hard_end - 1, minimum_boundary - 2, -1):
            if content[position].isspace():
                return position + 1

        return hard_end
