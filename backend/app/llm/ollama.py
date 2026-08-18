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
