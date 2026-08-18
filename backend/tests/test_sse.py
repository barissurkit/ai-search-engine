import json

from app.api.sse import serialize_rag_stream_event
from app.rag.models import (
    CitationSource,
    RAGStreamComplete,
    RAGStreamDelta,
    RAGStreamError,
    RAGStreamProgress,
    RAGStreamSources,
)


def test_serializes_each_rag_stream_event_as_sse():
    events = [
        (RAGStreamProgress(stage="searching"), "progress", {"stage": "searching"}),
        (RAGStreamDelta(text='First line\n"quoted"'), "delta", {"text": 'First line\n"quoted"'}),
        (
            RAGStreamSources(
                sources=[CitationSource(citation_number=1, url="https://example.com/source")]
            ),
            "sources",
            {
                "sources": [
                    {"citation_number": 1, "url": "https://example.com/source", "title": None}
                ]
            },
        ),
        (RAGStreamComplete(), "complete", {}),
        (RAGStreamError(message="RAG answer is unavailable."), "error", {"message": "RAG answer is unavailable."}),
    ]

    for event, name, payload in events:
        message = serialize_rag_stream_event(event)
        assert message.startswith(f"event: {name}\ndata: ")
        assert message.endswith("\n\n")
        assert "\n\"quoted\"" not in message
        assert json.loads(message.split("data: ", maxsplit=1)[1]) == payload
