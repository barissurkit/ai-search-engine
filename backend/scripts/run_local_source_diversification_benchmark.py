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
from app.retrieval.benchmark.diversification import (
    SourceDiversificationBenchmark,
    format_diversification_report,
)
from app.retrieval.benchmark.fixtures import (
    BENCHMARK_CASES,
    BENCHMARK_CHUNKS,
    BENCHMARK_COLLECTION_NAME,
    BENCHMARK_SCOPE_ID,
    BENCHMARK_TOP_K,
)
from app.retrieval.diversification import SourceDiversifier
from app.retrieval.evaluation.evaluator import RetrievalEvaluator
from app.retrieval.service import RetrievalService
from app.vectorstores.qdrant import QdrantVectorStore


class ScopedScoredRetriever:
    def __init__(self, retrieval_service: RetrievalService, scope_id: str) -> None:
        self._retrieval_service = retrieval_service
        self._scope_id = scope_id

    async def retrieve(self, query: str, top_k: int):
        return await self._retrieval_service.retrieve(query, self._scope_id, top_k)


async def main() -> None:
    settings = Settings(
        ollama_embedding_model="embeddinggemma",
        ollama_embedding_dimensions=768,
        qdrant_collection_name=BENCHMARK_COLLECTION_NAME,
    )
    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)
    try:
        async with httpx.AsyncClient() as http_client:
            embeddings = OllamaEmbeddingProvider(settings, http_client)
            vector_store = QdrantVectorStore(settings, embeddings.dimensions, qdrant_client)
            retrieval_service = RetrievalService(embeddings, vector_store)
            await retrieval_service.index(BENCHMARK_CHUNKS, BENCHMARK_SCOPE_ID)
            report = await SourceDiversificationBenchmark(
                ScopedScoredRetriever(retrieval_service, BENCHMARK_SCOPE_ID),
                SourceDiversifier(max_chunks_per_source=1),
                RetrievalEvaluator(),
            ).run(BENCHMARK_CASES, BENCHMARK_TOP_K)
            print(format_diversification_report(report))
    finally:
        await qdrant_client.close()


if __name__ == "__main__":
    asyncio.run(main())
