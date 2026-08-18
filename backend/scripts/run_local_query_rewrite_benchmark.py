import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import httpx
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings
from app.embeddings.ollama import OllamaEmbeddingProvider
from app.llm.ollama import OllamaLLMProvider
from app.retrieval.benchmark.fixtures import (
    BENCHMARK_CASES,
    BENCHMARK_CHUNKS,
    BENCHMARK_COLLECTION_NAME,
    BENCHMARK_SCOPE_ID,
    BENCHMARK_TOP_K,
)
from app.retrieval.benchmark.reporting import format_report
from app.retrieval.benchmark.retriever import ScopedRetrievalServiceRetriever
from app.retrieval.evaluation.evaluator import RetrievalEvaluator
from app.retrieval.experiments.service import QueryRewriteRetrievalExperiment
from app.retrieval.rewriting.service import LLMQueryRewriter
from app.retrieval.service import RetrievalService
from app.vectorstores.qdrant import QdrantVectorStore


async def main() -> None:
    settings = Settings(
        ollama_generation_model="qwen3:4b-instruct",
        ollama_embedding_model="embeddinggemma",
        ollama_embedding_dimensions=768,
        qdrant_collection_name=BENCHMARK_COLLECTION_NAME,
    )
    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)
    try:
        async with httpx.AsyncClient() as http_client:
            embedding_provider = OllamaEmbeddingProvider(settings, http_client)
            vector_store = QdrantVectorStore(
                settings,
                dimensions=embedding_provider.dimensions,
                client=qdrant_client,
            )
            retrieval_service = RetrievalService(embedding_provider, vector_store)
            await retrieval_service.index(BENCHMARK_CHUNKS, BENCHMARK_SCOPE_ID)

            experiment = QueryRewriteRetrievalExperiment(
                LLMQueryRewriter(OllamaLLMProvider(settings, http_client)),
                ScopedRetrievalServiceRetriever(retrieval_service, BENCHMARK_SCOPE_ID),
                RetrievalEvaluator(),
            )
            report = await experiment.run(BENCHMARK_CASES, BENCHMARK_TOP_K)
            print(format_report(report))
    finally:
        await qdrant_client.close()


if __name__ == "__main__":
    asyncio.run(main())
