"""Formatting tells: em-dash density and curly-quote ratio (WP:AIDASH, WP:AICURLY).

These are WEAK ALONE — em dashes and curly quotes appear in professionally edited human prose
(Chicago style, Word smart quotes). The guide is explicit that they only matter in combination,
so this dimension is low-weighted and corroboration-gated in the scorer. No spans (the signal is
distributional, and highlighting every dash would be noise).
"""

from __future__ import annotations

import regex as re

from slopscore.document import Document
from slopscore.features.base import register
from slopscore.models import Dimension, FeatureResult

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

        score = 0.6 * emdash_signal + 0.4 * curly_signal
        return FeatureResult(dimension=self.dimension, score=min(1.0, score), spans=[])


register(FormattingTells())
