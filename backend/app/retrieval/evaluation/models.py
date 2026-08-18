from typing import Annotated

from pydantic import BaseModel, StringConstraints

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class EvaluationCase(BaseModel):
    """A query and the source identifiers considered relevant to it."""

    id: NonEmptyString
    query: NonEmptyString
    relevant_sources: list[NonEmptyString]


class RetrievalObservation(BaseModel):
    """A provider-neutral representation of one ranked retrieval result."""

    source_identifier: NonEmptyString


class EvaluationCaseResult(BaseModel):
    case_id: str
    hit_rate_at_k: float
    recall_at_k: float
    reciprocal_rank: float


class RetrievalSummary(BaseModel):
    evaluated_case_count: int
    mean_hit_rate_at_k: float
    mean_recall_at_k: float
    mean_reciprocal_rank: float


class RetrievalEvaluationReport(BaseModel):
    k: int
    case_results: list[EvaluationCaseResult]
    summary: RetrievalSummary
