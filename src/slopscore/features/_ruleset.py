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
    "DEFAULT_FLAGS",
    "SEVERITY_WEIGHT",
    "Rule",
    "compile_rule_pattern",
    "expand_pattern",
    "find_matches",
    "load_rules",
    "load_rules_from_directory",
]

# The start of a clause, for metadiscourse rules and markers that must only match a sentence
# opener ("To be clear,", "In short:"). Written ONCE here and spliced into YAML wherever a pattern
# says ``{CLAUSE_START}``, because every hand-copied version of it was wrong in a different way:
#
# * ``^`` is a LINE anchor under the ``re.MULTILINE`` these rules compile with, so it matched
#   mid-sentence on hard-wrapped prose (code comments, commit messages, plain-text files).
# * ``(?<=[.!?]\s)`` allowed exactly one whitespace character, so a boundary written ``. \n``
#   never anchored, and neither did a sentence after a closing quote (``"no." To be clear,``).
# * ``(?<=\n\n)`` disagreed with the segmenter's ``\n[ \t]*\n`` about what a paragraph is.
#
# It accepts the start of the text, a blank line, and terminal punctuation (colon and semicolon
# included) followed by any closers and whitespace. The metadiscourse feature matches it against
# a flattened copy of the text in which soft line breaks are spaces and HTML comments are blank
# (``features/metadiscourse.py:flatten``), so it never has to reason about line structure.
#
# Deliberately NOT used by the clause-initial rules that shipped before v0.14
# (FORMULAIC_IN_CONCLUSION, FORMULAIC_THAT_SAID, FORMULAIC_SIMPLY_PUT, WEASEL_CERTAINTY_OPENER,
# CANDOR_ADVERB_PARENTHETICAL, PARALLEL_X_NOT_Y). Moving them onto it changed their findings on
# flat prose: they began firing after a mid-line semicolon, and stopped firing after an
# unpunctuated heading line. Their wrap-sensitivity predates v0.14 and is recorded in
# eval/results/source_sweep.json; changing it is a calibration decision, not a release fix.
#
# Variable-width lookbehind is a ``regex`` module feature; ``re`` would refuse this pattern.
CLAUSE_START = r"""(?:(?<=\A\s*)|(?<=\n\s*\n\s*)|(?<=[.!?:;]["')\]]*\s+))"""
CLAUSE_START_TOKEN = "{CLAUSE_START}"
DEFAULT_FLAGS = re.IGNORECASE | re.MULTILINE


def expand_pattern(pattern: str) -> str:
    """Splice the shared anchor into a YAML pattern before compiling it."""
    return pattern.replace(CLAUSE_START_TOKEN, CLAUSE_START)


def compile_rule_pattern(pattern: str, flags: int = DEFAULT_FLAGS) -> re.Pattern[str]:
    """Compile a pattern read from YAML. Every YAML loader goes through this.

    The ``regex`` module compiles an unexpanded ``{CLAUSE_START}`` without complaint, as a
    literal that never matches prose, so a loader that compiled patterns itself would silently
    disable any rule using the token.
    """
    return re.compile(expand_pattern(pattern), flags)


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
                pattern=compile_rule_pattern(entry["pattern"]),
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
