from typing import Annotated, Literal

from pydantic import BaseModel, HttpUrl, StringConstraints, model_validator


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    history: list["ConversationTurn"] | None = None
    source_mode: Literal["web", "files", "hybrid"] = "web"
    conversation_id: str | None = None
    document_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_file_mode(self) -> "SearchRequest":
        if self.source_mode in {"files", "hybrid"}:
            if not self.conversation_id or not self.conversation_id.strip():
                raise ValueError("conversation_id is required for file source modes.")
            if not self.document_ids:
                raise ValueError("document_ids are required for file source modes.")
        return self


class ConversationTurn(BaseModel):
    """A client-provided, bounded conversational turn used only for this request."""

    role: Literal["user", "assistant"]
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
