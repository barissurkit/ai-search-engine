"""Serialization of typed application stream events into SSE messages."""

import json

from app.rag.models import RAGStreamEvent


def serialize_rag_stream_event(event: RAGStreamEvent) -> str:
    """Return one standards-compliant SSE message for a RAG stream event."""
    payload = event.model_dump(mode="json", exclude={"type"})
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.type}\ndata: {data}\n\n"
