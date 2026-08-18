from pydantic import BaseModel

from app.rag.models import DocumentChunk


class ScoredDocumentChunk(BaseModel):
    chunk: DocumentChunk
    score: float
