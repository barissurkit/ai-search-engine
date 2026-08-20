import asyncio

import pytest

from app.rag.models import DocumentChunk
from app.rag.prompt import RAGPromptBuilder
from app.rag.service import RAGService
from app.search.models import ConversationTurn, SearchRequest
from app.vectorstores.models import ScoredDocumentChunk
from app.web.models import Document


class Search:
    def __init__(self): self.queries = []
    async def search(self, query): self.queries.append(query); return [object()]
class Ingest:
    def __init__(self): self.calls = 0
    async def ingest(self, _): self.calls += 1; return [Document(content="web evidence", source_url="https://example.com", final_url="https://example.com")]
class Chunker:
    def chunk(self, document): return [DocumentChunk(content=document.content, source_url=document.source_url, final_url=document.final_url, index=0)]
class Retrieval:
    def __init__(self): self.index_scopes=[]; self.file_calls=[]; self.deleted=[]; self.file_deletes=[]
    async def index(self, _, scope_id): self.index_scopes.append(scope_id)
    async def retrieve(self, _, scope_id, top_k): return [ScoredDocumentChunk(chunk=DocumentChunk(content="web", source_url="https://example.com", final_url="https://example.com", index=0), score=.9)]
    async def retrieve_file_chunks(self, query, conversation, docs, top_k):
        self.file_calls.append((query, conversation, docs)); return [ScoredDocumentChunk(chunk=DocumentChunk(content="file", source_url="file://d", final_url="file://d", index=0, source_type="file", conversation_id=conversation, document_id=docs[0], filename="report.pdf", page_number=2), score=.8)]
    async def delete_scope(self, scope): self.deleted.append(scope)
    async def delete_files(self, *args): self.file_deletes.append(args)
class LLM:
    async def generate(self, _): return "answer [1]"
    async def stream(self, _): yield "answer [1]"

def build():
    search=Search(); ingest=Ingest(); retrieval=Retrieval(); return RAGService(search, ingest, Chunker(), retrieval, RAGPromptBuilder(), LLM()), search, ingest, retrieval


@pytest.mark.parametrize("mode", ["web", "files", "hybrid"])
def test_source_mode_nonstream_and_stream_branching(mode):
    value, search, ingest, retrieval = build(); kwargs = {} if mode == "web" else {"conversation_id":"conversation", "document_ids":["document"]}
    answer = asyncio.run(value.answer("What are its disadvantages?", source_mode=mode, **kwargs))
    async def collect(): return [event async for event in value.stream_answer("What are its disadvantages?", source_mode=mode, **kwargs)]
    asyncio.run(collect())
    assert bool(search.queries) is (mode != "files")
    assert bool(ingest.calls) is (mode != "files")
    assert bool(retrieval.file_calls) is (mode != "web")
    assert any(source.source_type == "file" for source in answer.sources) is (mode != "web")
    assert all(scope != "conversation" for scope in retrieval.index_scopes)


def test_source_mode_contract_and_followup_composition():
    assert SearchRequest(query="q").source_mode == "web"
    with pytest.raises(ValueError): SearchRequest(query="q", source_mode="unsupported")
    for mode in ("files", "hybrid"):
        with pytest.raises(ValueError): SearchRequest(query="q", source_mode=mode)
        assert SearchRequest(query="q", source_mode=mode, conversation_id="c", document_ids=["d"]).source_mode == mode
    value, search, _, retrieval = build()
    history = [ConversationTurn(role="user", content="What is Retrieval-Augmented Generation?")]
    asyncio.run(value.answer("What are its disadvantages?", history=history, source_mode="hybrid", conversation_id="c", document_ids=["d"]))
    assert search.queries[0] == "What is Retrieval-Augmented Generation? What are its disadvantages?"
    assert retrieval.file_calls[0][1:] == ("c", ["d"])


def test_files_only_demo_uses_only_persistent_pdf_evidence():
    value, search, ingest, retrieval = build()
    answer = asyncio.run(value.answer("What does the report say about revenue?", source_mode="files", conversation_id="demo-conversation", document_ids=["demo-report-id"]))
    assert search.queries == [] and ingest.calls == 0 and retrieval.index_scopes == []
    assert retrieval.file_calls == [("What does the report say about revenue?", "demo-conversation", ["demo-report-id"])]
    source = answer.sources[0]
    assert (source.source_type, source.filename, source.page_number) == ("file", "report.pdf", 2)
    assert retrieval.deleted == [] and retrieval.file_deletes == []


def test_hybrid_demo_combines_web_and_file_evidence_and_cleans_web_scope():
    value, search, ingest, retrieval = build()
    answer = asyncio.run(value.answer("Compare the report's performance with current market conditions.", source_mode="hybrid", conversation_id="demo-conversation", document_ids=["demo-report-id"]))
    assert search.queries and ingest.calls == 1
    assert retrieval.file_calls[0][1:] == ("demo-conversation", ["demo-report-id"])
    assert retrieval.index_scopes[0] != "demo-conversation"
    assert {source.source_type for source in answer.sources} == {"web", "file"}
    file_source = next(source for source in answer.sources if source.source_type == "file")
    assert (file_source.filename, file_source.page_number) == ("report.pdf", 2)
    assert retrieval.deleted == retrieval.index_scopes and retrieval.file_deletes == []
