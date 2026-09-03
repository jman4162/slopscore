"""Structure tells: Markdown scaffolding that reads as chatbot output (WP:AISIGNS style section).

Emoji-led headings, bold inline-header lists (``**Speed:** fast``), heading levels that skip,
thematic breaks between every section, boldface density, and title-cased sub-headings. Scored from
the block metadata the Markdown ingester records (``Document.blocks``), so the markup is gone but
its shape is known. Plain text with no structure scores 0.

WEAK ALONE: technical documentation and READMEs use headings and lists legitimately, so this
dimension is corroboration-gated and profile-softened for ``technical``.
"""

from __future__ import annotations

from collections import Counter

import regex as re

from slopscore.document import Document
from slopscore.features.base import (
    SEVERITY_WEIGHT,
    per_hundred_words,
    register,
    saturating,
)
from slopscore.models import Dimension, Evidence, FeatureResult, Severity
from slopscore.spans import BlockMeta

_FULL_SCALE_PER_100 = 2.0
_INLINE_HEADER_MIN_ITEMS = 3
_BOLD_DENSITY_FULL = 0.08
_BOLD_RUNS_MIN = 3
_THEMATIC_BREAKS_MIN = 3

RULE_EMOJI_HEADING = "STRUCTURE_EMOJI_HEADING"
RULE_INLINE_HEADER_LIST = "STRUCTURE_INLINE_HEADER_LIST"
RULE_SKIPPED_LEVEL = "STRUCTURE_SKIPPED_HEADING_LEVEL"
RULE_THEMATIC_BREAKS = "STRUCTURE_THEMATIC_BREAKS"
RULE_BOLD_DENSITY = "STRUCTURE_BOLD_DENSITY"
RULE_TITLE_CASE = "STRUCTURE_TITLE_CASE_HEADING"
_RULES = frozenset(
    {
        RULE_EMOJI_HEADING,
        RULE_INLINE_HEADER_LIST,
        RULE_SKIPPED_LEVEL,
        RULE_THEMATIC_BREAKS,
        RULE_BOLD_DENSITY,
        RULE_TITLE_CASE,
    }
)
_EMOJI = re.compile(r"^\s*(?:\p{Extended_Pictographic}|\p{Emoji_Presentation})")


class StructureTells:
    dimension = Dimension.structure_tells

    def rule_ids(self) -> frozenset[str]:
        return _RULES

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
        return saturating(per_hundred_words(weighted, doc.word_count), _FULL_SCALE_PER_100)

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = self._spans(doc) if doc.blocks else []
        return FeatureResult(
            dimension=self.dimension, score=self.score_spans(doc, profile, spans), spans=spans
        )

    def _spans(self, doc: Document) -> list[Evidence]:
        blocks = doc.blocks
        text = doc.original_text
        spans: list[Evidence] = []

        def ev(b_start: int, b_end: int, rule: str, sev: Severity, why: str) -> None:
            end = min(b_end, len(text))
            spans.append(
                Evidence(
                    rule_id=rule,
                    severity=sev,
                    span=text[b_start:end],
                    start_char=b_start,
                    end_char=end,
                    explanation=why,
                )
            )

        # Emoji-led headings and list items.
        for b in blocks:
            if b.emoji_lead and b.kind in ("heading", "list_item"):
                ev(
                    b.start,
                    b.end,
                    RULE_EMOJI_HEADING,
                    Severity.medium,
                    "Emoji used as a heading or bullet decoration (WP:AIEMOJI).",
                )

        # Bold inline-header lists: runs of consecutive list items starting with **Label:**.
        run: list[BlockMeta] = []

        def flush() -> None:
            if len(run) >= _INLINE_HEADER_MIN_ITEMS:
                ev(
                    run[0].start,
                    run[-1].end,
                    RULE_INLINE_HEADER_LIST,
                    Severity.medium,
                    f"{len(run)} consecutive bullets with a bold inline header "
                    "('**Label:** text'), the chatbot listicle shape (WP:AILIST).",
                )
            run.clear()

        for b in blocks:
            if b.kind == "list_item" and b.bold_lead:
                run.append(b)
            else:
                flush()
        flush()

        # Heading levels that skip (H2 -> H4) and title-cased sub-headings.
        headings = [b for b in blocks if b.kind == "heading"]
        prev_level = 0
        for h in headings:
            if prev_level and h.level > prev_level + 1:
                ev(
                    h.start,
                    h.end,
                    RULE_SKIPPED_LEVEL,
                    Severity.low,
                    f"Heading level jumps from H{prev_level} to H{h.level}.",
                )
            prev_level = h.level
            if h.title_case and h.level >= 2:
                ev(
                    h.start,
                    h.end,
                    RULE_TITLE_CASE,
                    Severity.low,
                    "Title Case on a sub-heading (WP:AISIGNS title case).",
                )

        # Thematic breaks between sections.
        breaks = [b for b in blocks if b.break_before]
        if len(breaks) >= _THEMATIC_BREAKS_MIN and len(breaks) >= max(1, len(headings) // 2):
            first = breaks[0]
            ev(
                first.start,
                first.end,
                RULE_THEMATIC_BREAKS,
                Severity.low,
                f"{len(breaks)} horizontal rules separating sections.",
            )

        # Boldface density across the document.
        prose_chars = sum(b.end - b.start for b in blocks if b.kind != "heading")
        bold_chars = sum(b.bold_chars for b in blocks if b.kind != "heading")
        bold_blocks = [b for b in blocks if b.bold_chars and b.kind != "heading"]
        if prose_chars and len(bold_blocks) >= _BOLD_RUNS_MIN:
            density = bold_chars / prose_chars
            if density >= _BOLD_DENSITY_FULL:
                heaviest = max(bold_blocks, key=lambda b: b.bold_chars / max(1, b.end - b.start))
                ev(
                    heaviest.start,
                    heaviest.end,
                    RULE_BOLD_DENSITY,
                    Severity.low,
                    f"{density:.0%} of the prose is bold across {len(bold_blocks)} blocks "
                    "(WP:AIBOLD).",
                )

        spans.sort(key=lambda e: e.start_char)
        # One finding per rule per block at most.
        seen: Counter[tuple[str, int]] = Counter()
        out = []
        for e in spans:
            key = (e.rule_id, e.start_char)
            if seen[key]:
                continue
            seen[key] += 1
            out.append(e)
        return out


register(StructureTells())
