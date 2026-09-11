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

from bisect import bisect_right
from functools import lru_cache
from typing import Literal

import regex as re
import yaml

from slopscore.config import data_path
from slopscore.document import Document
from slopscore.features.base import (
    MIN_RATE_WORDS,
    SEVERITY_WEIGHT,
    register,
    severity_rate_score,
)
from slopscore.features.phrase_packs import PhrasePack
from slopscore.features.specificity import concrete_evidence_count
from slopscore.models import Dimension, Evidence, EvidenceKind, FeatureResult, Severity
from slopscore.spans import TextSpan

Kind = Literal["meta", "skip", "break"]

RULE_META_RUN = "META_RUN_OF_META_SENTENCES"

# Headings and list items end a run rather than being passed over. They are structural
# boundaries: four sections each opening "In this section we will describe..." are four
# signposts, not one four-sentence run, and treating the headings between them as transparent
# produced a single high-severity finding on ordinary IMRaD and reference-doc structure -- and a
# span whose text visibly contained the numbers its own explanation said were absent.
#
# This guard alone is NOT enough: Document.in_block_kind returns False whenever doc.blocks is
# empty, which is every non-Markdown source -- plain text, stdin, extracted code comments, web
# articles. A paragraph break is the structural boundary that exists for all of them, so _runs
# also ends a run whenever the paragraph index changes.
_NOT_PROSE = frozenset({"heading", "list_item"})

# Runs shorter than this are ordinary signposting. A run of 2 is already unusual in edited prose;
# the reference catch was a run of 3.
_MIN_RUN = 2

# Below this length a "sentence" is a fragment ("In summary." / "To be clear.") and saying it
# carries no evidence is not informative.
_MIN_SENTENCE_WORDS = 6

# How many un-judgeable sentences may sit inside a run before it stops being "consecutive".
# Unbounded, any stretch of short factless prose (dialogue, verse, clipped narration) silently
# bridged two distant markers into a run the evidence then described as consecutive.
_MAX_SKIPS_IN_RUN = 1

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


def _strip_markers(text: str) -> tuple[str, list[tuple[int, int]]]:
    """``text`` with every marker's characters removed, plus where each marker matched.

    All of them, not just the first: a sentence stacking several markers ("As noted above, in
    plain English, three things stand out") kept the others' text behind and was scored concrete,
    so the densest metadiscourse sentence in a passage was the one that broke the run. The
    excision matters because markers can look concrete on their own -- "In plain English" contains
    "English", which the proper-noun heuristic reads as a name, and "three things" contains a
    number.

    Each marker becomes ", " and the result is whitespace-collapsed, because ``_PROPER`` matches
    on ``(?<=[a-z,;:]\\s)`` -- exactly one space. Substituting a bare space hid a name that
    followed a comma-terminated marker ("In short, Tokyo remains the largest market" counted zero
    evidence), and substituting ", " without collapsing left two spaces and hid it just the same.
    """
    spans: list[tuple[int, int]] = []
    matched: list[re.Pattern[str]] = []
    for pattern in _markers():
        hits = [(m.start(), m.end()) for m in pattern.finditer(text)]
        if hits:
            spans.extend(hits)
            matched.append(pattern)
    if not spans:
        return text, []
    stripped = text
    for pattern in matched:
        stripped = pattern.sub(", ", stripped)
    return re.sub(r"\s+", " ", stripped).strip(), spans


def _classify(doc: Document, sentence: TextSpan) -> Kind:
    """``"meta"``, ``"skip"``, or ``"break"`` for one sentence.

    ``"skip"`` neither extends nor breaks a run: a sentence too short to judge says nothing about
    whether the passage around it is about the writing, and treating it as concrete used to sever
    a run, so a denser passage of prose-about-the-prose could score lower than a sparser one.
    Everything else -- a sentence carrying a fact, or any non-prose block -- is a ``"break"``.
    """
    from slopscore.normalize.quotes import inside_quotes

    text = sentence.text.strip()
    if doc.in_block_kind(sentence.start, _NOT_PROSE):
        return "break"
    rest, marker_spans = _strip_markers(text)
    # The pack sets skip_quoted=True and the run term has to honor it. Test each marker's own
    # offsets, not the sentence's: pysbd keeps 'He said "In this section we will..."' as ONE
    # sentence, which contains the quotation rather than sitting inside it.
    offset = sentence.start + (len(sentence.text) - len(sentence.text.lstrip()))
    unquoted = [
        (a, b) for a, b in marker_spans if not inside_quotes(doc.quoted, offset + a, offset + b)
    ]
    if not unquoted:
        # Judge it as if the marker were not there: a short quotation dropped into a genuine run
        # should not sever it, which is what "skip" exists to prevent.
        return _no_marker(text)
    if len(text.split()) < _MIN_SENTENCE_WORDS:
        return "skip"
    return "break" if concrete_evidence_count(rest, spelled_numbers=True) > 0 else "meta"


def _no_marker(text: str) -> Kind:
    """A sentence with no marker: short and factless says nothing, anything else interrupts."""
    if len(text.split()) < _MIN_SENTENCE_WORDS:
        return "skip" if concrete_evidence_count(text, spelled_numbers=True) == 0 else "break"
    return "break"


def _runs(doc: Document) -> list[list[TextSpan]]:
    """Maximal runs of consecutive evidence-free metadiscourse sentences, longest first.

    Cached on the document: ``extract`` and ``score_spans`` both need it, ``score_spans`` runs
    again whenever the scorer filters a span, and classification is ~30 regexes plus an evidence
    count per sentence. A copy is returned so a caller cannot corrupt the cache.
    """
    cached = doc.__dict__.get("_metadiscourse_runs")
    if cached is not None:
        return [list(r) for r in cached]

    para_starts = [p.start for p in doc.paragraphs]

    def paragraph_of(sentence: TextSpan) -> int:
        return bisect_right(para_starts, sentence.start) - 1 if para_starts else 0

    runs: list[list[TextSpan]] = []
    current: list[TextSpan] = []
    skips = 0
    para = -1
    for s in doc.sentences:
        if not s.text.strip():
            continue
        kind = _classify(doc, s)
        if kind == "skip":
            # Tolerated inside a run, but only so many: past the budget the run is not
            # "consecutive" in any sense the explanation could honestly claim.
            if current and (skips := skips + 1) > _MAX_SKIPS_IN_RUN:
                if len(current) >= _MIN_RUN:
                    runs.append(current)
                current, skips = [], 0
            continue
        if kind == "meta":
            here = paragraph_of(s)
            if current and here != para:
                # A paragraph break is a structural boundary on every source type, Markdown or
                # not. Without this, three signposts in three separate paragraphs of plain text
                # read as one "run of 3 consecutive sentences".
                if len(current) >= _MIN_RUN:
                    runs.append(current)
                current, skips = [], 0
            current.append(s)
            para = here
            continue
        if len(current) >= _MIN_RUN:
            runs.append(current)
        current, skips = [], 0
    if len(current) >= _MIN_RUN:
        runs.append(current)
    runs.sort(key=len, reverse=True)

    doc.__dict__["_metadiscourse_runs"] = runs
    return [list(r) for r in runs]


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
    return float(SEVERITY_WEIGHT[span.severity] / SEVERITY_WEIGHT[natural])


class Metadiscourse(PhrasePack):
    """Phrase pack plus a length-invariant concentration term."""

    def rule_ids(self) -> frozenset[str]:
        return super().rule_ids() | {RULE_META_RUN}

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        # The concentration term has its own span and must not also be charged to the rate term.
        rule_spans = [s for s in spans if s.rule_id != RULE_META_RUN]
        rate = severity_rate_score(doc, rule_spans, self._full_scale, MIN_RATE_WORDS)

        # Explicit max(), not a dict comprehension: _runs is sorted longest-first, so on any key
        # collision the comprehension's last write would keep the SHORTEST run.
        extents: dict[int, tuple[int, int, int]] = {}
        for run in _runs(doc):
            start, _ = doc.mapper.to_original(run[0].start, run[0].end)
            _, end = doc.mapper.to_original(run[-1].start, run[-1].end)
            best = extents.get(start)
            if best is None or len(run) > best[0]:
                extents[start] = (len(run), start, end)

        concentration = 0.0
        for s in (s for s in spans if s.rule_id == RULE_META_RUN):
            extent = extents.get(s.start_char)
            if extent is None:
                continue
            n, run_start, run_end = extent
            # The marker lexicon is a superset of this dimension's rules, so a run can be built
            # entirely from phrases whose scoring rule lives in formulaic_structure. Charging for
            # those would bill one set of phrases to two weighted dimensions, which the pack
            # design explicitly disclaims. Require at least one metadiscourse rule of our own
            # inside the run; the lexicon still supplies the shape, just not the licence to score.
            if not any(
                r.rule_id != RULE_META_RUN and run_start <= r.start_char < run_end for r in spans
            ):
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
