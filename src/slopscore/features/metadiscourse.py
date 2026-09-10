"""Metadiscourse: writing that refers to the text itself rather than to its subject.

Two measurements, combined with ``max``:

* **rate** — the shared severity-weighted hits-per-100-words used by every phrase pack.
* **concentration** — the longest run of consecutive *evidence-free* metadiscourse sentences,
  scored independently of document length.

The concentration term exists because the rate term alone cannot see this defect in long-form
prose. The passage that prompted the dimension saturates ``formulaic_structure`` at 1.0 in a
123-word sample; the same constructions spread across a 3,373-word document score 0.064, because
``per_hundred_words`` divides them away. ``MODEL_CARD.md`` names the same effect on the Wikipedia
slice ("their tells are sparse and per-100-word rates dilute them").

The distinction the concentration term draws is the honest one: a lone "as noted above" in a long
essay is ordinary writing, while three sentences in a row that talk about the writing and carry no
fact are the defect, at any length. Requiring the run's sentences to be evidence-free is also the
fairness gate — "In summary, Japan took 34 years to recover from 1989" is a real summary sentence
and is exempt, which is how ESL and simple-English writers use restatement scaffolding.

Hand-written rather than a plain phrase pack for the same reason ``formulaic_patterns.py`` is:
the score is not ``severity_rate_score`` alone. It subclasses ``PhrasePack`` so rule loading,
``rule_ids``, and the ``--broad`` re-score registration stay shared.
"""

from __future__ import annotations

import re
from functools import lru_cache

import yaml

from slopscore.config import data_path
from slopscore.document import Document
from slopscore.features.base import (
    SEVERITY_WEIGHT,
    per_hundred_words,
    register,
    saturating,
)
from slopscore.features.phrase_packs import PhrasePack
from slopscore.features.redundancy import pair_cosine
from slopscore.features.specificity import concrete_evidence_count
from slopscore.models import Dimension, Evidence, EvidenceKind, FeatureResult, Severity
from slopscore.spans import TextSpan

RULE_META_RUN = "META_RUN_OF_META_SENTENCES"
RULE_TERMINAL_RECAP = "META_TERMINAL_RECAP"

# Headings and list items are not prose; a bulleted "Key takeaways:" label is structure_tells'
# business, not a run of meta sentences. Same exclusion cadence.py uses.
_NOT_PROSE = frozenset({"heading", "list_item"})

# Runs shorter than this are ordinary signposting. A run of 2 is already unusual in edited prose;
# the reference catch was a run of 3.
_MIN_RUN = 2

# Below this length a "sentence" is a fragment ("In summary." / "To be clear.") and saying it
# carries no evidence is not informative.
_MIN_SENTENCE_WORDS = 6

# Rules whose construction is legitimate when it restates a FACT. A code gloss over "the bus
# costs two euros" is a comprehension aid, not prose about the prose, and it is how ESL and
# simple-English writers make a concrete point land; a code gloss over nothing is the tell. Same
# predicate the run detector uses, applied per span.
#
# Deliberately NOT gated: the prose-grading and frame-marker rules. "The defensible version is"
# and "In this section we will discuss" announce the writing whatever facts sit beside them.
_EVIDENCE_EXEMPT = frozenset(
    {
        "META_RESTATEMENT_COLON",
        "META_PLAIN_ENGLISH",
        "META_CLARIFY_FRAME",
        "META_ENDOPHORIC_BACKREF",
        "META_BROAD_CODE_GLOSS",
        "META_BROAD_BARE_RESTATEMENT",
    }
)

# Run length -> dimension score. Deliberately length-invariant: this is the whole point of the
# term. Capped below 1.0 so a run alone never saturates the dimension.
_RUN_SCORE: dict[int, float] = {2: 0.35, 3: 0.55, 4: 0.75}
_RUN_SCORE_MAX = 0.90

# Floor on the density denominator. per_hundred_words amplifies a 17-word document 5.9x, so a
# single low-severity marker there saturates the dimension at 1.0 — measured on two clean
# benchmark rows that went 13.8 -> 50.2 on one hit each. The other packs survive this because
# they are weak-damped; this one deliberately is not, so it needs the floor instead. Smoothing a
# rate estimated from a tiny sample toward zero is the same judgment abstention already encodes
# about short input, applied to the score rather than only to the label. No effect above 100
# words, which is where every real document lives.
_MIN_RATE_WORDS = 100


def _run_score(length: int) -> float:
    return _RUN_SCORE.get(length, _RUN_SCORE_MAX if length >= 5 else 0.0)


@lru_cache(maxsize=1)
def _markers() -> list[re.Pattern[str]]:
    """The non-scoring marker superset used to classify a sentence as metadiscourse."""
    with data_path("lexicons", "metadiscourse_markers.yaml").open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return [re.compile(m, re.IGNORECASE) for m in raw.get("markers", [])]


def _is_empty_meta(doc: Document, sentence: TextSpan) -> bool:
    """A metadiscourse sentence that carries no concrete reference of its own."""
    text = sentence.text.strip()
    if len(text.split()) < _MIN_SENTENCE_WORDS:
        return False
    if doc.in_block_kind(sentence.start, _NOT_PROSE):
        return False
    if concrete_evidence_count(text, spelled_numbers=True) > 0:
        return False
    return any(m.search(text) for m in _markers())


def _runs(doc: Document) -> list[list[TextSpan]]:
    """Maximal runs of consecutive evidence-free metadiscourse sentences, longest first."""
    runs: list[list[TextSpan]] = []
    current: list[TextSpan] = []
    for s in doc.sentences:
        if not s.text.strip():
            continue
        if _is_empty_meta(doc, s):
            current.append(s)
            continue
        if len(current) >= _MIN_RUN:
            runs.append(current)
        current = []
    if len(current) >= _MIN_RUN:
        runs.append(current)
    return sorted(runs, key=len, reverse=True)


# A closing section has to be announced as one; a final paragraph that simply continues the
# argument is not a recap however much vocabulary it shares with the body.
_CLOSER = re.compile(
    r"^\W{0,4}(?:\*\*)?(?:in summary|in conclusion|to sum up|to summari[sz]e|all in all|"
    r"in a nutshell|overall|to recap|key takeaways?|takeaways?|the bottom line|conclusion)\b",
    re.IGNORECASE,
)

# Below this the "body" is too short for shared vocabulary to mean anything.
_MIN_BODY_WORDS = 150

# Cosine over content unigrams and bigrams. A genuine restatement of the body lands near 0.75; a
# closing paragraph that adds something new lands near 0.
_RECAP_LO = 0.35
_RECAP_HI = 0.75


def _recap_score(cosine: float) -> float:
    if cosine < _RECAP_LO:
        return 0.0
    ramp = min(1.0, (cosine - _RECAP_LO) / (_RECAP_HI - _RECAP_LO))
    return 0.30 + 0.40 * ramp


def _terminal_split(doc: Document) -> tuple[TextSpan, str] | None:
    """The final paragraph and the body preceding it, when the final one announces a summary."""
    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    if len(paragraphs) < 2:
        return None
    last = paragraphs[-1]
    if not _CLOSER.match(last.text.strip()):
        return None
    body = doc.cleaned_text[: last.start]
    if len(body.split()) < _MIN_BODY_WORDS:
        return None
    return last, body


def _sentence_ranges(doc: Document) -> list[tuple[int, int]]:
    """Original-coordinate ranges of every non-empty sentence."""
    return [doc.mapper.to_original(s.start, s.end) for s in doc.sentences if s.text.strip()]


def _restates_a_fact(doc: Document, span: Evidence, ranges: list[tuple[int, int]]) -> bool:
    """True when the sentence around a marker carries a concrete reference of its own.

    The marker's own characters are cut out before counting, or a marker that looks concrete
    would exempt itself: "In plain English" contains "English", which the proper-noun heuristic
    reads as a name.
    """
    for start, end in ranges:
        if not start <= span.start_char < end:
            continue
        rest = (
            doc.original_text[start : span.start_char]
            + " "
            + doc.original_text[span.end_char : end]
        )
        return concrete_evidence_count(rest, spelled_numbers=True) > 0
    return False


def _count_sentences(text: str) -> int:
    """Recover a run's sentence count from the span text itself.

    ``score_spans`` must be a pure function of the surviving spans — the scorer re-scores after
    suppression and severity overrides — so the run length cannot be cached on the feature.
    """
    return len([p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p])


class Metadiscourse(PhrasePack):
    """Phrase pack plus a length-invariant concentration term."""

    def rule_ids(self) -> frozenset[str]:
        return super().rule_ids() | {RULE_META_RUN, RULE_TERMINAL_RECAP}

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        rule_spans = [s for s in spans if s.rule_id != RULE_META_RUN]
        run_spans = [s for s in spans if s.rule_id == RULE_META_RUN]
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in rule_spans)
        rate = saturating(
            per_hundred_words(weighted, max(doc.word_count, _MIN_RATE_WORDS)), self._full_scale
        )
        concentration = max((_run_score(_count_sentences(s.span)) for s in run_spans), default=0.0)
        recap = 0.0
        if any(s.rule_id == RULE_TERMINAL_RECAP for s in spans):
            split = _terminal_split(doc)
            if split is not None:
                last, body = split
                recap = _recap_score(pair_cosine(last.text, body))
        return max(rate, concentration, recap)

    def _recap_span(self, doc: Document) -> list[Evidence]:
        """A closing section that restates the body instead of adding to it.

        The spec's own report mock-up lists "Conclusion: formulaic summary without new
        information" as a finding. Length-invariant for the same reason the run term is: one
        recap paragraph is one hit, and a per-100-word rate would erase it in long-form.
        """
        split = _terminal_split(doc)
        if split is None:
            return []
        last, body = split
        cosine = pair_cosine(last.text, body)
        if _recap_score(cosine) == 0.0:
            return []
        return [
            doc.evidence(
                rule_id=RULE_TERMINAL_RECAP,
                severity=Severity.medium,
                clean_start=last.start,
                clean_end=last.end,
                explanation=(
                    f"Closing section restates the body ({cosine:.0%} content overlap) "
                    "rather than adding to it."
                ),
                kind=EvidenceKind.finding,
            )
        ]

    def _run_spans(self, doc: Document) -> list[Evidence]:
        spans: list[Evidence] = []
        for run in _runs(doc):
            n = len(run)
            spans.append(
                doc.evidence(
                    rule_id=RULE_META_RUN,
                    severity=Severity.high if n >= 4 else Severity.medium,
                    clean_start=run[0].start,
                    clean_end=run[-1].end,
                    explanation=(
                        f"{n} consecutive sentences about the writing rather than the subject, "
                        "none carrying a name, number, date, URL, or identifier."
                    ),
                    kind=EvidenceKind.finding,
                )
            )
        return spans

    def extract(self, doc: Document, profile: str, broad: bool = False) -> FeatureResult:
        base = super().extract(doc, profile, broad=broad)
        ranges = _sentence_ranges(doc)
        kept = [
            s
            for s in base.spans
            if s.rule_id not in _EVIDENCE_EXEMPT or not _restates_a_fact(doc, s, ranges)
        ]
        extra = self._run_spans(doc) + self._recap_span(doc)
        spans = sorted(kept + extra, key=lambda e: e.start_char)
        return FeatureResult(
            dimension=self.dimension,
            score=self.score_spans(doc, profile, spans),
            spans=spans,
        )


MetadiscoursePack = Metadiscourse(
    Dimension.metadiscourse,
    "metadiscourse",
    full_scale=4.0,
    broad_category="metadiscourse_broad",
)

register(MetadiscoursePack)
