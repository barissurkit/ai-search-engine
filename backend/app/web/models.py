from pydantic import BaseModel


class FetchedPage(BaseModel):
    source_url: str
    final_url: str
    html: str
