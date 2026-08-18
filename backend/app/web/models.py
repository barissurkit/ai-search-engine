from typing import Annotated

from pydantic import BaseModel, StringConstraints


class FetchedPage(BaseModel):
    source_url: str
    final_url: str
    html: str


class Document(BaseModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    source_url: str
    final_url: str
