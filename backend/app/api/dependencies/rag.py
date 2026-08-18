from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status

from app.api.dependencies.providers import (
    create_embedding_provider,
    create_llm_provider,
)
from app.core.config import Settings, get_settings
from app.rag.chunking import DocumentChunker
from app.rag.prompt import RAGPromptBuilder
from app.rag.service import RAGService
from app.retrieval.service import RetrievalService
from app.search.service import SearchService
from app.search.tavily import TavilySearchProvider
from app.vectorstores.qdrant import QdrantVectorStore
from app.web.extractor import ContentExtractor
from app.web.fetcher import WebFetcher
from app.web.ingestion import WebIngestionService


async def get_rag_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[RAGService]:
    try:
        async with httpx.AsyncClient() as client:
            embedding_provider = create_embedding_provider(settings, client)
            vector_store = QdrantVectorStore(settings, embedding_provider.dimensions)
            llm_provider = create_llm_provider(settings, client)
            yield RAGService(
                search_service=SearchService(TavilySearchProvider(settings, client)),
                ingestion_service=WebIngestionService(
                    fetcher=WebFetcher(settings, client),
                    extractor=ContentExtractor(),
                    max_concurrency=settings.web_ingestion_max_concurrency,
                ),
                chunker=DocumentChunker(),
                retrieval_service=RetrievalService(embedding_provider, vector_store),
                prompt_builder=RAGPromptBuilder(),
                llm_provider=llm_provider,
                retrieval_top_k=settings.rag_retrieval_top_k,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service is not configured.",
        ) from exc
