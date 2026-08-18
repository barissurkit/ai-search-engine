from app.llm.provider import LLMProvider
from app.rag.chunking import DocumentChunker
from app.rag.models import RAGAnswer
from app.rag.prompt import RAGPromptBuilder
from app.retrieval.service import RetrievalService
from app.search.service import SearchService
from app.web.ingestion import WebIngestionService


class RAGServiceError(Exception):
    """Raised when a retrieval-grounded answer cannot be produced safely."""


class RAGService:
    def __init__(
        self,
        search_service: SearchService,
        ingestion_service: WebIngestionService,
        chunker: DocumentChunker,
        retrieval_service: RetrievalService,
        prompt_builder: RAGPromptBuilder,
        llm_provider: LLMProvider,
        retrieval_top_k: int = 5,
    ) -> None:
        if retrieval_top_k < 1:
            raise RAGServiceError("RAG retrieval top_k must be at least 1.")

        self._search_service = search_service
        self._ingestion_service = ingestion_service
        self._chunker = chunker
        self._retrieval_service = retrieval_service
        self._prompt_builder = prompt_builder
        self._llm_provider = llm_provider
        self._retrieval_top_k = retrieval_top_k

    async def answer(self, query: str) -> RAGAnswer:
        if not isinstance(query, str) or not query.strip():
            raise RAGServiceError("RAG query must not be empty.")

        search_results = await self._search(query)
        documents = await self._ingest(search_results)
        chunks = self._chunk_documents(documents)
        scope_id = str(uuid4())
        await self._index(chunks, scope_id)
        retrieved_chunks = await self._retrieve(query, scope_id)
        prompt = self._build_prompt(query, retrieved_chunks)
        generated_answer = await self._generate(prompt.prompt)

        return RAGAnswer(
            query=query,
            answer=generated_answer,
            sources=prompt.sources,
        )

    async def _search(self, query: str):
        try:
            results = await self._search_service.search(query)
        except Exception as exc:
            raise RAGServiceError("RAG web search failed.") from exc
        if not results:
            raise RAGServiceError("RAG web search returned no results.")
        return results

    async def _ingest(self, search_results):
        try:
            documents = await self._ingestion_service.ingest(search_results)
        except Exception as exc:
            raise RAGServiceError("RAG web ingestion failed.") from exc
        if not documents:
            raise RAGServiceError("RAG web ingestion returned no documents.")
        return documents

    def _chunk_documents(self, documents):
        try:
            chunks = [
                chunk
                for document in documents
                for chunk in self._chunker.chunk(document)
            ]
        except Exception as exc:
            raise RAGServiceError("RAG document chunking failed.") from exc
        if not chunks:
            raise RAGServiceError("RAG document chunking returned no chunks.")
        return chunks

    async def _index(self, chunks, scope_id: str) -> None:
        try:
            await self._retrieval_service.index(chunks, scope_id=scope_id)
        except Exception as exc:
            raise RAGServiceError("RAG document indexing failed.") from exc

    async def _retrieve(self, query: str, scope_id: str):
        try:
            chunks = await self._retrieval_service.retrieve(
                query,
                scope_id=scope_id,
                top_k=self._retrieval_top_k,
            )
        except Exception as exc:
            raise RAGServiceError("RAG retrieval failed.") from exc
        if not chunks:
            raise RAGServiceError("RAG retrieval returned no context.")
        return chunks

    def _build_prompt(self, query: str, retrieved_chunks):
        try:
            return self._prompt_builder.build(query, retrieved_chunks)
        except Exception as exc:
            raise RAGServiceError("RAG prompt building failed.") from exc

    async def _generate(self, prompt: str) -> str:
        try:
            return await self._llm_provider.generate(prompt)
        except Exception as exc:
            raise RAGServiceError("RAG answer generation failed.") from exc
from uuid import uuid4
