"""Markdown ingestion: extract prose, dropping code, tables, and blockquotes.

We walk marko's CommonMark AST and keep heading and paragraph/list text while skipping
fenced/indented code, inline code spans, blockquotes, and raw HTML, none of which should be
scored as prose. Blocks are rejoined with blank lines so paragraph segmentation still works.

One exception: standalone ``<!-- slopscore-... -->`` control comments are kept (other HTML is
still dropped) and glued onto the line directly above the block they guard, so inline suppression
(`suppress.py`) works in Markdown the same way it does in plain text. Inline end-of-line comments
already survive as ``InlineHTML`` inside their paragraph.

Offsets in the resulting report index this extracted prose, not the original ``.md`` bytes.
"""

from __future__ import annotations

import marko
import regex as re
from marko import block, inline
from marko.element import Element

from slopscore.ingest import RawSource
from slopscore.models import SourceType

_SKIP_BLOCKS: tuple[type[Element], ...] = (
    block.FencedCode,
    block.CodeBlock,
    block.Quote,
    block.ThematicBreak,
)
_SKIP_INLINE: tuple[type[Element], ...] = (inline.CodeSpan, inline.Image)
_SLOP_COMMENT = re.compile(r"<!--\s*slopscore-[^>]*-->", re.IGNORECASE)


def _inline_text(el: Element | str) -> str:
    if isinstance(el, str):
        return el
    if isinstance(el, _SKIP_INLINE):
        return ""
    if isinstance(el, inline.LineBreak):
        return " "
    children = getattr(el, "children", "")
    if isinstance(children, str):
        return children
    return "".join(_inline_text(c) for c in children)


def _walk(el: Element, out: list[str], pending: list[str]) -> None:
    children = getattr(el, "children", None)
    if not isinstance(children, list):
        return
    for child in children:
        if isinstance(child, block.HTMLBlock):
            # Keep slopscore control comments (stash to glue above the next block); drop other HTML.
            pending.extend(_SLOP_COMMENT.findall(getattr(child, "body", "") or ""))
            continue
        if isinstance(child, _SKIP_BLOCKS):
            continue
        if isinstance(child, (block.Heading, block.Paragraph)):
            text = _inline_text(child).strip()
            if text:
                if pending:
                    text = "\n".join(pending) + "\n" + text
                    pending.clear()
                out.append(text)
        else:
            _walk(child, out, pending)


def markdown_to_prose(md_text: str) -> str:
    document = marko.parse(md_text)
    blocks: list[str] = []
    pending: list[str] = []
    _walk(document, blocks, pending)
    if pending:  # control comments with no following block (e.g. trailing disable-file)
        blocks.append("\n".join(pending))
    return "\n\n".join(blocks)


def ingest_markdown(md_text: str, source: str = "<string>") -> RawSource:
    return RawSource(
        text=markdown_to_prose(md_text),
        source_type=SourceType.markdown,
        source=source,
    )
