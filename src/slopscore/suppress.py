"""Inline suppression of findings via HTML comments (works in plain text and Markdown).

Grammar (markdownlint-style; names are comma-separated rule_ids and/or dimension names, or empty
to mean "all"):

    <!-- slopscore-disable-file [names] -->        whole file from the comment onward
    <!-- slopscore-disable-line [names] -->        findings on the comment's own line
    <!-- slopscore-disable-next-line [names] -->   findings on the next line
    <!-- slopscore-disable [names] -->  ...  <!-- slopscore-enable [names] -->   block

Offsets index the canonical text the comments live in, so a finding whose span starts inside a
disabled range (and whose rule_id or dimension matches the range's names) is dropped.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

import regex as re

_COMMENT = re.compile(
    r"<!--\s*slopscore-(disable-file|disable-line|disable-next-line|disable|enable)\b([^>]*?)-->",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Range:
    start: int
    end: int
    names: frozenset[str]  # empty => matches everything


def _parse_names(raw: str) -> frozenset[str]:
    return frozenset(n.strip() for n in raw.replace(",", " ").split() if n.strip())


def _line_bounds(text: str, offset: int) -> tuple[int, int]:
    """(start, end) char offsets of the line containing ``offset`` (end is the newline or EOF)."""
    start = text.rfind("\n", 0, offset) + 1
    nl = text.find("\n", offset)
    return start, (len(text) if nl == -1 else nl)


class Suppressions:
    """Disabled ranges parsed from a text; queryable by finding span + rule/dimension."""

    def __init__(self, ranges: list[_Range], unknown: set[str]) -> None:
        self._ranges = sorted(ranges, key=lambda r: r.start)
        self._starts = [r.start for r in self._ranges]
        self.unknown_names = unknown

    def is_suppressed(self, start: int, rule_id: str, dimension: str) -> bool:
        # Check every range whose start <= the finding start.
        i = bisect.bisect_right(self._starts, start)
        for r in self._ranges[:i]:
            if r.start <= start < r.end and (
                not r.names or rule_id in r.names or dimension in r.names
            ):
                return True
        return False


def parse_suppressions(text: str, known_names: frozenset[str] | None = None) -> Suppressions:
    ranges: list[_Range] = []
    open_blocks: list[tuple[int, frozenset[str]]] = []  # (start_offset, names)
    unknown: set[str] = set()

    for m in _COMMENT.finditer(text):
        kind = m.group(1).lower()
        names = _parse_names(m.group(2))
        if known_names is not None:
            unknown |= {n for n in names if n not in known_names}
        line_start, line_end = _line_bounds(text, m.start())

        if kind == "disable-file":
            ranges.append(_Range(m.start(), len(text), names))
        elif kind == "disable-line":
            ranges.append(_Range(line_start, line_end, names))
        elif kind == "disable-next-line":
            _, this_end = line_start, line_end
            nxt_start = this_end + 1
            _, nxt_end = _line_bounds(text, nxt_start) if nxt_start <= len(text) else (0, 0)
            ranges.append(_Range(nxt_start, nxt_end, names))
        elif kind == "disable":
            open_blocks.append((m.end(), names))
        elif kind == "enable":
            still_open: list[tuple[int, frozenset[str]]] = []
            for b_start, b_names in open_blocks:
                # An enable with no names closes everything; otherwise only matching blocks.
                if not names or b_names == names or (b_names & names):
                    ranges.append(_Range(b_start, m.start(), b_names))
                else:
                    still_open.append((b_start, b_names))
            open_blocks = still_open

    for b_start, b_names in open_blocks:  # unclosed blocks run to EOF
        ranges.append(_Range(b_start, len(text), b_names))
    return Suppressions(ranges, unknown)
