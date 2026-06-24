"""Text cleaning that preserves an offset mapping back to the source.

The ``original_text`` the rest of the pipeline reports against is the ftfy-fixed input
(mojibake repaired, readable). Cleaning then normalizes line endings and collapses runs of
horizontal whitespace, recording a mapping so evidence offsets point back at that text.
"""

from __future__ import annotations

import ftfy

from slopscore.normalize.offsets import MappingBuilder, OffsetMapper


def canonicalize(raw: str) -> str:
    """Repair encoding/mojibake and produce the canonical text we report against."""
    return ftfy.fix_text(raw)


def clean(canonical: str) -> tuple[str, OffsetMapper]:
    """Normalize newlines and collapse horizontal whitespace runs.

    Newlines are preserved (paragraph splitting depends on blank lines). A run of spaces
    and tabs becomes a single space, mapped to the first character of the run.
    """
    builder = MappingBuilder(canonical)
    i = 0
    n = len(canonical)
    while i < n:
        ch = canonical[i]
        if ch in " \t":
            run_start = i
            while i < n and canonical[i] in " \t":
                i += 1
            builder.emit(" ", run_start)
            continue
        if ch == "\r":
            # Normalize \r\n and bare \r to a single \n.
            run_start = i
            i += 1
            if i < n and canonical[i] == "\n":
                i += 1
            builder.emit("\n", run_start)
            continue
        builder.keep(ch, i)
        i += 1
    return builder.build()
