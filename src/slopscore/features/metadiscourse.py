"""Metadiscourse: writing that refers to the text itself rather than to its subject.

Two measurements, combined with ``max``:

* **rate** -- the shared severity-weighted hits-per-100-words used by every phrase pack.
* **concentration** -- the longest run of consecutive *evidence-free* metadiscourse sentences,
  scored independently of document length.

The concentration term exists because the rate term alone cannot see this defect in long-form
prose. The passage that prompted the dimension saturates ``formulaic_structure`` at 1.0 in a
123-word sample; the same constructions spread across a 3,373-word document score 0.064, because
``per_hundred_words`` divides them away. ``MODEL_CARD.md`` names the same effect on the Wikipedia
slice ("their tells are sparse and per-100-word rates dilute them").

The distinction the concentration term draws is the honest one: a lone "as noted above" in a long
essay is ordinary writing, while several sentences in a row that talk about the writing and carry
no fact are the defect, at any length. Requiring the run's sentences to be evidence-free is also
the fairness gate -- "In summary, Japan took 34 years to recover from 1989" is a real summary
sentence and is exempt, which is how ESL and simple-English writers use restatement scaffolding.

Hand-written rather than a plain phrase pack for the same reason ``formulaic_patterns.py`` is:
the score is not ``severity_rate_score`` alone. It subclasses ``PhrasePack`` so rule loading,
``rule_ids``, and the ``--broad`` re-score registration stay shared.
"""

from __future__ import annotations

from functools import lru_cache

import regex as re
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
from slopscore.features.specificity import concrete_evidence_count
from slopscore.models import Dimension, Evidence, EvidenceKind, FeatureResult, Severity
from slopscore.spans import TextSpan

RULE_META_RUN = "META_RUN_OF_META_SENTENCES"

# Headings and list items end a run rather than being passed over. They are structural
# boundaries: four sections each opening "In this section we will describe..." are four
# signposts, not one four-sentence run, and treating the headings between them as transparent
# produced a single high-severity finding on ordinary IMRaD and reference-doc structure -- and a
# span whose text visibly contained the numbers its own explanation said were absent.
_NOT_PROSE = frozenset({"heading", "list_item"})

# Runs shorter than this are ordinary signposting. A run of 2 is already unusual in edited prose;
# the reference catch was a run of 3.
_MIN_RUN = 2

# Below this length a "sentence" is a fragment ("In summary." / "To be clear.") and saying it
# carries no evidence is not informative.
_MIN_SENTENCE_WORDS = 6

# Rules whose construction is legitimate when it restates a FACT. A code gloss over "the bus
# costs two euros" is a comprehension aid, not prose about the prose, and it is how ESL and
# simple-English writers make a concrete point land; a code gloss over nothing is the tell.
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
# single low-severity marker there saturates the dimension at 1.0: measured on two clean
# benchmark rows that went 13.8 -> 50.2 on one hit each. Smoothing a rate estimated from a tiny
# sample is the same judgment abstention already encodes about short input, applied to the score
# rather than only to the label. No effect above 100 words.
#
# This is a local fix for a shared defect, and it is worth being honest about which. Every pack
# using severity_rate_score has it: significance_inflation, formulaic_structure,
# weasel_attribution, unsupported_claims and insight_signaling are all non-weak with no floor,
# and one medium hit in a 17-word document saturates each of them too. The right fix is a
# minimum-denominator argument on severity_rate_score itself, which moves every dimension's
# scores and needs its own calibration pass; it is not done here.
_MIN_RATE_WORDS = 100


def _run_score(length: int) -> float:
    return _RUN_SCORE.get(length, _RUN_SCORE_MAX if length >= 5 else 0.0)


@lru_cache(maxsize=1)
def _markers() -> list[re.Pattern[str]]:
    """The non-scoring marker superset used to classify a sentence as metadiscourse."""
    with data_path("lexicons", "metadiscourse_markers.yaml").open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    # Same module and flags _ruleset.py compiles the YAML rules with, so a marker copied from
    # patterns/*.yaml behaves identically here.
    return [re.compile(m, re.IGNORECASE | re.MULTILINE) for m in raw.get("markers", [])]


def _strip_markers(text: str) -> tuple[str, bool]:
    """``text`` with every marker's characters removed, and whether any matched.

    All of them, not just the first: a sentence stacking several markers ("As noted above, in
    plain English, three things stand out") kept the others' text behind and was scored concrete,
    so the densest metadiscourse sentence in a passage was the one that broke the run. The
    excision matters because markers can look concrete on their own -- "In plain English" contains
    "English", which the proper-noun heuristic reads as a name, and "three things" contains a
    number.
    """
    matched = False
    for pattern in _markers():
        stripped = pattern.sub(" ", text)
        if stripped != text:
            matched = True
            text = stripped
    return text, matched


def _classify(doc: Document, sentence: TextSpan) -> str:
    """``"meta"``, ``"skip"``, or ``"break"`` for one sentence.

    ``"skip"`` neither extends nor breaks a run: a sentence too short to judge says nothing about
    whether the passage around it is about the writing, and treating it as concrete used to sever
    a run, so a denser passage of prose-about-the-prose could score lower than a sparser one.
    Everything else -- a sentence carrying a fact, or any non-prose block -- is a ``"break"``.
    """
    text = sentence.text.strip()
    if doc.in_block_kind(sentence.start, _NOT_PROSE):
        return "break"
    rest, matched = _strip_markers(text)
    if not matched:
        if len(text.split()) < _MIN_SENTENCE_WORDS:
            return "skip" if concrete_evidence_count(text, spelled_numbers=True) == 0 else "break"
        return "break"
    if len(text.split()) < _MIN_SENTENCE_WORDS:
        return "skip"
    return "break" if concrete_evidence_count(rest, spelled_numbers=True) > 0 else "meta"


def _runs(doc: Document) -> list[list[TextSpan]]:
    """Maximal runs of consecutive evidence-free metadiscourse sentences, longest first.

    Cached on the document: ``extract`` and ``score_spans`` both need it, ``score_spans`` runs
    again whenever the scorer filters a span, and classification is ~30 regexes plus an evidence
    count per sentence. The cache is best-effort so that making ``Document`` slotted or frozen
    later degrades to recomputation rather than raising at scan time.
    """
    try:
        cached = doc.__dict__.get("_metadiscourse_runs")
        if cached is not None:
            return cached  # type: ignore[no-any-return]
    except AttributeError:  # pragma: no cover - only if Document gains __slots__
        pass

    runs: list[list[TextSpan]] = []
    current: list[TextSpan] = []
    for s in doc.sentences:
        if not s.text.strip():
            continue
        kind = _classify(doc, s)
        if kind == "skip":
            continue
        if kind == "meta":
            current.append(s)
            continue
        if len(current) >= _MIN_RUN:
            runs.append(current)
        current = []
    if len(current) >= _MIN_RUN:
        runs.append(current)
    runs.sort(key=len, reverse=True)

    try:
        doc.__dict__["_metadiscourse_runs"] = runs
    except AttributeError:  # pragma: no cover - only if Document gains __slots__
        pass
    return runs


def _sentence_ranges(doc: Document) -> list[tuple[int, int]]:
    """Original-coordinate range of every sentence, positionally aligned with ``doc.sentences``."""
    return [doc.mapper.to_original(s.start, s.end) for s in doc.sentences]


def _restates_a_fact(doc: Document, span: Evidence, ranges: list[tuple[int, int]]) -> bool:
    """True when the sentence around a marker carries a concrete reference of its own.

    Every marker's characters are cut out before counting, or a marker that looks concrete would
    exempt itself.
    """
    for start, end in ranges:
        if not start <= span.start_char < end:
            continue
        sentence = doc.original_text[start:end]
        rest, _ = _strip_markers(sentence)
        return concrete_evidence_count(rest, spelled_numbers=True) > 0
    return False


def _natural_severity(run_length: int) -> Severity:
    return Severity.high if run_length >= 4 else Severity.medium


def _severity_factor(span: Evidence, natural: Severity) -> float:
    """How far a ``rule_severity`` override moved this span from the severity it would have had.

    Without this the concentration term ignores severity overrides entirely, so
    ``rule_severity={"META_RUN_OF_META_SENTENCES": "low"}`` changed the report label and nothing
    else, against the scorer contract that overrides apply before ``by_dim``. Raising a severity
    scales up as well as down; the dimension score is clamped to [0, 1] by the caller.
    """
    return SEVERITY_WEIGHT[span.severity] / SEVERITY_WEIGHT[natural]


class Metadiscourse(PhrasePack):
    """Phrase pack plus a length-invariant concentration term."""

    def rule_ids(self) -> frozenset[str]:
        return super().rule_ids() | {RULE_META_RUN}

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        # The concentration term has its own span and must not also be charged to the rate term.
        rule_spans = [s for s in spans if s.rule_id != RULE_META_RUN]
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in rule_spans)
        rate = saturating(
            per_hundred_words(weighted, max(doc.word_count, _MIN_RATE_WORDS)), self._full_scale
        )

        # The run span anchors on its first sentence, so the length is recovered from the
        # document rather than from the span text. score_spans must stay a pure function of the
        # surviving spans, which this is: same doc, same spans, same answer.
        lengths = {
            doc.mapper.to_original(run[0].start, run[0].end)[0]: len(run) for run in _runs(doc)
        }
        concentration = 0.0
        for s in (s for s in spans if s.rule_id == RULE_META_RUN):
            n = lengths.get(s.start_char)
            if n is None:
                continue
            concentration = max(
                concentration, _run_score(n) * _severity_factor(s, _natural_severity(n))
            )

        return min(1.0, max(rate, concentration))

    def _run_spans(self, doc: Document) -> list[Evidence]:
        """One span per run, anchored on the run's FIRST sentence.

        Not the whole run: report/html.py picks the longest span at each offset and skips the
        ones inside it, so a multi-sentence finding swallowed every phrase-level highlight in the
        passage, from every dimension. A short anchor also keeps report/baseline.py fingerprints
        (``sha256(file | rule_id | span text)``) stable when an unrelated word later in the
        passage is edited, which ``--fail-on-new`` depends on.
        """
        spans: list[Evidence] = []
        for run in _runs(doc):
            n = len(run)
            spans.append(
                doc.evidence(
                    rule_id=RULE_META_RUN,
                    severity=_natural_severity(n),
                    clean_start=run[0].start,
                    clean_end=run[0].end,
                    explanation=(
                        f"Starts a run of {n} consecutive sentences about the writing rather "
                        "than the subject, none carrying a name, number, date, URL, or identifier."
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
        spans = sorted(kept + self._run_spans(doc), key=lambda e: e.start_char)
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
    # Quoted text is someone else's, or an example being discussed rather than used. Same reason
    # the candor and attribution packs skip it: a character may say "To be clear," and a style
    # guide may quote "As noted above" without either author being charged for it.
    skip_quoted=True,
)

register(MetadiscoursePack)
