import trafilatura

MINIMUM_CONTENT_CHARACTERS = 40


class ContentExtractionError(Exception):
    """Raised when HTML cannot be converted into meaningful text."""


class ContentExtractor:
    def extract(self, html: str) -> str:
        try:
            content = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=False,
            )
        except Exception as exc:
            raise ContentExtractionError("Web page content could not be extracted.") from exc

        if content is None or len(content.strip()) < MINIMUM_CONTENT_CHARACTERS:
            raise ContentExtractionError(
                "Web page did not contain meaningful extractable content."
            )

        return content.strip()
