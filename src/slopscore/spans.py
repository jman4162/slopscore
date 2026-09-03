"""Lightweight span type shared by normalization and the document model.

Kept dependency-free to avoid an import cycle between ``document`` and ``normalize``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextSpan:
    """A segment (sentence or paragraph) with offsets in the CLEANED text."""

    text: str
    start: int
    end: int


@dataclass(frozen=True)
class BlockMeta:
    """Structure of one Markdown block, with offsets in the ORIGINAL (ingested prose) text.

    Recorded by the Markdown ingester so structure-level tells (emoji headings, bold inline-header
    lists, heading-level jumps) can be scored after the markup itself is gone.
    """

    start: int
    end: int
    kind: str  # heading | paragraph | list_item
    level: int = 0  # heading level, 0 otherwise
    bold_lead: bool = False  # starts with **Label:** (or **Label** followed by a colon)
    emoji_lead: bool = False  # first character is a pictographic emoji
    title_case: bool = False  # heading of 4+ words with every content word capitalized
    bold_chars: int = 0  # characters inside strong emphasis
    break_before: bool = False  # a thematic break (---) directly preceded this block
