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
