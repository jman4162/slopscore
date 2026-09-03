"""Plain-text / pasted-string ingestion.

Fenced code blocks (``` or ~~~ delimited) are stripped before scoring: code is not prose, and
leaving the fences in inflates the ``prompt_residue`` dimension (a Markdown post with code blocks
should not read as "severe"). The Markdown ingester already drops code via its AST; this does the
same for plain text, stdin, and the ``scan_text`` API on a raw string.

Text that is visibly Markdown (headings, list markers, bold runs, fences on two or more lines)
is routed through the Markdown ingester instead, so a draft pasted on stdin gets the same
treatment as the same draft saved as ``.md``: emphasis markers no longer hide phrases from the
rules ("Let's **dive into**"), tables and code are dropped, and the structure tells are scored.
"""

from __future__ import annotations

import regex as re

from slopscore.ingest import RawSource
from slopscore.models import SourceType

# A fenced code block: an opening ``` / ~~~ line through its matching closing fence line.
_FENCED = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")
_MARKDOWN_LINE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6} \S|[-*+] \S|\d+\. \S|```|~~~|>\s|\|.*\|[ \t]*$|\*\*[^*\n]+\*\*)"
)
_MARKDOWN_MIN_LINES = 2


def strip_fenced_code(text: str) -> str:
    """Remove fenced code blocks, leaving a blank line so paragraph segmentation still works."""
    return str(_FENCED.sub("\n", text))


def looks_like_markdown(text: str) -> bool:
    return len(_MARKDOWN_LINE.findall(text)) >= _MARKDOWN_MIN_LINES


def ingest_text(text: str, source: str = "<string>") -> RawSource:
    if looks_like_markdown(text):
        from slopscore.ingest.markdown import ingest_markdown

        return ingest_markdown(text, source=source)
    return RawSource(text=strip_fenced_code(text), source_type=SourceType.text, source=source)
