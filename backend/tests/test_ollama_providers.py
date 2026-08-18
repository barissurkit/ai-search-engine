import asyncio
from collections.abc import AsyncIterator

import httpx
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


class FakeStreamResponse:
    def __init__(self, lines: list[str], error: Exception | None = None) -> None:
        self.lines = lines
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self.lines:
            yield line


class FakeStreamContext:
    def __init__(self, response: FakeStreamResponse) -> None:
        self.response = response
        self.closed = False

    async def __aenter__(self) -> FakeStreamResponse:
        return self.response

    async def __aexit__(self, *args: object) -> None:
        self.closed = True


class FakeStreamingClient:
    def __init__(self, context: FakeStreamContext, error: Exception | None = None) -> None:
        self.context = context
        self.error = error
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def stream(self, *args: object, **kwargs: object) -> FakeStreamContext:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.context


def ollama_settings(**values: object) -> Settings:
    return Settings(_env_file=None, debug=False, **values)


def test_ollama_embedding_batches_inputs_once_and_preserves_order():
    client = FakeClient(FakeResponse({"embeddings": [[1.0] * 768, [2.0] * 768]}))
    provider = OllamaEmbeddingProvider(ollama_settings(), client)  # type: ignore[arg-type]

    vectors = asyncio.run(provider.embed_batch(["first", "second"]))

    assert provider.dimensions == 768
    assert vectors == [[1.0] * 768, [2.0] * 768]
    assert client.calls[0][0] == "http://localhost:11434/api/embed"
    assert client.calls[0][1]["json"] == {
        "model": "embeddinggemma",
        "input": ["first", "second"],
    }
    assert client.calls[0][1]["timeout"].read == 120.0


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
    assert client.calls[0][0] == "http://localhost:11434/api/generate"
    assert client.calls[0][1]["json"] == {
        "model": "qwen3:4b-instruct",
        "prompt": "Prompt",
        "stream": False,
    }
    assert client.calls[0][1]["timeout"].read == 120.0


@pytest.mark.parametrize("payload", [{}, {"response": " "}])
def test_ollama_generation_rejects_malformed_responses(payload: object):
    provider = OllamaLLMProvider(ollama_settings(), FakeClient(FakeResponse(payload)))  # type: ignore[arg-type]

    with pytest.raises(OllamaLLMProviderError, match="response was invalid"):
        asyncio.run(provider.generate("Prompt"))


def test_ollama_generation_stream_yields_text_deltas_and_closes_response():
    context = FakeStreamContext(
        FakeStreamResponse(
            [
                '{"response":"First "}',
                '{"response":""}',
                '{"response":"second"}',
                '{"done":true}',
            ]
        )
    )
    client = FakeStreamingClient(context)
    provider = OllamaLLMProvider(ollama_settings(), client)  # type: ignore[arg-type]

    async def collect() -> list[str]:
        return [part async for part in provider.stream("Prompt")]

    assert asyncio.run(collect()) == ["First ", "second"]
    assert client.calls == [
        (
            ("POST", "http://localhost:11434/api/generate"),
            {
                "json": {"model": "qwen3:4b-instruct", "prompt": "Prompt", "stream": True},
                "timeout": provider._timeout,
            },
        )
    ]
    assert context.closed is True


@pytest.mark.parametrize("lines", [["not json"], ['[]'], ['{"done": false}']])
def test_ollama_generation_stream_rejects_malformed_lines(lines: list[str]):
    context = FakeStreamContext(FakeStreamResponse(lines))
    provider = OllamaLLMProvider(ollama_settings(), FakeStreamingClient(context))  # type: ignore[arg-type]

    async def collect() -> None:
        async for _ in provider.stream("Prompt"):
            pass

    with pytest.raises(OllamaLLMProviderError, match="stream was invalid"):
        asyncio.run(collect())
    assert context.closed is True


def test_ollama_generation_stream_rejects_empty_prompt_without_request():
    context = FakeStreamContext(FakeStreamResponse([]))
    client = FakeStreamingClient(context)
    provider = OllamaLLMProvider(ollama_settings(), client)  # type: ignore[arg-type]

    async def collect() -> None:
        async for _ in provider.stream(" "):
            pass

    with pytest.raises(OllamaLLMProviderError, match="must not be empty"):
        asyncio.run(collect())
    assert client.calls == []


def test_ollama_generation_stream_converts_http_and_network_errors_to_safe_errors():
    request = httpx.Request("POST", "http://localhost:11434/api/generate")
    status_error = httpx.HTTPStatusError(
        "server error", request=request, response=httpx.Response(500, request=request)
    )
    response_context = FakeStreamContext(FakeStreamResponse([], error=status_error))
    network_context = FakeStreamContext(FakeStreamResponse([]))
    providers = [
        OllamaLLMProvider(ollama_settings(), FakeStreamingClient(response_context)),  # type: ignore[arg-type]
        OllamaLLMProvider(
            ollama_settings(),
            FakeStreamingClient(network_context, httpx.ReadTimeout("timeout", request=request)),
        ),  # type: ignore[arg-type]
    ]

    async def collect(provider: OllamaLLMProvider) -> None:
        async for _ in provider.stream("Prompt"):
            pass

    for provider in providers:
        with pytest.raises(OllamaLLMProviderError, match="request failed"):
            asyncio.run(collect(provider))


def test_ollama_generation_stream_closes_response_when_consumer_stops_early():
    context = FakeStreamContext(FakeStreamResponse(['{"response":"First"}', '{"response":"Second"}']))
    provider = OllamaLLMProvider(ollama_settings(), FakeStreamingClient(context))  # type: ignore[arg-type]

    async def consume_once() -> str:
        stream = provider.stream("Prompt")
        first = await anext(stream)
        await stream.aclose()
        return first

    assert asyncio.run(consume_once()) == "First"
    assert context.closed is True


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
