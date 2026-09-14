"""Shared loader for YAML regex rulesets (formulaic patterns, prompt residue)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import regex as re
import yaml

from slopscore.config import data_path
from slopscore.document import Document
from slopscore.features.base import SEVERITY_WEIGHT
from slopscore.models import Evidence, Severity

__all__ = [
    "CLAUSE_START",
    "CLAUSE_START_TOKEN",
    "SEVERITY_WEIGHT",
    "Rule",
    "expand_pattern",
    "find_matches",
    "load_rules",
    "load_rules_from_directory",
]

# The start of a clause, for rules that must only match a sentence opener ("To be clear,",
# "Honestly,", "In short,"). Written ONCE here and spliced into YAML patterns at load time
# wherever they say ``{CLAUSE_START}``, because every hand-copied version of it has been wrong in
# a different way:
#
# * ``^`` is a LINE anchor under the ``re.MULTILINE`` these rules compile with, so it matched
#   mid-sentence on hard-wrapped prose (code comments, commit messages, plain-text files) and let
#   a wrapped paragraph with no metadiscourse in it escalate to a run finding.
# * ``(?<=[.!?]\s)`` allowed exactly one whitespace character, so a sentence boundary written as
#   ``. \n`` (trailing space, then the line break; 18 of 180 long-form corpus rows) never anchored,
#   and neither did a sentence after a closing quote (``he said "no." To be clear,``).
# * ``(?<=\n\n)`` was a second definition of "paragraph break" that disagreed with the
#   segmenter's ``\n[ \t]*\n``: a blank line containing a space was a paragraph to one and not
#   the other, so the same bytes scored differently as .txt and as .md.
#
# What it accepts: the start of the text (leading whitespace allowed), a blank line, terminal
# punctuation plus any closers and whitespace (a line break included), a colon- or
# semicolon-terminated line ("Key points:\nTo be clear,"), and the end of an HTML comment,
# which is what ``ingest/markdown.py`` leaves in front of a paragraph carrying a suppression
# comment. What it refuses: a line break after a bare word, which is what a hard wrap looks
# like. The cost is a plain-text heading with no punctuation ("Background\nTo be clear,"), and
# that is accepted: the wrap case is far commoner and the false positive it produced was severe.
#
# Variable-width lookbehind is a ``regex`` module feature; ``re`` would refuse this pattern.
CLAUSE_START = r"""(?:(?<=\A\s*)|(?<=\n\s*\n)|(?<=[.!?:;]["')\]]*\s+)|(?<=-->\s*))"""
CLAUSE_START_TOKEN = "{CLAUSE_START}"


def expand_pattern(pattern: str) -> str:
    """Splice the shared anchor into a YAML pattern before compiling it."""
    return pattern.replace(CLAUSE_START_TOKEN, CLAUSE_START)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: Severity
    pattern: re.Pattern[str]
    explanation: str
    source: str = ""  # optional citation (e.g. "Kobak 2025"), for the model card


def _rules_from_yaml(raw: dict[str, Any]) -> list[Rule]:
    rules = []
    for entry in raw.get("rules", []) or []:
        rules.append(
            Rule(
                rule_id=entry["rule_id"],
                severity=Severity(entry.get("severity", "low")),
                pattern=re.compile(expand_pattern(entry["pattern"]), re.IGNORECASE | re.MULTILINE),
                explanation=entry["explanation"],
                source=entry.get("source", ""),
            )
        )
    return rules


def load_rules(*parts: str) -> list[Rule]:
    with data_path(*parts).open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return _rules_from_yaml(raw)


def load_rules_from_directory(*parts: str) -> list[Rule]:
    """Merge every ``*.yaml`` rule file under a packaged ``data/`` subdirectory.

    Lets a growing rule pack be split into small, themed files (the way Vale/proselint
    organize styles) without changing the loading feature.
    """
    directory = data_path(*parts)
    rules: list[Rule] = []
    for entry in sorted(directory.iterdir(), key=lambda p: p.name):
        if entry.name.endswith(".yaml"):
            with entry.open(encoding="utf-8") as fh:
                rules.extend(_rules_from_yaml(yaml.safe_load(fh)))
    return rules


def find_matches(doc: Document, rules: list[Rule], *, skip_quoted: bool = False) -> list[Evidence]:
    """Run every rule over the cleaned text. With ``skip_quoted``, matches that fall wholly inside
    a quotation are dropped: they are someone else's words, not the author's."""
    from slopscore.normalize.quotes import inside_quotes

    spans: list[Evidence] = []
    for rule in rules:
        for m in rule.pattern.finditer(doc.cleaned_text):
            if skip_quoted and inside_quotes(doc.quoted, m.start(), m.end()):
                continue
            spans.append(
                doc.evidence(
                    rule_id=rule.rule_id,
                    severity=rule.severity,
                    clean_start=m.start(),
                    clean_end=m.end(),
                    explanation=rule.explanation,
                )
            )
    return spans
