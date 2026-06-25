"""Map character offsets to 1-based (line, column) for SARIF physical locations.

Evidence offsets index ``Report.original_text``. SARIF regions are line/column based, so a
single forward pass over the text converts a ``[start, end)`` char span to
``(startLine, startColumn, endLine, endColumn)`` (all 1-based; endColumn is exclusive per the
SARIF spec). For Markdown the text is the extracted prose, so positions are prose-relative.
"""

from __future__ import annotations

import bisect


def _line_starts(text: str) -> list[int]:
    """Char offset at which each line begins (index 0 == line 1)."""
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def char_to_line_col(text: str, start: int, end: int) -> tuple[int, int, int, int]:
    """Return 1-based ``(startLine, startColumn, endLine, endColumn)`` for ``text[start:end]``."""
    if start < 0 or end < start or end > len(text):
        raise ValueError(f"span ({start}, {end}) out of range for text of length {len(text)}")
    starts = _line_starts(text)

    def line_col(offset: int) -> tuple[int, int]:
        # Rightmost line whose start is <= offset.
        line_idx = bisect.bisect_right(starts, offset) - 1
        return line_idx + 1, offset - starts[line_idx] + 1

    start_line, start_col = line_col(start)
    end_line, end_col = line_col(end)
    return start_line, start_col, end_line, end_col
