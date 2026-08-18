from typing import Annotated

from pydantic import BaseModel, StringConstraints


class DocumentChunk(BaseModel):
    """A non-empty, character-based segment of an ingested document."""

    content: Annotated[str, StringConstraints(min_length=1)]
    source_url: str
    final_url: str
    index: int
    title: str | None = None


class CitationSource(BaseModel):
    """A source that can be cited in a generated answer."""

    citation_number: int
    url: str
    title: str | None = None


class RAGAnswer(BaseModel):
    """A provider-independent answer with its supporting sources."""

    query: str
    answer: str
    sources: list[CitationSource]


class RAGPrompt(BaseModel):
    """A prompt and the citation sources represented within it."""

    prompt: str
    sources: list[CitationSource]
