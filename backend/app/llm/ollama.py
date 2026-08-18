import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings


class OllamaLLMProviderError(Exception):
    """Raised when an Ollama generation request or response is invalid."""


class OllamaLLMProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_generation_model
        self._timeout = httpx.Timeout(settings.ollama_request_timeout_seconds)
        self._client = client

    async def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise OllamaLLMProviderError("Prompt must not be empty.")
        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError, ValueError) as exc:
            raise OllamaLLMProviderError("Ollama generation request failed.") from exc

        text = payload.get("response") if isinstance(payload, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise OllamaLLMProviderError("Ollama generation response was invalid.")
        return text

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield only generated text from Ollama's NDJSON generation stream."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise OllamaLLMProviderError("Prompt must not be empty.")

        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": True},
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise OllamaLLMProviderError(
                            "Ollama generation stream was invalid."
                        ) from exc
                    if not isinstance(payload, dict):
                        raise OllamaLLMProviderError("Ollama generation stream was invalid.")

                    text = payload.get("response")
                    if text is None and payload.get("done") is True:
                        continue
                    if not isinstance(text, str):
                        raise OllamaLLMProviderError("Ollama generation stream was invalid.")
                    if text:
                        yield text
        except OllamaLLMProviderError:
            raise
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise OllamaLLMProviderError("Ollama generation request failed.") from exc
