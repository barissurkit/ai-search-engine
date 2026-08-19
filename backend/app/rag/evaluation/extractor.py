import re

_CITATION_MARKER_PATTERN = re.compile(
    r"(?:\[(\d+(?:\s*,\s*\d+)*)\]|【(\d+(?:\s*,\s*\d+)*)】)"
)


def extract_citation_markers(answer: str) -> list[int]:
    """Extract strict numeric ``[n]`` and ``【n】`` markers in appearance order.

    This recognizes marker syntax only. It intentionally does not decide whether
    a number refers to an available source.
    """
    return [
        int(number)
        for match in _CITATION_MARKER_PATTERN.finditer(answer)
        for number in (match.group(1) or match.group(2)).split(",")
    ]
