"""Quoted spans: ranges of the cleaned text that sit inside straight double quotes.

Dialogue and quotations are someone else's words. Rules that judge the AUTHOR's sincerity or
sourcing (performative candor, unsupported claims, vague attribution) skip matches that fall wholly
inside a quoted range; a novelist's character may say "honestly" and "everyone knows" without the
narrator being charged for it. ftfy has already straightened curly quotes by the time this runs.

A quote is a pair of ``"`` on the same paragraph, at most ``_MAX_QUOTE_CHARS`` apart, opened at a
word boundary. Unpaired quotes are ignored. Single quotes are not considered: apostrophes make
them unreliable.
"""

from __future__ import annotations

import bisect

import regex as re

_QUOTE = re.compile(r'(?<![\w])"(?=\S)([^"\n]{1,400}?)(?<=\S)"')
_MAX_QUOTE_CHARS = 400


def quoted_ranges(text: str) -> list[tuple[int, int]]:
    """End-exclusive (start, end) ranges of the text inside quotation marks (marks excluded)."""
    ranges: list[tuple[int, int]] = []
    for m in _QUOTE.finditer(text):
        inner_start, inner_end = m.start(1), m.end(1)
        if inner_end - inner_start <= _MAX_QUOTE_CHARS:
            ranges.append((inner_start, inner_end))
    return ranges


def inside_quotes(ranges: list[tuple[int, int]], start: int, end: int) -> bool:
    """True when [start, end) lies wholly inside one quoted range."""
    if not ranges:
        return False
    starts = [r[0] for r in ranges]
    i = bisect.bisect_right(starts, start) - 1
    return i >= 0 and ranges[i][0] <= start and end <= ranges[i][1]
