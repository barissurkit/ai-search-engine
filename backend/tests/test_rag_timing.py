import asyncio

import pytest

import app.rag.service as rag_service_module
from app.rag.models import DocumentChunk, RAGStreamDelta, RAGStreamError
from app.rag.prompt import RAGPromptBuilder
from app.rag.service import RAGService, RAGServiceError
from app.rag.timing import PipelineTimings
from app.vectorstores.models import ScoredDocumentChunk
from app.web.models import Document


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class Search:
    async def search(self, _query):
        return [object()]


class Ingest:
    async def ingest(self, _results):
        return [Document(content="web evidence", source_url="https://example.com", final_url="https://example.com")]


class Chunker:
    def chunk(self, document):
        return [DocumentChunk(content=document.content, source_url=document.source_url, final_url=document.final_url, index=0)]


class Retrieval:
    def __init__(self) -> None:
        self.deleted_scopes: list[str] = []
        self.file_deletes: list[tuple] = []

    async def index(self, _chunks, scope_id):
        return None

    async def retrieve(self, _query, scope_id, top_k):
        return [ScoredDocumentChunk(chunk=DocumentChunk(content="web", source_url="https://example.com", final_url="https://example.com", index=0), score=0.9)]

    async def retrieve_file_chunks(self, _query, conversation, document_ids, _top_k):
        return [ScoredDocumentChunk(chunk=DocumentChunk(content="file", source_url="file://document", final_url="file://document", index=0, source_type="file", conversation_id=conversation, document_id=document_ids[0], filename="report.pdf", page_number=1), score=0.8)]

    async def delete_scope(self, scope_id):
        self.deleted_scopes.append(scope_id)

    async def delete_files(self, *args):
        self.file_deletes.append(args)


class LLM:
    def __init__(self, clock: FakeClock, *, fail_before_token: bool = False) -> None:
        self.clock = clock
        self.fail_before_token = fail_before_token

    async def generate(self, _prompt):
        self.clock.advance(0.2)
        return "answer [1]"

    async def stream(self, _prompt):
        self.clock.advance(0.3)
        if self.fail_before_token:
            raise RuntimeError("provider failed")
        yield "first "
        self.clock.advance(0.1)
        yield "second"


def build(clock: FakeClock, *, fail_before_token: bool = False):
    retrieval = Retrieval()
    service = RAGService(Search(), Ingest(), Chunker(), retrieval, RAGPromptBuilder(), LLM(clock, fail_before_token=fail_before_token), clock=clock)
    return service, retrieval


def capture_events(monkeypatch):
    events = []
    monkeypatch.setattr(rag_service_module.logger, "info", lambda _message, event: events.append(event))
    return events


def test_pipeline_timings_are_monotonic_sparse_and_serializable():
    clock = FakeClock()
    timings = PipelineTimings(clock=clock)
    started_at = timings.start_stage()
    clock.advance(0.125)
    timings.record("stage_ms", started_at)
    clock.advance(-1)
    timings.record_from_start("non_negative_ms")

    assert timings.finish() == {"stage_ms": 125.0, "non_negative_ms": 0.0, "total_ms": 0.0}
    assert "missing_ms" not in timings.finish()


@pytest.mark.parametrize(
    ("mode", "kwargs", "present", "absent"),
    [
        ("web", {}, {"web_search_ms", "web_retrieval_pipeline_ms", "generation_ms", "cleanup_ms"}, {"file_retrieval_ms"}),
        ("files", {"conversation_id": "conversation", "document_ids": ["document"]}, {"file_retrieval_ms", "generation_ms"}, {"web_search_ms", "web_retrieval_pipeline_ms", "cleanup_ms"}),
        ("hybrid", {"conversation_id": "conversation", "document_ids": ["document"]}, {"web_search_ms", "web_retrieval_pipeline_ms", "file_retrieval_ms", "generation_ms", "cleanup_ms"}, set()),
    ],
)
def test_nonstream_latency_event_matches_source_mode(monkeypatch, mode, kwargs, present, absent):
    clock = FakeClock()
    service, retrieval = build(clock)
    events = capture_events(monkeypatch)

    answer = asyncio.run(service.answer("question", source_mode=mode, **kwargs))

    assert answer.answer == "answer [1]"
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "rag_pipeline_latency"
    assert event["source_mode"] == mode and event["status"] == "success"
    assert {"query_preparation_ms", "total_ms", *present}.issubset(event)
    assert all(name not in event for name in absent)
    assert bool(retrieval.deleted_scopes) is (mode != "files")
    assert retrieval.file_deletes == []


def test_stream_latency_uses_first_delta_and_finalizes_on_abort(monkeypatch):
    clock = FakeClock()
    service, retrieval = build(clock)
    events = capture_events(monkeypatch)

    async def abort_after_first_delta():
        stream = service.stream_answer("question")
        while True:
            event = await stream.__anext__()
            if isinstance(event, RAGStreamDelta):
                await stream.aclose()
                return event

    assert asyncio.run(abort_after_first_delta()).text == "first "
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "aborted"
    assert event["first_token_ms"] == 300.0
    assert {"generation_ms", "cleanup_ms", "total_ms"}.issubset(event)
    assert len(retrieval.deleted_scopes) == 1 and retrieval.file_deletes == []


def test_stream_pre_token_error_omits_first_token_and_preserves_safe_error(monkeypatch):
    clock = FakeClock()
    service, retrieval = build(clock, fail_before_token=True)
    events = capture_events(monkeypatch)

    async def collect():
        return [event async for event in service.stream_answer("question", source_mode="hybrid", conversation_id="conversation", document_ids=["document"])]

    stream_events = asyncio.run(collect())
    assert isinstance(stream_events[-1], RAGStreamError)
    assert events[0]["status"] == "error"
    assert "first_token_ms" not in events[0]
    assert {"generation_ms", "cleanup_ms", "total_ms", "file_retrieval_ms"}.issubset(events[0])
    assert len(retrieval.deleted_scopes) == 1 and retrieval.file_deletes == []


def test_nonstream_generation_error_remains_a_safe_rag_error(monkeypatch):
    clock = FakeClock()
    service, retrieval = build(clock)
    events = capture_events(monkeypatch)

    async def fail(_prompt):
        clock.advance(0.1)
        raise RAGServiceError("generation failed")

    monkeypatch.setattr(service, "_generate", fail)
    with pytest.raises(RAGServiceError, match="generation failed"):
        asyncio.run(service.answer("question"))
    assert events[0]["status"] == "error"
    assert {"generation_ms", "cleanup_ms", "total_ms"}.issubset(events[0])
    assert len(retrieval.deleted_scopes) == 1
