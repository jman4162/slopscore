"""Every clause-initial rule uses the one shared anchor, and the anchor does what it says."""

from __future__ import annotations

from pathlib import Path

import regex as re
import yaml

from slopscore.config import data_path
from slopscore.features._ruleset import (
    CLAUSE_START,
    CLAUSE_START_TOKEN,
    expand_pattern,
    load_rules,
    load_rules_from_directory,
)

_DATA = Path(data_path("patterns")).parent


def _every_yaml_pattern() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(_DATA.rglob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entry in raw.get("rules", []) or []:
            out.append((f"{path.name}:{entry['rule_id']}", entry["pattern"]))
        for marker in raw.get("markers", []) or []:
            out.append((f"{path.name}:marker", marker))
    return out


def test_no_pattern_hand_writes_a_clause_anchor() -> None:
    # `^` under MULTILINE is a line anchor. It fired mid-sentence on hard-wrapped prose, and each
    # hand-copied lookbehind that replaced it was wrong in its own way (one whitespace character,
    # a private definition of "paragraph break"). The prompt_residue rules are the exception:
    # "Certainly!" and "Great question!" as the first thing on a line IS the tell.
    offenders = [
        name
        for name, pattern in _every_yaml_pattern()
        if "(?:^|" in pattern or "(?<=[.!?]\\s)" in pattern or "(?<=\\n\\n)" in pattern
    ]
    assert offenders == []
    assert any(CLAUSE_START_TOKEN in p for _, p in _every_yaml_pattern())


def test_the_loader_expands_the_token() -> None:
    rules = load_rules("patterns", "formulaic.yaml") + load_rules_from_directory(
        "patterns", "metadiscourse"
    )
    assert all(CLAUSE_START_TOKEN not in r.pattern.pattern for r in rules)
    assert any(CLAUSE_START in r.pattern.pattern for r in rules)


def test_anchor_accepts_sentence_boundaries_and_refuses_wraps() -> None:
    p = re.compile(expand_pattern("{CLAUSE_START}to be clear,"), re.IGNORECASE | re.MULTILINE)
    assert CLAUSE_START in p.pattern
    for text in [
        "to be clear, x",
        "\n to be clear, x",
        "a. to be clear, x",
        "a. \nto be clear, x",
        "a.\n \nto be clear, x",
        "Key points:\nto be clear, x",
        "-->\nto be clear, x",
        'he said "no." to be clear, x',
        "a.) to be clear, x",
    ]:
        assert p.search(text), text
    for text in ["and\nto be clear, x", "and, to be clear, x", "and to be clear, x"]:
        assert not p.search(text), text
