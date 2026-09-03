"""Markdown ingestion: extract prose, dropping code, tables, and blockquotes.

We walk marko's GFM AST and keep heading and paragraph/list text while skipping fenced/indented
code, tables, inline code spans, blockquotes, and raw HTML, none of which should be scored as
prose. Blocks are rejoined with blank lines so paragraph segmentation still works. The parser
must be the GFM one: CommonMark has no table node, so pipe tables used to flow through as one
long "sentence" of cell text. Link text is kept and the URL appended in parentheses so the
specificity feature can count it as concrete evidence.

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
from marko.ext.gfm import elements as gfm

from slopscore.ingest import RawSource
from slopscore.models import SourceType
from slopscore.spans import BlockMeta

_SKIP_BLOCKS: tuple[type[Element], ...] = (
    block.FencedCode,
    block.CodeBlock,
    block.Quote,
    block.ThematicBreak,
    gfm.Table,
)
_PARSER = marko.Markdown(extensions=["gfm"])
_SKIP_INLINE: tuple[type[Element], ...] = (inline.CodeSpan, inline.Image)
_SLOP_COMMENT = re.compile(r"<!--\s*slopscore-[^>]*-->", re.IGNORECASE)


def _inline_text(el: Element | str) -> str:
    if isinstance(el, str):
        return el
    if isinstance(el, _SKIP_INLINE):
        return ""
    if isinstance(el, inline.LineBreak):
        return " "
    if isinstance(el, inline.Link):
        label = "".join(_inline_text(c) for c in el.children)
        dest = getattr(el, "dest", "") or ""
        return f"{label} ({dest})" if dest.startswith(("http://", "https://")) else label
    children = getattr(el, "children", "")
    if isinstance(children, str):
        return children
    return "".join(_inline_text(c) for c in children)


_EMOJI_LEAD = re.compile(r"^\s*(?:\p{Extended_Pictographic}|\p{Emoji_Presentation})")
_SMALL_WORDS = frozenset(
    "a an and as at but by for in nor of on or per so the to up via vs".split()
)


def _bold_chars(el: Element | str) -> int:
    if isinstance(el, str):
        return 0
    if isinstance(el, inline.StrongEmphasis):
        return len(_inline_text(el))
    children = getattr(el, "children", "")
    if isinstance(children, str):
        return 0
    return sum(_bold_chars(c) for c in children)


def _bold_lead(el: Element) -> bool:
    """``**Label:** text`` or ``**Label**: text``: the first inline child is strong emphasis that
    ends with a colon, or is followed by one."""
    children = getattr(el, "children", None)
    if not isinstance(children, list) or not children:
        return False
    first = children[0]
    if not isinstance(first, inline.StrongEmphasis):
        return False
    label = _inline_text(first).strip()
    if label.endswith(":"):
        return True
    nxt = children[1] if len(children) > 1 else None
    tail = _inline_text(nxt) if nxt is not None else ""
    return tail.lstrip().startswith(":")


def _title_case(text: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if len(words) < 4:
        return False
    content = [w for w in words[1:] if w.lower() not in _SMALL_WORDS]
    return bool(content) and all(w[0].isupper() for w in content)


class _Collector:
    def __init__(self) -> None:
        self.out: list[str] = []
        self.blocks: list[BlockMeta] = []
        self.pending: list[str] = []
        self.break_pending = False
        self.offset = 0

    def add(
        self,
        text: str,
        *,
        kind: str,
        level: int = 0,
        bold_lead: bool = False,
        emoji_lead: bool = False,
        title_case: bool = False,
        bold_chars: int = 0,
    ) -> None:
        if self.pending:
            text = "\n".join(self.pending) + "\n" + text
            self.pending.clear()
        if self.out:
            self.offset += 2  # the "\n\n" joiner
        start = self.offset
        self.out.append(text)
        self.offset += len(text)
        self.blocks.append(
            BlockMeta(
                start=start,
                end=self.offset,
                kind=kind,
                level=level,
                bold_lead=bold_lead,
                emoji_lead=emoji_lead,
                title_case=title_case,
                bold_chars=bold_chars,
                break_before=self.break_pending,
            )
        )
        self.break_pending = False


def _walk(el: Element, col: _Collector, in_list: bool = False) -> None:
    children = getattr(el, "children", None)
    if not isinstance(children, list):
        return
    for child in children:
        if isinstance(child, block.HTMLBlock):
            # Keep slopscore control comments (stash to glue above the next block); drop other HTML.
            col.pending.extend(_SLOP_COMMENT.findall(getattr(child, "body", "") or ""))
            continue
        if isinstance(child, block.ThematicBreak):
            col.break_pending = True
            continue
        if isinstance(child, _SKIP_BLOCKS):
            continue
        if isinstance(child, (block.Heading, block.Paragraph)):
            text = _inline_text(child).strip()
            if not text:
                continue
            emoji = bool(_EMOJI_LEAD.match(text))
            bold = _bold_chars(child)
            if isinstance(child, block.Heading):
                col.add(
                    text,
                    kind="heading",
                    level=int(getattr(child, "level", 1) or 1),
                    title_case=_title_case(text),
                    emoji_lead=emoji,
                    bold_chars=bold,
                )
            else:
                col.add(
                    text,
                    kind="list_item" if in_list else "paragraph",
                    bold_lead=_bold_lead(child),
                    emoji_lead=emoji,
                    bold_chars=bold,
                )
        else:
            _walk(child, col, in_list or isinstance(child, block.ListItem))


def markdown_to_prose_with_blocks(md_text: str) -> tuple[str, list[BlockMeta]]:
    document = _PARSER.parse(md_text)
    col = _Collector()
    _walk(document, col)
    if col.pending:  # control comments with no following block (e.g. trailing disable-file)
        col.add("\n".join(col.pending), kind="paragraph")
        col.pending.clear()
    return "\n\n".join(col.out), col.blocks


def markdown_to_prose(md_text: str) -> str:
    return markdown_to_prose_with_blocks(md_text)[0]


def ingest_markdown(md_text: str, source: str = "<string>") -> RawSource:
    prose, blocks = markdown_to_prose_with_blocks(md_text)
    return RawSource(text=prose, source_type=SourceType.markdown, source=source, blocks=blocks)
