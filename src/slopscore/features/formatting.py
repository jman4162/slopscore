"""Formatting tells: em-dash density and curly-quote ratio (WP:AIDASH, WP:AICURLY).

These are WEAK ALONE: em dashes and curly quotes appear in professionally edited human prose
(Chicago style, Word smart quotes), so this dimension is low-weighted and corroboration-gated in
the scorer.

Density metric: an em-dash-to-COMMA ratio (em / (em + commas)), not per-paragraph or per-100-words.
The ratio measures the actual tell (reaching for a dash where a comma would do) and is invariant to
both document length and paragraph structure. Per-100-words is a reasonable length-normalized
alternative; per-paragraph is avoided because the pipeline rejoins/normalizes paragraphs (markdown
extraction, code-prose concatenation) and short or single-paragraph inputs make that denominator
degenerate.

When the em-dash signal fires, one summary FORMATTING_EM_DASH span is emitted (pointing at the first
dash, with the count and ratio in its explanation) so the score is traceable; we do not flag every
dash, which would be noise.
"""

from __future__ import annotations

import regex as re

from slopscore.document import Document
from slopscore.features.base import register
from slopscore.models import Dimension, Evidence, FeatureResult, Severity

_EM_DASH = re.compile("[—–]")  # em dash, en dash
_COMMA = re.compile(r",")
_CURLY = re.compile("[“”‘’]")  # curly double/single quotes
_STRAIGHT = re.compile(r"[\"']")

# An em-dash-to-comma ratio at/above this looks dash-heavy in the LLM way.
_EMDASH_RATIO_FULL = 0.25


class FormattingTells:
    dimension = Dimension.formatting_tells

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        text = doc.cleaned_text
        em = len(_EM_DASH.findall(text))
        commas = len(_COMMA.findall(text))
        curly = len(_CURLY.findall(text))
        straight = len(_STRAIGHT.findall(text))

        emdash_ratio = em / (em + commas) if (em + commas) else 0.0
        curly_ratio = curly / (curly + straight) if (curly + straight) else 0.0

        # Need at least a couple of em dashes before the ratio means anything.
        emdash_signal = min(1.0, emdash_ratio / _EMDASH_RATIO_FULL) if em >= 2 else 0.0
        curly_signal = curly_ratio if curly >= 2 else 0.0

        spans: list[Evidence] = []
        if emdash_signal > 0:
            first = _EM_DASH.search(text)
            if first is not None:
                spans.append(
                    doc.evidence(
                        rule_id="FORMATTING_EM_DASH",
                        severity=Severity.low,
                        clean_start=first.start(),
                        clean_end=first.end(),
                        explanation=(
                            f"{em} em dashes vs {commas} commas (dash-heavy: ratio "
                            f"{emdash_ratio:.2f})."
                        ),
                    )
                )

        score = 0.6 * emdash_signal + 0.4 * curly_signal
        return FeatureResult(dimension=self.dimension, score=min(1.0, score), spans=spans)


register(FormattingTells())
