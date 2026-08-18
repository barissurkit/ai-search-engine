from typing import Literal

from pydantic import BaseModel

from app.retrieval.evaluation.models import EvaluationCaseResult


class QueryRewriteCaseComparison(BaseModel):
    case_id: str
    original_query: str
    rewritten_query: str
    rewrite_changed: bool
    baseline: EvaluationCaseResult
    rewritten: EvaluationCaseResult
    outcome: Literal["improved", "unchanged", "regressed"]


class QueryRewriteComparisonSummary(BaseModel):
    evaluated_case_count: int
    baseline_mean_hit_rate_at_k: float
    rewritten_mean_hit_rate_at_k: float
    hit_rate_delta: float
    baseline_mean_recall_at_k: float
    rewritten_mean_recall_at_k: float
    recall_delta: float
    baseline_mean_reciprocal_rank: float
    rewritten_mean_reciprocal_rank: float
    reciprocal_rank_delta: float
    improved_case_count: int
    unchanged_case_count: int
    regressed_case_count: int


class QueryRewriteComparisonReport(BaseModel):
    k: int
    case_comparisons: list[QueryRewriteCaseComparison]
    summary: QueryRewriteComparisonSummary
