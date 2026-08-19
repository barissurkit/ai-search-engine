import httpx

from app.core.config import Settings
from app.core.http import optional_bearer_auth_headers


class OllamaEmbeddingConfigurationError(ValueError):
    """Raised when Ollama embedding configuration is invalid."""


class OllamaEmbeddingProviderError(Exception):
    """Raised when an Ollama embedding request or response is invalid."""


class OllamaEmbeddingProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        if settings.ollama_embedding_dimensions < 1:
            raise OllamaEmbeddingConfigurationError(
                "OLLAMA_EMBEDDING_DIMENSIONS must be at least 1."
            )
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_embedding_model
        self._dimensions = settings.ollama_embedding_dimensions
        self._timeout = httpx.Timeout(settings.ollama_request_timeout_seconds)
        self._headers = optional_bearer_auth_headers(settings.ollama_api_key)
        self._client = client

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise OllamaEmbeddingProviderError("Embedding text must not be empty.")
        if not texts:
            return []

        try:
            request_kwargs: dict[str, object] = {
                "json": {"model": self._model, "input": texts},
                "timeout": self._timeout,
            }
            if self._headers is not None:
                request_kwargs["headers"] = self._headers
            response = await self._client.post(
                f"{self._base_url}/api/embed", **request_kwargs
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
            raise OllamaEmbeddingProviderError("Ollama embedding request failed.") from exc

        embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise OllamaEmbeddingProviderError("Ollama embedding response was invalid.")
        if any(
            not isinstance(vector, list)
            or len(vector) != self._dimensions
            or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in vector)
            for vector in embeddings
        ):
            raise OllamaEmbeddingProviderError("Ollama embedding response was invalid.")
        return [[float(value) for value in vector] for vector in embeddings]
