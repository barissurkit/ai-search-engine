from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedDocument:
    filename: str
    media_type: str
    pages: list[tuple[int | None, str]]


class DocumentExtractionError(ValueError):
    """Raised when an uploaded document is unsupported or has no usable text."""
