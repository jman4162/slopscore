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
from slopscore.features.base import register, severity_rate_score
from slopscore.features.phrase_packs import PhrasePack
from slopscore.features.specificity import concrete_evidence_count
from slopscore.models import Dimension, Evidence, EvidenceKind, FeatureResult, Severity
from slopscore.spans import TextSpan

RULE_META_RUN = "META_RUN_OF_META_SENTENCES"

# Headings and list items are not prose; a bulleted "Key takeaways:" label is structure_tells'
# business, not a run of meta sentences. Same exclusion cadence.py uses.
_NOT_PROSE = frozenset({"heading", "list_item"})

# Runs shorter than this are ordinary signposting. A run of 2 is already unusual in edited prose;
# the reference catch was a run of 3.
_MIN_RUN = 2

# Below this length a "sentence" is a fragment ("In summary." / "To be clear.") and saying it
# carries no evidence is not informative.
_MIN_SENTENCE_WORDS = 6

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
    return [re.compile(m, re.IGNORECASE) for m in raw.get("markers", [])]


def _is_empty_meta(doc: Document, sentence: TextSpan) -> bool:
    """A metadiscourse sentence that carries no concrete reference of its own."""
    text = sentence.text.strip()
    if len(text.split()) < _MIN_SENTENCE_WORDS:
        return False
    if doc.in_block_kind(sentence.start, _NOT_PROSE):
        return False
    if concrete_evidence_count(text) > 0:
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


def _count_sentences(text: str) -> int:
    """Recover a run's sentence count from the span text itself.

    ``score_spans`` must be a pure function of the surviving spans — the scorer re-scores after
    suppression and severity overrides — so the run length cannot be cached on the feature.
    """
    return len([p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p])


class Metadiscourse(PhrasePack):
    """Phrase pack plus a length-invariant concentration term."""

    def rule_ids(self) -> frozenset[str]:
        return super().rule_ids() | {RULE_META_RUN}

    def score_spans(self, doc: Document, profile: str, spans: list[Evidence]) -> float:
        rule_spans = [s for s in spans if s.rule_id != RULE_META_RUN]
        run_spans = [s for s in spans if s.rule_id == RULE_META_RUN]
        rate = severity_rate_score(doc, rule_spans, self._full_scale)
        concentration = max((_run_score(_count_sentences(s.span)) for s in run_spans), default=0.0)
        return max(rate, concentration)

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
        spans = sorted(base.spans + self._run_spans(doc), key=lambda e: e.start_char)
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
