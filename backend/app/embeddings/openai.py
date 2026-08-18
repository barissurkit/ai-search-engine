from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import Settings


class EmbeddingConfigurationError(ValueError):
    """Raised when embedding provider configuration is invalid."""


class EmbeddingProviderError(Exception):
    """Raised when an embedding request or response is invalid."""


class AsyncEmbeddingsClient(Protocol):
    async def create(
        self,
        *,
        input: list[str],
        model: str,
        dimensions: int,
    ) -> object: ...


class AsyncOpenAIClient(Protocol):
    embeddings: AsyncEmbeddingsClient


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings, client: AsyncOpenAIClient | None = None) -> None:
        api_key = settings.openai_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise EmbeddingConfigurationError(
                "OPENAI_API_KEY is required to use OpenAIEmbeddingProvider."
            )
        if settings.openai_embedding_dimensions < 1:
            raise EmbeddingConfigurationError(
                "OPENAI_EMBEDDING_DIMENSIONS must be at least 1."
            )

        self._model = settings.openai_embedding_model
        self._dimensions = settings.openai_embedding_dimensions
        self._client = client or AsyncOpenAI(api_key=api_key.get_secret_value())

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self._validate_texts(texts)
        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                input=texts,
                model=self._model,
                dimensions=self._dimensions,
            )
        except Exception as exc:
            raise EmbeddingProviderError("OpenAI embedding request failed.") from exc

        return self._extract_embeddings(response, expected_count=len(texts))

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingProviderError("Embedding text must not be empty.")

    def _extract_embeddings(
        self,
        response: object,
        expected_count: int,
    ) -> list[list[float]]:
        data = getattr(response, "data", None)
        if not isinstance(data, list) or len(data) != expected_count:
            raise EmbeddingProviderError("OpenAI embedding response was invalid.")

        embeddings_by_index: dict[int, list[float]] = {}
        for item in data:
            index = getattr(item, "index", None)
            embedding = getattr(item, "embedding", None)
            if (
                not isinstance(index, int)
                or index in embeddings_by_index
                or not isinstance(embedding, list)
                or len(embedding) != self._dimensions
                or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in embedding)
            ):
                raise EmbeddingProviderError("OpenAI embedding response was invalid.")
            embeddings_by_index[index] = [float(value) for value in embedding]

        if set(embeddings_by_index) != set(range(expected_count)):
            raise EmbeddingProviderError("OpenAI embedding response was invalid.")

        return [embeddings_by_index[index] for index in range(expected_count)]
