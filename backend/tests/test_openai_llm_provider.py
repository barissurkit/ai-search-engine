import asyncio
from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.llm.openai import (
    LLMConfigurationError,
    LLMProviderError,
    OpenAILLMProvider,
)
from app.llm.provider import LLMProvider


@dataclass
class FakeResponse:
    output_text: str


class FakeResponsesClient:
    def __init__(self, response: object | Exception) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class FakeClient:
    def __init__(self, response: object | Exception) -> None:
        self.responses = FakeResponsesClient(response)


def create_provider(response: object | Exception):
    settings = Settings(
        _env_file=None,
        debug=False,
        openai_api_key="openai-test-secret",
        openai_generation_model="test-generation-model",
    )
    client = FakeClient(response)
    return OpenAILLMProvider(settings, client), client


def test_generate_sends_prompt_and_model_and_returns_generated_text():
    provider, client = create_provider(FakeResponse("Generated answer."))

    generated_text = asyncio.run(provider.generate("What is RAG?"))

    assert isinstance(provider, LLMProvider)
    assert generated_text == "Generated answer."
    assert client.responses.calls == [
        {
            "model": "test-generation-model",
            "input": "What is RAG?",
        }
    ]


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_generate_rejects_empty_prompt_without_a_request(prompt: str):
    provider, client = create_provider(FakeResponse("Unused"))

    with pytest.raises(LLMProviderError, match="Prompt must not be empty"):
        asyncio.run(provider.generate(prompt))

    assert client.responses.calls == []


def test_provider_rejects_missing_api_key():
    settings = Settings(_env_file=None, debug=False)

    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        OpenAILLMProvider(settings, FakeClient(FakeResponse("Unused")))


@pytest.mark.parametrize("response", [object(), FakeResponse(""), FakeResponse(" \n\t ")])
def test_generate_rejects_invalid_or_empty_response(response: object):
    provider, _ = create_provider(response)

    with pytest.raises(LLMProviderError, match="response was invalid"):
        asyncio.run(provider.generate("A valid prompt"))


def test_generate_converts_client_errors_without_leaking_secret():
    provider, _ = create_provider(RuntimeError("openai-test-secret request failed"))

    with pytest.raises(LLMProviderError, match="request failed") as exc_info:
        asyncio.run(provider.generate("A valid prompt"))

    assert "openai-test-secret" not in str(exc_info.value)
