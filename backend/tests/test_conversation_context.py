from app.rag.conversation import MAX_HISTORY_TURNS, bound_history, compose_search_query
from app.search.models import ConversationTurn


def turn(role: str, content: str) -> ConversationTurn:
    return ConversationTurn(role=role, content=content)


def test_search_query_is_unchanged_without_history():
    assert compose_search_query("What is RAG?") == "What is RAG?"


def test_follow_up_search_query_uses_recent_user_questions_not_assistant_prose():
    history = [
        turn("user", "What is Retrieval-Augmented Generation?"),
        turn("assistant", "A long answer with citation [99]."),
    ]
    assert compose_search_query("What are its disadvantages?", history) == (
        "What is Retrieval-Augmented Generation? What are its disadvantages?"
    )


def test_explicit_topic_switch_stays_current_only():
    history = [turn("user", "Explain RAG"), turn("assistant", "Answer")]
    assert compose_search_query("Explain the CAP theorem.", history) == "Explain the CAP theorem."


def test_history_is_bounded_and_preserves_turn_order():
    history = [turn("user", f"Question {index}") for index in range(MAX_HISTORY_TURNS + 3)]
    bounded = bound_history(history)
    assert len(bounded) == MAX_HISTORY_TURNS
    assert bounded[0].content == "Question 3"
