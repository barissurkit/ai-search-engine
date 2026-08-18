from pydantic import BaseModel, field_validator, model_validator


class QueryRewriteResult(BaseModel):
    """The original retrieval query and its safe rewritten form."""

    original_query: str
    rewritten_query: str
    changed: bool = False

    @field_validator("original_query", "rewritten_query")
    @classmethod
    def require_non_empty_query(cls, value: str) -> str:
        if not isinstance(value, str) or not (normalized_query := value.strip()):
            raise ValueError("Query must not be empty.")
        return normalized_query

    @model_validator(mode="after")
    def set_changed(self) -> "QueryRewriteResult":
        self.changed = _comparison_key(self.original_query) != _comparison_key(self.rewritten_query)
        return self


def _comparison_key(query: str) -> str:
    return " ".join(query.split()).casefold()
