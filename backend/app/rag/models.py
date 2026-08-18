from typing import Annotated

from pydantic import BaseModel, StringConstraints


class DocumentChunk(BaseModel):
    """A non-empty, character-based segment of an ingested document."""

    content: Annotated[str, StringConstraints(min_length=1)]
    source_url: str
    final_url: str
    index: int
    title: str | None = None
