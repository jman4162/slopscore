"""Every shipped regex rule pack stays well-formed: required fields present, regex compiles,
rule_ids globally unique. Cheap defense as the phrase packs grow (e.g. the v0.7 insight tier)."""

from __future__ import annotations

from pathlib import Path

import yaml

from slopscore.features._ruleset import _rules_from_yaml

_PATTERNS = Path(__file__).resolve().parents[1] / "src" / "slopscore" / "data" / "patterns"

# The suggestions pack uses a different schema (suggestion/confidence, no explanation), handled by
# features/suggestions.py rather than the shared ruleset loader.
_SKIP_DIRS = {"suggestions"}


def _rule_pack_files() -> list[Path]:
    return [
        p
        for p in sorted(_PATTERNS.rglob("*.yaml"))
        if not any(part in _SKIP_DIRS for part in p.relative_to(_PATTERNS).parts)
    ]


def test_every_rule_pack_is_well_formed() -> None:
    files = _rule_pack_files()
    assert files, "no rule packs found"
    for path in files:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        rules = _rules_from_yaml(raw)  # raises on a missing field or an uncompilable regex
        assert rules, f"{path} has no rules"
        for rule in rules:
            assert rule.rule_id and rule.explanation


def test_rule_ids_are_globally_unique() -> None:
    seen: dict[str, Path] = {}
    for path in _rule_pack_files():
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rule in _rules_from_yaml(raw):
            assert rule.rule_id not in seen, (
                f"duplicate rule_id {rule.rule_id} in {path} and {seen[rule.rule_id]}"
            )
            seen[rule.rule_id] = path
