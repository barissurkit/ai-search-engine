import re

_CITATION_MARKER_PATTERN = re.compile(r"\[(\d+)\]")


def extract_citation_markers(answer: str) -> list[int]:
    """Extract strict numeric ``[n]`` markers in their order of appearance.

    This recognizes marker syntax only. It intentionally does not decide whether
    a number refers to an available source.
    """
    return [int(match.group(1)) for match in _CITATION_MARKER_PATTERN.finditer(answer)]
