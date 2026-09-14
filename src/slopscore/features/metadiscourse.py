"""Metadiscourse: writing that refers to the text itself rather than to its subject.

Two measurements, combined with ``max``:

* **rate**: the shared severity-weighted hits-per-100-words used by every phrase pack.
* **concentration**: the longest run of consecutive *evidence-free* metadiscourse sentences,
  scored independently of document length.

The concentration term exists because the rate term alone cannot see this defect in long-form
prose. The passage that prompted the dimension saturates ``formulaic_structure`` at 1.0 in a
123-word sample; the same constructions spread across a 3,373-word document score 0.064, because
``per_hundred_words`` divides them away. ``MODEL_CARD.md`` names the same effect on the Wikipedia
slice ("their tells are sparse and per-100-word rates dilute them").

A lone "as noted above" in a long essay is ordinary writing, while several sentences in a row
that talk about the writing and carry no fact are the defect, at any length. Requiring the run's
sentences to be evidence-free is also the fairness gate. "In summary, Japan took 34 years to
recover from 1989" is a real summary sentence and is exempt, which is how ESL and simple-English
writers use restatement scaffolding.

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
from slopscore.features._ruleset import compile_rule_pattern
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
# signposts, not one four-sentence run. Treating the headings between them as transparent
# produced a single high-severity finding on ordinary IMRaD and reference-doc structure, and a
# span whose text visibly contained the numbers its own explanation said were absent.
#
# This guard alone is NOT enough: Document.in_block_kind returns False whenever doc.blocks is
# empty, which is every non-Markdown source (plain text, stdin, extracted code comments, web
# articles). A paragraph break is the structural boundary that exists for all of them, so _runs
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

# LINE-STRUCTURED PARAGRAPHS NEVER FORM A RUN. A paragraph whose text contains a line break (a
# hard-wrapped plain-text file, a code comment, a web article extracted with single newlines
# between blocks) or an HTML comment contributes no sentence to a run, and a marker in it is
# judged against the evidence in the whole paragraph rather than in its own sentence.
#
# This is a conservative rule, not a guarantee. It stops wrapped fragments from being judged one
# at a time, which v0.14 review rounds 5 to 9 showed cannot be done without letting wrapping create
# findings. It does not make wrapped text score the same as flat, and it does not rule out every
# case where wrapping adds a finding. Known limits, from review round 10:
#
# * normalize/quotes.py does not pair quotes across a line break, so a wrap inside a quoted marker
#   phrase exposes a marker the flat text skips;
# * a paragraph carrying an HTML comment, including a suppression comment for an unrelated rule,
#   forms no run, and a fact anywhere in it exempts its evidence-gated markers;
# * text that separates paragraphs with single newlines (extracted web text, much pasted text) is
#   one paragraph to this rule, so it forms no run and one fact exempts the whole of it;
# * the whole-paragraph evidence check runs once per evidence-gated marker, so a long
#   single-newline document dense with markers scans slowly.
_HTML_COMMENT = re.compile(r"<!--[\s\S]*?-->")
_WHITESPACE = re.compile(r"\s+")

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

# Run length to dimension score. Deliberately length-invariant: this is the whole point of the
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
    # The same compile path _ruleset.py uses for the YAML rules (flags and {CLAUSE_START}
    # expansion). A marker whose scoring rule predates v0.14 ("in short,", "that said,") is
    # anchored with CLAUSE_START here and with that rule's own 0.13.0 anchor there, so the two can
    # disagree at a line start; see the comment on CLAUSE_START.
    return [compile_rule_pattern(m) for m in raw.get("markers", [])]


class _Layout:
    """Paragraph and sentence geometry for one document, computed once and cached on it."""

    __slots__ = (
        "para_clean_starts",
        "para_orig",
        "para_orig_starts",
        "sent_orig",
        "sent_starts",
        "structured",
    )

    def __init__(self, doc: Document) -> None:
        self.para_clean_starts = [p.start for p in doc.paragraphs]
        self.para_orig = [doc.mapper.to_original(p.start, p.end) for p in doc.paragraphs]
        self.para_orig_starts = [start for start, _ in self.para_orig]
        self.structured = ["\n" in p.text.strip() or "<!--" in p.text for p in doc.paragraphs]
        self.sent_orig = [
            doc.mapper.to_original(s.start, s.end) for s in doc.sentences if s.text.strip()
        ]
        self.sent_starts = [start for start, _ in self.sent_orig]

    def paragraph_of(self, clean_start: int) -> int:
        return bisect_right(self.para_clean_starts, clean_start) - 1

    def is_structured(self, clean_start: int) -> bool:
        i = self.paragraph_of(clean_start)
        return 0 <= i < len(self.structured) and self.structured[i]

    def evidence_range(self, orig_start: int) -> tuple[int, int, bool] | None:
        """The ``(start, end, whole_paragraph)`` span a marker at ``orig_start`` is judged by."""
        i = bisect_right(self.para_orig_starts, orig_start) - 1
        if (
            0 <= i < len(self.para_orig)
            and self.structured[i]
            and orig_start < self.para_orig[i][1]
        ):
            return self.para_orig[i][0], self.para_orig[i][1], True
        j = bisect_right(self.sent_starts, orig_start) - 1
        if 0 <= j < len(self.sent_orig) and orig_start < self.sent_orig[j][1]:
            return self.sent_orig[j][0], self.sent_orig[j][1], False
        return None


def _layout(doc: Document) -> _Layout:
    cached = doc.__dict__.get("_metadiscourse_layout")
    if isinstance(cached, _Layout):
        return cached
    layout = _Layout(doc)
    doc.__dict__["_metadiscourse_layout"] = layout
    return layout


def _strip_markers(text: str) -> tuple[str, list[tuple[int, int]]]:
    """``text`` with every marker's characters removed, plus where each marker matched.

    All of them, not just the first: a sentence stacking several markers ("As noted above, in
    plain English, three things stand out") kept the others' text behind and was scored concrete,
    so the densest metadiscourse sentence in a passage was the one that broke the run. The
    excision matters because markers can look concrete on their own. "In plain English" contains
    "English", which the proper-noun heuristic reads as a name, and "three things" contains a
    number.

    Each marker becomes ", " and the result is whitespace-collapsed, because ``_PROPER`` matches
    on ``(?<=[a-z,;:]\\s)``, exactly one space. Substituting a bare space hid a name that followed
    a comma-terminated marker ("In short, Tokyo remains the largest market" counted zero
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
    """``"meta"``, ``"skip"``, or ``"break"`` for one sentence of a paragraph with no line break.

    ``"skip"`` neither extends nor breaks a run. A short factless sentence says nothing about
    whether the passage around it is about the writing, and treating it as concrete used to sever
    a run, so a denser passage of prose-about-the-prose could score lower than a sparser one. It
    is the only neutral class. Everything else is a ``"break"``: a non-prose block, or a sentence
    carrying a fact at any length. The evidence test runs before the length test.
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
    if concrete_evidence_count(rest, spelled_numbers=True) > 0:
        return "break"
    return "skip" if len(text.split()) < _MIN_SENTENCE_WORDS else "meta"


def _no_marker(text: str) -> Kind:
    """A sentence with no marker: short and factless says nothing, anything else interrupts."""
    if len(text.split()) < _MIN_SENTENCE_WORDS:
        return "skip" if concrete_evidence_count(text, spelled_numbers=True) == 0 else "break"
    return "break"


def _runs(doc: Document) -> list[list[TextSpan]]:
    """Maximal runs of consecutive evidence-free metadiscourse sentences, longest first.

    Every sentence of a line-structured paragraph is a ``"break"`` (see the note on
    ``_HTML_COMMENT``). Cached on the document: ``extract``, ``score_spans`` and ``prune_spans``
    all need it, and classification is ~30 regexes plus an evidence count per sentence. A copy is
    returned so a caller cannot corrupt the cache.
    """
    cached = doc.__dict__.get("_metadiscourse_runs")
    if cached is not None:
        return [list(r) for r in cached]

    layout = _layout(doc)
    runs: list[list[TextSpan]] = []
    current: list[TextSpan] = []
    skips = 0
    para = -1
    for s in doc.sentences:
        if not s.text.strip():
            continue
        kind: Kind = "break" if layout.is_structured(s.start) else _classify(doc, s)
        if kind == "skip":
            # Tolerated inside a run, but only so many: past the budget the run is not
            # "consecutive" in any sense the explanation could honestly claim.
            if current and (skips := skips + 1) > _MAX_SKIPS_IN_RUN:
                if len(current) >= _MIN_RUN:
                    runs.append(current)
                current, skips = [], 0
            continue
        if kind == "meta":
            here = layout.paragraph_of(s.start)
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


def _restates_a_fact(doc: Document, span: Evidence) -> bool:
    """True when the text a marker is judged by carries a concrete reference of its own.

    That text is the marker's sentence, or its whole paragraph when the paragraph is
    line-structured. Every marker's characters are cut out before counting, or a marker that looks
    concrete would exempt itself. In a line-structured paragraph, comment text is removed (a rule
    id reads as an identifier) and whitespace is collapsed, which can only find more evidence.
    """
    found = _layout(doc).evidence_range(span.start_char)
    if found is None:
        return False
    start, end, whole_paragraph = found
    text = doc.original_text[start:end]
    if whole_paragraph:
        text = _WHITESPACE.sub(" ", _HTML_COMMENT.sub(" ", text)).strip()
    rest, _ = _strip_markers(text)
    return concrete_evidence_count(rest, spelled_numbers=True) > 0


def _natural_severity(run_length: int) -> Severity:
    return Severity.high if run_length >= 4 else Severity.medium


def _run_extents(doc: Document) -> dict[int, tuple[int, int, int]]:
    """``{original start: (run length, original start, original end)}`` for every run.

    Explicit max on collision, not a dict comprehension: ``_runs`` is sorted longest-first, so
    the comprehension's last write would keep the SHORTEST run at a shared start. Cached on the
    document, since ``prune_spans`` and ``score_spans`` both need it on every filtered scan.
    """
    cached = doc.__dict__.get("_metadiscourse_extents")
    if cached is not None:
        return dict(cached)
    extents: dict[int, tuple[int, int, int]] = {}
    for run in _runs(doc):
        start, _ = doc.mapper.to_original(run[0].start, run[0].end)
        _, end = doc.mapper.to_original(run[-1].start, run[-1].end)
        best = extents.get(start)
        if best is None or len(run) > best[0]:
            extents[start] = (len(run), start, end)
    doc.__dict__["_metadiscourse_extents"] = extents
    return dict(extents)


def _licensed(start: int, end: int, spans: list[Evidence]) -> bool:
    """Whether a run over ``[start, end)`` may score: a metadiscourse rule of our own sits in it.

    The marker lexicon is a superset of this dimension's rules, so a run can be built entirely
    from phrases whose scoring rule lives in formulaic_structure. Charging for those would bill
    one set of phrases to two weighted dimensions, which the pack design explicitly disclaims.
    The lexicon supplies the shape; only a rule of this dimension supplies the licence to score.
    This is the ONE predicate behind ``extract``, ``score_spans`` and ``prune_spans``. It was
    once two, and they drifted.
    """
    return any(r.rule_id != RULE_META_RUN and start <= r.start_char < end for r in spans)


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

        extents = _run_extents(doc)
        concentration = 0.0
        for s in (s for s in spans if s.rule_id == RULE_META_RUN):
            extent = extents.get(s.start_char)
            if extent is None or not _licensed(extent[1], extent[2], spans):
                continue
            n = extent[0]
            concentration = max(
                concentration, _run_score(n) * _severity_factor(s, _natural_severity(n))
            )

        return min(1.0, max(rate, concentration))

    def prune_spans(self, doc: Document, spans: list[Evidence]) -> list[Evidence]:
        """Drop a run finding whose licensing rule the scorer has just filtered out.

        ``extract`` only emits a run that ``_licensed`` approves, but the scorer applies
        ``disabled_rules`` and inline suppressions AFTER that, by rule id. Disable or suppress the
        one ``META_`` rule inside a run and the run span survived on its own: a medium- or
        high-severity finding in the report, ``metadiscourse == 0.0``, and ``--fail-on medium``
        exiting non-zero for a rule the user had turned off.
        """
        extents = _run_extents(doc)
        kept: list[Evidence] = []
        for s in spans:
            if s.rule_id == RULE_META_RUN:
                extent = extents.get(s.start_char)
                if extent is None or not _licensed(extent[1], extent[2], spans):
                    continue
            kept.append(s)
        return kept

    def _run_spans(self, doc: Document, rule_spans: list[Evidence]) -> list[Evidence]:
        """One span per licensed run, anchored on the run's FIRST sentence.

        Not the whole run: report/html.py picks the longest span at each offset and skips the
        ones inside it, so a multi-sentence finding swallowed every phrase-level highlight in the
        passage. A short anchor also keeps report/baseline.py fingerprints (``sha256(file |
        rule_id | span text)``) stable when an unrelated word later in the passage is edited,
        which ``--fail-on-new`` depends on.

        Only a run ``_licensed`` approves is emitted. Emitting one the scorer then declines to
        charge left a medium- or high-severity finding in the report with ``metadiscourse ==
        0.0``, which still tripped ``--fail-on``. ``prune_spans`` applies the same predicate
        again after the scorer's own filtering, for the same reason.
        """
        spans: list[Evidence] = []
        for run in _runs(doc):
            start, _ = doc.mapper.to_original(run[0].start, run[0].end)
            _, end = doc.mapper.to_original(run[-1].start, run[-1].end)
            if not _licensed(start, end, rule_spans):
                continue
            n = len(run)
            spans.append(
                doc.evidence(
                    rule_id=RULE_META_RUN,
                    severity=_natural_severity(n),
                    clean_start=run[0].start,
                    clean_end=run[0].end,
                    explanation=(
                        f"Starts a run of {n} consecutive sentences about the writing rather "
                        "than the subject, none carrying a name, number, date, URL, or "
                        "identifier of their own."
                    ),
                    kind=EvidenceKind.finding,
                )
            )
        return spans

    def extract(self, doc: Document, profile: str, broad: bool = False) -> FeatureResult:
        base = super().extract(doc, profile, broad=broad)
        # A marker inside an HTML comment is a note to a tool or a reader, not the author's prose.
        comments = [(m.start(), m.end()) for m in _HTML_COMMENT.finditer(doc.original_text)]
        kept = [
            s
            for s in base.spans
            if not any(a <= s.start_char < b for a, b in comments)
            and (s.rule_id not in _EVIDENCE_EXEMPT or not _restates_a_fact(doc, s))
        ]
        spans = sorted(kept + self._run_spans(doc, kept), key=lambda e: e.start_char)
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
