from typing import Protocol, runtime_checkable

from app.retrieval.rewriting.models import QueryRewriteResult


@runtime_checkable
class QueryRewriter(Protocol):
    """Rewrites a query without exposing a concrete model provider."""

    async def rewrite(self, query: str) -> QueryRewriteResult: ...
