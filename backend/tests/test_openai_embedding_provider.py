import asyncio
from dataclasses import dataclass

import pytest

from app.core.config import Settings
from app.embeddings.openai import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
)
from app.embeddings.provider import EmbeddingProvider


@dataclass
class FakeEmbedding:
    index: int
    embedding: list[float]


@dataclass
class FakeResponse:
    data: list[FakeEmbedding]


class FakeEmbeddingsClient:
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
        self.embeddings = FakeEmbeddingsClient(response)


def create_provider(response: object | Exception, dimensions: int = 3):
    settings = Settings(
        _env_file=None,
        debug=False,
        openai_api_key="openai-test-secret",
        openai_embedding_dimensions=dimensions,
    )
    client = FakeClient(response)
    return OpenAIEmbeddingProvider(settings, client), client


def test_embed_returns_a_single_embedding():
    provider, client = create_provider(FakeResponse([FakeEmbedding(0, [0.1, 0.2, 0.3])]))

    embedding = asyncio.run(provider.embed("First chunk"))

    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimensions == 3
    assert embedding == [0.1, 0.2, 0.3]
    assert client.embeddings.calls == [
        {
            "input": ["First chunk"],
            "model": "text-embedding-3-small",
            "dimensions": 3,
        }
    ]


def test_embed_batch_uses_one_request_and_preserves_input_order():
    provider, client = create_provider(
        FakeResponse(
            [
                FakeEmbedding(2, [3.0, 3.0, 3.0]),
                FakeEmbedding(0, [1.0, 1.0, 1.0]),
                FakeEmbedding(1, [2.0, 2.0, 2.0]),
            ]
        )
    )

    embeddings = asyncio.run(
        provider.embed_batch(["First chunk", "Second chunk", "Third chunk"])
    )

    assert embeddings == [[1.0, 1.0, 1.0], [2.0, 2.0, 2.0], [3.0, 3.0, 3.0]]
    assert len(client.embeddings.calls) == 1


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_embed_rejects_empty_text(text: str):
    provider, client = create_provider(FakeResponse([]))

    with pytest.raises(EmbeddingProviderError, match="must not be empty"):
        asyncio.run(provider.embed(text))

    assert client.embeddings.calls == []


def test_embed_batch_rejects_empty_text_and_skips_empty_batch():
    provider, client = create_provider(FakeResponse([]))

    assert asyncio.run(provider.embed_batch([])) == []
    with pytest.raises(EmbeddingProviderError, match="must not be empty"):
        asyncio.run(provider.embed_batch(["Valid", " "]))
    assert client.embeddings.calls == []


def test_provider_rejects_missing_api_key():
    settings = Settings(_env_file=None, debug=False, openai_embedding_dimensions=3)

    with pytest.raises(EmbeddingConfigurationError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider(settings, FakeClient(FakeResponse([])))


def test_provider_converts_client_error_without_leaking_secret():
    provider, _ = create_provider(RuntimeError("openai-test-secret request failed"))

    with pytest.raises(EmbeddingProviderError, match="request failed") as exc_info:
        asyncio.run(provider.embed("A valid chunk"))

    assert "openai-test-secret" not in str(exc_info.value)


@pytest.mark.parametrize(
    "response",
    [
        object(),
        FakeResponse([]),
        FakeResponse([FakeEmbedding(0, [1.0, 2.0])]),
        FakeResponse([FakeEmbedding(1, [1.0, 2.0, 3.0])]),
    ],
)
def test_provider_rejects_invalid_or_wrong_dimension_response(response: object):
    provider, _ = create_provider(response)

    with pytest.raises(EmbeddingProviderError, match="response was invalid"):
        asyncio.run(provider.embed("A valid chunk"))
