import pytest

from app.documents.extractor import extract_document
from app.documents.models import DocumentExtractionError


@pytest.mark.parametrize(("filename", "content", "message"), [
    ("report.pdf", b"%PDF malformed", "PDF file is invalid"),
    ("report.docx", b"not a zip archive", "DOCX file is invalid"),
    ("empty.txt", b"", "no extractable text"),
    ("malware.exe", b"x", "Unsupported file type"),
])
def test_invalid_uploads_are_safe_application_errors(filename, content, message):
    with pytest.raises(DocumentExtractionError, match=message):
        extract_document(filename, content)
