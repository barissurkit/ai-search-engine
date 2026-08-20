from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints


class DocumentChunk(BaseModel):
    """A non-empty, character-based segment of an ingested document."""

    content: Annotated[str, StringConstraints(min_length=1)]
    source_url: str
    final_url: str
    index: int
    title: str | None = None
    source_type: Literal["file"] | None = Field(default=None, exclude_if=lambda value: value is None)
    conversation_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    document_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    filename: str | None = Field(default=None, exclude_if=lambda value: value is None)
    page_number: int | None = Field(default=None, exclude_if=lambda value: value is None)


class CitationSource(BaseModel):
    """A source that can be cited in a generated answer."""

    citation_number: int
    url: str
    title: str | None = None
    source_type: Literal["file"] | None = Field(default=None, exclude_if=lambda value: value is None)
    document_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    filename: str | None = Field(default=None, exclude_if=lambda value: value is None)
    page_number: int | None = Field(default=None, exclude_if=lambda value: value is None)


class RAGAnswer(BaseModel):
    """A provider-independent answer with its supporting sources."""

    query: str
    answer: str
    sources: list[CitationSource]


class RAGPrompt(BaseModel):
    """A prompt and the citation sources represented within it."""

    prompt: str
    sources: list[CitationSource]


class RAGStreamProgress(BaseModel):
    type: Literal["progress"] = "progress"
    stage: Literal["searching", "ingesting", "retrieving", "generating"]


class RAGStreamDelta(BaseModel):
    type: Literal["delta"] = "delta"
    text: str


class RAGStreamSources(BaseModel):
    type: Literal["sources"] = "sources"
    sources: list[CitationSource]


class RAGStreamComplete(BaseModel):
    type: Literal["complete"] = "complete"


class RAGStreamError(BaseModel):
    type: Literal["error"] = "error"
    message: str


type RAGStreamEvent = (
    RAGStreamProgress | RAGStreamDelta | RAGStreamSources | RAGStreamComplete | RAGStreamError
)
