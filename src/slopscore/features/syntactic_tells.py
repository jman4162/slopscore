"""Syntactic tells from WP:AISIGNS: superficial '-ing' analyses, negative parallelism /
rule-of-three, and copula avoidance.

All three have a regex default. ``superficial_analysis`` additionally upgrades to a spaCy
dependency-parse path when the ``[nlp]`` extra is installed, which cuts its false-positive rate
sharply (Reinhart et al. 2025 measure these clauses at ~5.3x human frequency, but the regex
approximation also fires on ordinary participles). parallelism and copula stay regex in v0.2.
"""

from __future__ import annotations

from functools import lru_cache

import regex as re

from slopscore.document import Document
from slopscore.features._nlp import is_nlp_available, parse
from slopscore.features._ruleset import (
    SEVERITY_WEIGHT,
    Rule,
    find_matches,
    load_rules_from_directory,
)
from slopscore.features.base import per_hundred_words, register, saturating
from slopscore.models import Dimension, Evidence, FeatureResult, Severity

# --- superficial analysis ('-ing' adjunct clauses) -------------------------------------------

# Present participles that head an LLM "superficial analysis" tail clause.
_ANALYSIS_VERBS = frozenset(
    """highlighting reflecting underscoring emphasizing demonstrating showcasing contributing
    ensuring fostering symbolizing embodying cementing solidifying shaping cultivating
    reinforcing illustrating signaling signalling affirming enhancing offering creating
    marking representing positioning""".split()
)
# Vague nouns that, combined with any trailing participle, mark the clause as superficial.
_VAGUE_NOUNS = frozenset(
    """significance importance impact role legacy identity heritage nature sense spirit future
    landscape development growth community culture values relevance prominence resilience
    journey potential connection commitment dedication""".split()
)

_PARTICIPLE_CLAUSE = re.compile(r",\s+([A-Za-z]+ing)\b([^.?!]{0,100})[.?!]")


def _is_superficial(lead: str, clause: str) -> bool:
    lead = lead.lower()
    if lead in _ANALYSIS_VERBS:
        return True
    words = set(re.findall(r"[a-z]+", clause.lower()))
    return bool(words & _VAGUE_NOUNS)


class SuperficialAnalysis:
    dimension = Dimension.superficial_analysis
    _full_scale = 2.0

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = self._nlp_spans(doc) if is_nlp_available() else self._regex_spans(doc)
        rate = per_hundred_words(len(spans), doc.word_count)
        return FeatureResult(
            dimension=self.dimension, score=saturating(rate, self._full_scale), spans=spans
        )

    def _regex_spans(self, doc: Document) -> list[Evidence]:
        spans: list[Evidence] = []
        for m in _PARTICIPLE_CLAUSE.finditer(doc.cleaned_text):
            if _is_superficial(m.group(1), m.group(2)):
                spans.append(
                    doc.evidence(
                        rule_id="SUPERFICIAL_PARTICIPLE_CLAUSE",
                        severity=Severity.medium,
                        clean_start=m.start(),
                        clean_end=m.end(),
                        explanation="Trailing '-ing' clause adds vague significance "
                        "(superficial analysis).",
                    )
                )
        return spans

    def _nlp_spans(self, doc: Document) -> list[Evidence]:
        """Dependency-parse path: a trailing adverbial/adjectival clause headed by a present
        participle whose subtree carries no concrete entity or number is superficial."""
        spans: list[Evidence] = []
        parsed = parse(doc.cleaned_text)
        for sent in parsed.sents:
            for tok in sent:
                if tok.tag_ != "VBG" or tok.dep_ not in {"advcl", "acl", "conj"}:
                    continue
                if tok.i <= sent.root.i:  # only trailing clauses (after the main verb)
                    continue
                subtree = list(tok.subtree)
                if any(t.ent_type_ or t.like_num for t in subtree):
                    continue  # concrete -> not superficial
                if (
                    tok.lemma_ + "ing" not in _ANALYSIS_VERBS
                    and tok.text.lower() not in _ANALYSIS_VERBS
                ):
                    if not any(t.lower_ in _VAGUE_NOUNS for t in subtree):
                        continue
                start = min(t.idx for t in subtree)
                last = max(subtree, key=lambda t: t.idx)
                end = last.idx + len(last.text)
                spans.append(
                    doc.evidence(
                        rule_id="SUPERFICIAL_PARTICIPLE_CLAUSE",
                        severity=Severity.medium,
                        clean_start=start,
                        clean_end=end,
                        explanation="Trailing '-ing' clause adds vague significance "
                        "(superficial analysis).",
                    )
                )
        return spans


# --- negative parallelism + rule of three ----------------------------------------------------

# Three coordinated abstract/evaluative items ("vibrant, dynamic, and transformative").
_TRICOLON = re.compile(r"\b(\w+), (\w+),? and (\w+)\b")
_ABSTRACT_SUFFIX = re.compile(r"(?:ing|ity|ness|tion|ment|ive|ous|ful|ant|ent|al|ic)$")


def _abstract(word: str) -> bool:
    return bool(_ABSTRACT_SUFFIX.search(word.lower())) and len(word) > 4


class Parallelism:
    dimension = Dimension.parallelism
    _full_scale = 3.0

    @lru_cache(maxsize=1)  # noqa: B019
    def _rules(self) -> list[Rule]:
        return load_rules_from_directory("patterns", "parallelism")

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = find_matches(doc, self._rules())
        spans.extend(self._tricolon_spans(doc))
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
        rate = per_hundred_words(weighted, doc.word_count)
        return FeatureResult(
            dimension=self.dimension, score=saturating(rate, self._full_scale), spans=spans
        )

    def _tricolon_spans(self, doc: Document) -> list[Evidence]:
        spans: list[Evidence] = []
        for m in _TRICOLON.finditer(doc.cleaned_text):
            items = [m.group(1), m.group(2), m.group(3)]
            if sum(_abstract(w) for w in items) >= 2:
                spans.append(
                    doc.evidence(
                        rule_id="PARALLEL_RULE_OF_THREE",
                        severity=Severity.low,
                        clean_start=m.start(),
                        clean_end=m.end(),
                        explanation="Rule of three: three coordinated abstract items.",
                    )
                )
        return spans


# --- copula avoidance ------------------------------------------------------------------------


class CopulaAvoidance:
    dimension = Dimension.copula_avoidance
    _full_scale = 4.0

    @lru_cache(maxsize=1)  # noqa: B019
    def _rules(self) -> list[Rule]:
        return load_rules_from_directory("patterns", "copula")

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        spans = find_matches(doc, self._rules())
        weighted = sum(SEVERITY_WEIGHT[s.severity] for s in spans)
        rate = per_hundred_words(weighted, doc.word_count)
        return FeatureResult(
            dimension=self.dimension, score=saturating(rate, self._full_scale), spans=spans
        )


register(SuperficialAnalysis())
register(Parallelism())
register(CopulaAvoidance())
