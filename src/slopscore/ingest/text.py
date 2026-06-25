"""Plain-text / pasted-string ingestion.

Fenced code blocks (``` or ~~~ delimited) are stripped before scoring: code is not prose, and
leaving the fences in inflates the ``prompt_residue`` dimension (a Markdown post with code blocks
should not read as "severe"). The Markdown ingester already drops code via its AST; this does the
same for plain text, ``.mdx``, stdin, and the ``scan_text`` API on a raw Markdown string.
"""

from __future__ import annotations

import regex as re

from slopscore.ingest import RawSource
from slopscore.models import SourceType

# A fenced code block: an opening ``` / ~~~ line through its matching closing fence line.
_FENCED = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")


def strip_fenced_code(text: str) -> str:
    """Remove fenced code blocks, leaving a blank line so paragraph segmentation still works."""
    return str(_FENCED.sub("\n", text))


def ingest_text(text: str, source: str = "<string>") -> RawSource:
    return RawSource(text=strip_fenced_code(text), source_type=SourceType.text, source=source)
