import asyncio

import pytest

from app.retrieval.rewriting.models import QueryRewriteResult
from app.retrieval.rewriting.provider import QueryRewriter
from app.retrieval.rewriting.service import LLMQueryRewriter, QueryRewriteError


class FakeLLMProvider:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_successful_rewrite_preserves_the_trimmed_original_and_marks_a_change():
    provider = FakeLLMProvider("benefits and advantages of Retrieval-Augmented Generation (RAG)")

    result = asyncio.run(LLMQueryRewriter(provider).rewrite("  What are the benefits of RAG?  "))

    assert result == QueryRewriteResult(
        original_query="What are the benefits of RAG?",
        rewritten_query="benefits and advantages of Retrieval-Augmented Generation (RAG)",
        changed=True,
    )


def test_rewrite_normalizes_newlines_surrounding_quotes_and_code_fences():
    provider = FakeLLMProvider('```text\n"retrieval query with\nkeywords"\n```')

    result = asyncio.run(LLMQueryRewriter(provider).rewrite("original query"))

    assert result.rewritten_query == "retrieval query with keywords"
    assert result.changed is True


@pytest.mark.parametrize("output", ["", "   ", "\n\t"])
def test_empty_or_whitespace_llm_output_falls_back_to_original_query(output: str):
    result = asyncio.run(LLMQueryRewriter(FakeLLMProvider(output)).rewrite("original query"))

    assert result.original_query == "original query"
    assert result.rewritten_query == "original query"
    assert result.changed is False


def test_provider_failure_falls_back_without_exposing_provider_error():
    result = asyncio.run(
        LLMQueryRewriter(FakeLLMProvider(RuntimeError("provider-secret"))).rewrite("original query")
    )

    assert result.rewritten_query == "original query"
    assert result.changed is False


@pytest.mark.parametrize("query", ["", "  ", "\n\t"])
def test_whitespace_only_input_is_rejected(query: str):
    with pytest.raises(QueryRewriteError, match="must not be empty"):
        asyncio.run(LLMQueryRewriter(FakeLLMProvider("unused")).rewrite(query))


def test_normalized_equivalent_query_is_not_marked_as_changed():
    result = asyncio.run(LLMQueryRewriter(FakeLLMProvider("  ORIGINAL   QUERY ")).rewrite("original query"))

    assert result.changed is False


def test_prompt_explicitly_preserves_intent_and_restricts_unsafe_output_formats():
    provider = FakeLLMProvider("rewritten query")

    asyncio.run(LLMQueryRewriter(provider).rewrite("original query"))

    prompt = provider.prompts[0]
    assert "Preserve the user's intent" in prompt
    assert "Do not add facts" in prompt
    assert "no explanation, prefix, bullet list, Markdown, or reasoning" in prompt


def test_rewriter_conforms_to_the_provider_independent_contract():
    rewriter = LLMQueryRewriter(FakeLLMProvider("rewritten query"))

    assert isinstance(rewriter, QueryRewriter)
