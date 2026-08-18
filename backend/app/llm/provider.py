from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    async def generate(self, prompt: str) -> str: ...


@runtime_checkable
class StreamingLLMProvider(Protocol):
    """A provider that yields generated answer-text deltas over time."""

    def stream(self, prompt: str) -> AsyncIterator[str]: ...
