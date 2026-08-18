import httpx

from app.core.config import Settings
from app.embeddings.ollama import OllamaEmbeddingProvider
from app.embeddings.openai import OpenAIEmbeddingProvider
from app.embeddings.provider import EmbeddingProvider
from app.llm.ollama import OllamaLLMProvider
from app.llm.openai import OpenAILLMProvider
from app.llm.provider import LLMProvider


def create_embedding_provider(settings: Settings, client: httpx.AsyncClient) -> EmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(settings, client)
    return OpenAIEmbeddingProvider(settings)


def create_llm_provider(settings: Settings, client: httpx.AsyncClient) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(settings, client)
    return OpenAILLMProvider(settings)
