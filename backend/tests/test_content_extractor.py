import pytest

from app.web.extractor import ContentExtractionError, ContentExtractor


def test_extracts_main_content_without_common_html_noise():
    html = """
    <html>
      <head>
        <style>.banner { color: red; }</style>
        <script>window.tracker = 'ignore me';</script>
      </head>
      <body>
        <nav>Home Products Account</nav>
        <article>
          <h1>Useful article title</h1>
          <p>This is the first meaningful paragraph.</p>
          <p>This is the second meaningful paragraph.</p>
        </article>
      </body>
    </html>
    """

    content = ContentExtractor().extract(html)

    assert "Useful article title" in content
    assert "first meaningful paragraph" in content
    assert "second meaningful paragraph" in content
    assert "Home Products Account" not in content
    assert "window.tracker" not in content
    assert "color: red" not in content


def test_rejects_html_without_meaningful_content():
    html = "<html><body><nav>Home</nav><script>track()</script></body></html>"

    with pytest.raises(ContentExtractionError, match="meaningful"):
        ContentExtractor().extract(html)


def test_converts_library_errors_to_content_extraction_errors(monkeypatch):
    def raise_extraction_error(*args, **kwargs):
        raise ValueError("invalid HTML details")

    monkeypatch.setattr("app.web.extractor.trafilatura.extract", raise_extraction_error)

    with pytest.raises(ContentExtractionError, match="could not be extracted"):
        ContentExtractor().extract("<html></html>")
