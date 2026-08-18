from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import Settings


class LLMConfigurationError(ValueError):
    """Raised when the LLM provider configuration is invalid."""


class LLMProviderError(Exception):
    """Raised when an LLM request or response is invalid."""


class AsyncResponsesClient(Protocol):
    async def create(self, *, model: str, input: str) -> object: ...


class AsyncOpenAIClient(Protocol):
    responses: AsyncResponsesClient


class OpenAILLMProvider:
    def __init__(self, settings: Settings, client: AsyncOpenAIClient | None = None) -> None:
        api_key = settings.openai_api_key
        if api_key is None or not api_key.get_secret_value().strip():
            raise LLMConfigurationError(
                "OPENAI_API_KEY is required to use OpenAILLMProvider."
            )

        self._model = settings.openai_generation_model
        self._client = client or AsyncOpenAI(api_key=api_key.get_secret_value())

    async def generate(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise LLMProviderError("Prompt must not be empty.")

        try:
            response = await self._client.responses.create(
                model=self._model,
                input=prompt,
            )
        except Exception as exc:
            raise LLMProviderError("OpenAI generation request failed.") from exc

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise LLMProviderError("OpenAI generation response was invalid.")

        return output_text
