import asyncio

import pytest

from app.api.dependencies.providers import (
    create_embedding_provider,
    create_llm_provider,
)
from app.core.config import Settings
from app.embeddings.ollama import OllamaEmbeddingProvider, OllamaEmbeddingProviderError
from app.embeddings.openai import OpenAIEmbeddingProvider
from app.llm.ollama import OllamaLLMProvider, OllamaLLMProviderError
from app.llm.openai import OpenAILLMProvider


class FakeResponse:
    def __init__(self, payload: object, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    def json(self) -> object:
        return self.payload


class FakeClient:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def ollama_settings(**values: object) -> Settings:
    return Settings(_env_file=None, debug=False, **values)


def test_ollama_embedding_batches_inputs_once_and_preserves_order():
    client = FakeClient(FakeResponse({"embeddings": [[1.0] * 768, [2.0] * 768]}))
    provider = OllamaEmbeddingProvider(ollama_settings(), client)  # type: ignore[arg-type]

    vectors = asyncio.run(provider.embed_batch(["first", "second"]))

    assert provider.dimensions == 768
    assert vectors == [[1.0] * 768, [2.0] * 768]
    assert client.calls == [
        (
            "http://localhost:11434/api/embed",
            {"json": {"model": "embeddinggemma", "input": ["first", "second"]}},
        )
    ]


@pytest.mark.parametrize("payload", [{}, {"embeddings": [[1.0] * 767]}, {"embeddings": []}])
def test_ollama_embedding_rejects_malformed_responses(payload: object):
    provider = OllamaEmbeddingProvider(ollama_settings(), FakeClient(FakeResponse(payload)))  # type: ignore[arg-type]

    with pytest.raises(OllamaEmbeddingProviderError, match="response was invalid"):
        asyncio.run(provider.embed("text"))


def test_ollama_embedding_rejects_empty_input_without_request():
    client = FakeClient(FakeResponse({"embeddings": []}))
    provider = OllamaEmbeddingProvider(ollama_settings(), client)  # type: ignore[arg-type]

    assert asyncio.run(provider.embed_batch([])) == []
    with pytest.raises(OllamaEmbeddingProviderError, match="must not be empty"):
        asyncio.run(provider.embed(" "))
    assert client.calls == []


def test_ollama_generation_sends_model_prompt_and_normalizes_text():
    client = FakeClient(FakeResponse({"response": "Local answer."}))
    provider = OllamaLLMProvider(ollama_settings(), client)  # type: ignore[arg-type]

    assert asyncio.run(provider.generate("Prompt")) == "Local answer."
    assert client.calls == [
        (
            "http://localhost:11434/api/generate",
            {"json": {"model": "qwen3:4b-instruct", "prompt": "Prompt", "stream": False}},
        )
    ]


@pytest.mark.parametrize("payload", [{}, {"response": " "}])
def test_ollama_generation_rejects_malformed_responses(payload: object):
    provider = OllamaLLMProvider(ollama_settings(), FakeClient(FakeResponse(payload)))  # type: ignore[arg-type]

    with pytest.raises(OllamaLLMProviderError, match="response was invalid"):
        asyncio.run(provider.generate("Prompt"))


def test_provider_selector_uses_ollama_without_an_openai_key():
    client = FakeClient(FakeResponse({"embeddings": [[1.0] * 768]}))
    settings = ollama_settings()

    embedding_provider = create_embedding_provider(settings, client)  # type: ignore[arg-type]
    llm_provider = create_llm_provider(settings, client)  # type: ignore[arg-type]

    assert isinstance(embedding_provider, OllamaEmbeddingProvider)
    assert isinstance(llm_provider, OllamaLLMProvider)
    assert embedding_provider.dimensions == 768


def test_provider_selector_preserves_openai_option():
    settings = ollama_settings(
        llm_provider="openai",
        embedding_provider="openai",
        openai_api_key="openai-test-secret",
    )
    client = FakeClient(FakeResponse({}))

    assert isinstance(create_embedding_provider(settings, client), OpenAIEmbeddingProvider)  # type: ignore[arg-type]
    assert isinstance(create_llm_provider(settings, client), OpenAILLMProvider)  # type: ignore[arg-type]
