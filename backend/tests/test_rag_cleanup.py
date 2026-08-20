import asyncio

import pytest

from app.rag.models import RAGPrompt, RAGStreamDelta, RAGStreamError
from app.rag.service import RAGService, RAGServiceError


class Retrieval:
    def __init__(self, fail_cleanup: bool = False): self.scopes = []; self.file_deletes = []; self.fail_cleanup = fail_cleanup
    async def delete_scope(self, scope):
        self.scopes.append(scope)
        if self.fail_cleanup: raise RuntimeError("cleanup failed")
    async def delete_files(self, *args): self.file_deletes.append(args)


class LLM:
    async def generate(self, prompt): return "answer"
    async def stream(self, prompt): yield "answer"


def service(retrieval: Retrieval) -> RAGService:
    return RAGService(None, None, None, retrieval, None, LLM())


def prepared(scope: str | None): return RAGPrompt(prompt="prompt", sources=[], retrieval_scope_id=scope)


def test_nonstream_web_cleanup_and_cleanup_failure_do_not_mask_success(monkeypatch):
    retrieval = Retrieval(fail_cleanup=True); value = service(retrieval)
    monkeypatch.setattr(value, "_prepare_prompt", lambda *args: asyncio.sleep(0, result=prepared("web-scope")))
    assert asyncio.run(value.answer("q")) .answer == "answer"
    assert retrieval.scopes == ["web-scope"] and retrieval.file_deletes == []


def test_nonstream_primary_error_still_cleans_scope(monkeypatch):
    retrieval = Retrieval(fail_cleanup=True); value = service(retrieval)
    monkeypatch.setattr(value, "_prepare_prompt", lambda *args: asyncio.sleep(0, result=prepared("web-scope")))
    async def fail(_): raise RAGServiceError("primary")
    monkeypatch.setattr(value, "_generate", fail)
    with pytest.raises(RAGServiceError, match="primary"): asyncio.run(value.answer("q"))
    assert retrieval.scopes == ["web-scope"]


@pytest.mark.parametrize("scope", ["web-scope", "hybrid-web-scope", None])
def test_stream_completion_and_files_persistence(monkeypatch, scope):
    retrieval = Retrieval(); value = service(retrieval)
    async def stages(*_): yield "generating", prepared(scope)
    monkeypatch.setattr(value, "_prepare_prompt_stages", stages)
    async def collect(): return [event async for event in value.stream_answer("q")]
    assert any(isinstance(event, RAGStreamDelta) for event in asyncio.run(collect()))
    assert retrieval.scopes == ([] if scope is None else [scope]) and retrieval.file_deletes == []


@pytest.mark.parametrize("scope", ["web-scope", "hybrid-web-scope", None])
def test_stream_close_runs_real_finally_without_file_deletion(monkeypatch, scope):
    retrieval = Retrieval(); value = service(retrieval)
    async def stages(*_): yield "generating", prepared(scope)
    monkeypatch.setattr(value, "_prepare_prompt_stages", stages)
    async def run():
        generator = value.stream_answer("q")
        await generator.__anext__()
        await generator.aclose()
    asyncio.run(run())
    assert retrieval.scopes == ([] if scope is None else [scope]) and retrieval.file_deletes == []


@pytest.mark.parametrize("scope", ["web-error-scope", "hybrid-web-error-scope"])
def test_stream_generation_error_cleans_only_the_current_web_scope(monkeypatch, scope):
    retrieval = Retrieval(); value = service(retrieval)
    async def stages(*_): yield "generating", prepared(scope)
    async def failing_stream(_):
        yield "partial"
        raise RuntimeError("generation failed")
    monkeypatch.setattr(value, "_prepare_prompt_stages", stages)
    monkeypatch.setattr(value._llm_provider, "stream", failing_stream)
    async def collect(): return [event async for event in value.stream_answer("q")]
    events = asyncio.run(collect())
    assert any(isinstance(event, RAGStreamDelta) for event in events)
    assert isinstance(events[-1], RAGStreamError)
    assert retrieval.scopes == [scope]
    assert retrieval.file_deletes == []
