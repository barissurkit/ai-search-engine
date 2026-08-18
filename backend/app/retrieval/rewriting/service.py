import re

from app.llm.provider import LLMProvider
from app.retrieval.rewriting.models import QueryRewriteResult


class QueryRewriteError(ValueError):
    """Raised when a query cannot safely be considered for rewriting."""


class LLMQueryRewriter:
    """Use an LLM to clarify a retrieval query, with a safe original-query fallback."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def rewrite(self, query: str) -> QueryRewriteResult:
        original_query = _validate_query(query)
        try:
            generated_query = await self._llm_provider.generate(_build_rewrite_prompt(original_query))
        except Exception:  # noqa: BLE001 - every provider failure must safely fall back.
            return QueryRewriteResult(
                original_query=original_query,
                rewritten_query=original_query,
            )

        rewritten_query = _normalize_output(generated_query)
        if not rewritten_query:
            rewritten_query = original_query
        return QueryRewriteResult(
            original_query=original_query,
            rewritten_query=rewritten_query,
        )


def _validate_query(query: str) -> str:
    if not isinstance(query, str) or not (normalized_query := query.strip()):
        raise QueryRewriteError("Query must not be empty.")
    return normalized_query


def _build_rewrite_prompt(query: str) -> str:
    return (
        "Rewrite the user's search query for semantic retrieval. Preserve the user's intent. "
        "Do not add facts or invent people, dates, companies, products, or other details. "
        "Keep important keywords and the user's language whenever possible. Do not make the "
        "query unnecessarily long. Return only the rewritten query: no explanation, prefix, "
        "bullet list, Markdown, or reasoning.\n\n"
        "USER QUERY:\n"
        f"{query}"
    )


def _normalize_output(output: object) -> str:
    if not isinstance(output, str):
        return ""

    normalized = output.strip()
    fenced_match = re.fullmatch(r"```(?:[A-Za-z0-9_-]+)?\s*\n?(.*?)\n?```", normalized, re.DOTALL)
    if fenced_match:
        normalized = fenced_match.group(1).strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1].strip()
    return " ".join(normalized.split())
