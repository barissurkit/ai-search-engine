from typing import Annotated, Literal

from pydantic import BaseModel, HttpUrl, StringConstraints


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    history: list["ConversationTurn"] | None = None


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
