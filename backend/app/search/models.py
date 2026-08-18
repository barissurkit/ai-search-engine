from typing import Annotated

from pydantic import BaseModel, HttpUrl, StringConstraints


class SearchRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
