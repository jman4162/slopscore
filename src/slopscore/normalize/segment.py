"""Sentence and paragraph segmentation over cleaned text.

Sentences use pySBD (pure-Python, no model download). Paragraphs split on blank lines.
Both return :class:`TextSpan` with offsets in the cleaned text.
"""

from __future__ import annotations

import re
import warnings

# pysbd ships regex strings with unescaped backslashes that trip SyntaxWarning on import/call.
# The library is otherwise fine; silence the third-party noise.
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

import pysbd  # noqa: E402

from slopscore.spans import TextSpan  # noqa: E402

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")

# pySBD segmenters are not thread-safe but are cheap to construct; one per call is fine
# for v0.1 document-at-a-time scanning.


def split_paragraphs(text: str) -> list[TextSpan]:
    spans: list[TextSpan] = []
    pos = 0
    for chunk in _PARAGRAPH_BREAK.split(text):
        start = text.find(chunk, pos) if chunk else pos
        if chunk.strip():
            spans.append(TextSpan(text=chunk, start=start, end=start + len(chunk)))
        pos = start + len(chunk)
    return spans


def split_sentences(text: str) -> list[TextSpan]:
    segmenter = pysbd.Segmenter(language="en", clean=False, char_span=True)
    spans: list[TextSpan] = []
    for seg in segmenter.segment(text):
        # char_span=True yields objects with .start/.end/.sent
        sent = seg.sent
        if sent.strip():
            spans.append(TextSpan(text=sent, start=seg.start, end=seg.end))
    return spans
