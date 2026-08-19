"""Deterministic, bounded helpers for stateless conversation-aware RAG."""

from app.search.models import ConversationTurn

MAX_HISTORY_TURNS = 12
MAX_HISTORY_CHARACTERS = 12_000
MAX_SEARCH_QUERY_CHARACTERS = 700


def bound_history(history: list[ConversationTurn] | None) -> list[ConversationTurn]:
    """Keep recent turns within a predictable prompt budget."""
    if not history:
        return []
    selected: list[ConversationTurn] = []
    total = 0
    for turn in reversed(history[-MAX_HISTORY_TURNS:]):
        content = turn.content.strip()
        if total + len(content) > MAX_HISTORY_CHARACTERS:
            break
        selected.append(turn.model_copy(update={"content": content}))
        total += len(content)
    return list(reversed(selected))


def compose_search_query(current_query: str, history: list[ConversationTurn] | None = None) -> str:
    """Add recent user questions to ambiguous follow-ups without an LLM rewrite."""
    current = current_query.strip()
    if not history:
        return current
    prior_users = [turn.content.strip() for turn in bound_history(history) if turn.role == "user"]
    # An explicit, self-contained question is usually a topic switch.
    lower = current.lower()
    if len(current) > 70 or any(token in lower for token in ("explain ", "define ", "compare ")):
        return current
    context: list[str] = []
    for question in reversed(prior_users):
        if question.casefold() != current.casefold():
            context.append(question)
        if len(context) == 2:
            break
    if not context:
        return current
    result = " ".join([*reversed(context), current])
    return result[:MAX_SEARCH_QUERY_CHARACTERS].rstrip()
