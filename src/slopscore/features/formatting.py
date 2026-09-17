"""Formatting tells: dash density and curly-quote ratio (WP:AIDASH, WP:AICURLY).

These are WEAK ALONE: em dashes and curly quotes appear in professionally edited human prose
(Chicago style, Word smart quotes), so this dimension is low-weighted and corroboration-gated in
the scorer.

Density metric: a dash-to-COMMA ratio (dashes / (dashes + commas)), not per-paragraph or
per-100-words. The ratio measures the actual tell (reaching for a dash where a comma would do) and
is invariant to both document length and paragraph structure. Per-100-words is a reasonable
length-normalized alternative; per-paragraph is avoided because the pipeline rejoins/normalizes
paragraphs (markdown extraction, code-prose concatenation) and short or single-paragraph inputs
make that denominator degenerate.

Dashes typed in ASCII count too. A model writing into a terminal, a commit message, or a code
comment types ``--`` where a chat model writes an em dash, and swapping one for the other is a
known way to strip the tell. Two forms count: two or three hyphens with a single space on each side
between words ("the model -- which was new -- failed"), and two or three hyphens between two
lowercase letters ("the plan--simple--worked"). The lowercase guard is deliberate: in the committed
long-form corpus, three of the four unspaced human uses were names and titles ("Wenner--Gren",
"Eulalie--A Song"), not dashes. CLI flags, ``<!--`` and ``-->``, rule lines, numeric ranges and
decrements match neither form. A spaced single hyphen is not counted, because human text uses it as
a separator far more often than as a dash.

Quotes are counted on ``doc.original_text``, not ``cleaned_text``: the normalizer runs ftfy, whose
default ``uncurl_quotes`` straightens every curly quote before features see the text, which left
the curly branch of this feature permanently at zero. The summary span for that branch is built in
original coordinates directly (no clean-to-original mapping is needed).

When a signal fires, one summary span is emitted per branch (FORMATTING_EM_DASH and
FORMATTING_CURLY_QUOTES, each with the count and ratio in its explanation) so the score is
traceable; we do not flag every
dash, which would be noise. The dash span anchors on the first Unicode dash, and on the first ASCII
dash only when there is none, so ``report/baseline.py`` fingerprints (file, rule id, span text) do
not change for a document that fired before ASCII dashes counted. The score is a function of which
summary spans survive filtering, so suppressing one branch removes its points.
"""

from __future__ import annotations

import regex as re

from slopscore.document import Document
from slopscore.features.base import register
from slopscore.models import Dimension, Evidence, FeatureResult, Severity

_EM_DASH = re.compile("[—–]")  # em dash, en dash
# Two or three hyphens used as a dash: spaced between words, or unspaced between lowercase letters.
# The lookarounds keep the spaces out of the match, so the evidence span is the hyphens alone.
_ASCII_DASH = re.compile(
    r"""(?<=[\w)\]"'’”] )-{2,3}(?= [\w(\["'‘“])"""
    r"""|(?<=\p{Ll})-{2,3}(?=\p{Ll})"""
)
_COMMA = re.compile(r",")
_CURLY = re.compile("[“”‘’]")  # curly double/single quotes
_STRAIGHT = re.compile(r"[\"']")

# A dash-to-comma ratio at/above this looks dash-heavy in the LLM way.
_EMDASH_RATIO_FULL = 0.25

RULE_EM_DASH = "FORMATTING_EM_DASH"
RULE_CURLY = "FORMATTING_CURLY_QUOTES"


class FormattingTells:
    dimension = Dimension.formatting_tells

    def rule_ids(self) -> frozenset[str]:
        return frozenset({RULE_EM_DASH, RULE_CURLY})

    @staticmethod
    def _signals(doc: Document) -> tuple[float, float, int, int, int, int, int]:
        text = doc.cleaned_text
        ascii_dashes = len(_ASCII_DASH.findall(text))
        em = len(_EM_DASH.findall(text)) + ascii_dashes
        commas = len(_COMMA.findall(text))
        curly = len(_CURLY.findall(doc.original_text))
        straight = len(_STRAIGHT.findall(doc.original_text))
        emdash_ratio = em / (em + commas) if (em + commas) else 0.0
        curly_ratio = curly / (curly + straight) if (curly + straight) else 0.0
        # Need at least a couple of instances before either ratio means anything.
        emdash_signal = min(1.0, emdash_ratio / _EMDASH_RATIO_FULL) if em >= 2 else 0.0
        curly_signal = curly_ratio if curly >= 2 else 0.0
        return emdash_signal, curly_signal, em, ascii_dashes, commas, curly, straight

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        emdash_signal, curly_signal, *_ = self._signals(doc)
        present = {e.rule_id for e in spans}
        score = 0.0
        if RULE_EM_DASH in present:
            score += 0.6 * emdash_signal
        if RULE_CURLY in present:
            score += 0.4 * curly_signal
        return min(1.0, score)

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        emdash_signal, curly_signal, em, ascii_dashes, commas, curly, straight = self._signals(doc)
        spans: list[Evidence] = []
        if emdash_signal > 0:
            first = _EM_DASH.search(doc.cleaned_text) or _ASCII_DASH.search(doc.cleaned_text)
            if first is not None:
                if ascii_dashes:
                    counted = f'{em} dashes ({ascii_dashes} typed as "--")'
                else:
                    counted = f"{em} em dashes"
                spans.append(
                    doc.evidence(
                        rule_id=RULE_EM_DASH,
                        severity=Severity.low,
                        clean_start=first.start(),
                        clean_end=first.end(),
                        explanation=(
                            f"{counted} vs {commas} commas (dash-heavy: ratio "
                            f"{emdash_ratio_text(em, commas)})."
                        ),
                    )
                )
        if curly_signal > 0:
            first_curly = _CURLY.search(doc.original_text)
            if first_curly is not None:
                spans.append(
                    Evidence(
                        rule_id=RULE_CURLY,
                        severity=Severity.low,
                        span=doc.original_text[first_curly.start() : first_curly.end()],
                        start_char=first_curly.start(),
                        end_char=first_curly.end(),
                        explanation=(
                            f"{curly} curly vs {straight} straight quotes (word-processor "
                            f"smart quotes: ratio {curly_signal:.2f})."
                        ),
                    )
                )
        return FeatureResult(
            dimension=self.dimension, score=self.score_spans(doc, profile, spans), spans=spans
        )


def emdash_ratio_text(em: int, commas: int) -> str:
    return f"{em / (em + commas):.2f}" if (em + commas) else "0.00"


register(FormattingTells())
