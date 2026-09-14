"""Clause-initial rules use the one shared anchor, and every YAML loader expands it."""

from __future__ import annotations

from pathlib import Path

import regex as re
import yaml

from slopscore.config import data_path
from slopscore.features._ruleset import (
    CLAUSE_START,
    CLAUSE_START_TOKEN,
    compile_rule_pattern,
    load_rules,
    load_rules_from_directory,
)

_DATA = Path(data_path("patterns")).parent

# Rules that use a bare `^` line anchor or a hand-written sentence lookbehind ON PURPOSE.
#
# RESIDUE_*: "Certainly!" or "Great question!" as the first thing on a line IS the tell.
# The other six shipped before v0.14 with their own anchors. Moving them onto CLAUSE_START
# changed their findings on flat prose (they fired after a mid-line semicolon and stopped firing
# after an unpunctuated heading line), so they were put back. Their wrap-sensitivity is recorded in
# eval/results/source_sweep.json. Adding an id here is a decision to be written down, not a fix.
LINE_ANCHORED = frozenset(
    {
        "RESIDUE_CERTAINLY",
        "RESIDUE_SYCOPHANTIC_OPENER",
        "FORMULAIC_IN_CONCLUSION",
        "FORMULAIC_THAT_SAID",
        "FORMULAIC_SIMPLY_PUT",
        "WEASEL_CERTAINTY_OPENER",
        "CANDOR_ADVERB_PARENTHETICAL",
        "PARALLEL_X_NOT_Y",
    }
)

_BARE_CARET = re.compile(r"(?<!\[)\^")
_HAND_LOOKBEHIND = re.compile(r"\(\?<=\[[.!?]")


def _every_yaml_pattern() -> list[tuple[str, str, str]]:
    """``(file, rule id or "marker", pattern)`` for every pattern under data/."""
    out: list[tuple[str, str, str]] = []
    for path in sorted(_DATA.rglob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            continue
        for entry in raw.get("rules", []) or []:
            if "pattern" in entry:
                out.append((path.name, entry["rule_id"], entry["pattern"]))
        for marker in raw.get("markers", []) or []:
            out.append((path.name, "marker", marker))
    return out


def test_no_unlisted_pattern_anchors_on_a_line_or_a_hand_written_boundary() -> None:
    # `^` under MULTILINE is a line anchor and fires mid-sentence on hard-wrapped prose; every
    # hand-copied sentence lookbehind was wrong in its own way. Write {CLAUSE_START} instead.
    offenders = sorted(
        f"{name}:{rule}"
        for name, rule, pattern in _every_yaml_pattern()
        if rule not in LINE_ANCHORED
        and (_BARE_CARET.search(pattern) or _HAND_LOOKBEHIND.search(pattern))
    )
    assert offenders == []


def test_the_allow_list_is_not_stale() -> None:
    # Each exemption must still be needed: the rule exists AND still uses a line anchor or a
    # hand-written boundary. A rule moved onto {CLAUSE_START} and left on the list would silently
    # exempt any bare `^` added to it later.
    patterns = {rule: pattern for _, rule, pattern in _every_yaml_pattern()}
    assert set(patterns) >= LINE_ANCHORED
    for rule in LINE_ANCHORED:
        assert _BARE_CARET.search(patterns[rule]) or _HAND_LOOKBEHIND.search(patterns[rule]), rule


def test_the_token_is_used_and_every_loader_expands_it() -> None:
    from slopscore.features.metadiscourse import _markers
    from slopscore.features.suggestions import _swaps

    assert any(CLAUSE_START_TOKEN in p for _, _, p in _every_yaml_pattern())
    compiled = (
        [r.pattern for r in load_rules("patterns", "formulaic.yaml")]
        + [r.pattern for r in load_rules_from_directory("patterns", "metadiscourse")]
        + [r.pattern for r in load_rules_from_directory("patterns", "metadiscourse_broad")]
        + _markers()
        + [s.pattern for s in _swaps()]
    )
    assert all(CLAUSE_START_TOKEN not in p.pattern for p in compiled)
    assert any(CLAUSE_START in p.pattern for p in compiled)


def test_an_unexpanded_token_would_fail_silently() -> None:
    # Why every loader must use compile_rule_pattern: the regex module accepts the raw token as a
    # literal, so a rule compiled without expansion loads fine and never matches prose.
    raw = re.compile("{CLAUSE_START}to be clear,", re.IGNORECASE)
    assert raw.search("It rained. To be clear, x") is None
    assert compile_rule_pattern("{CLAUSE_START}to be clear,").search("It rained. To be clear, x")


def test_anchor_accepts_sentence_boundaries_and_refuses_wraps() -> None:
    p = compile_rule_pattern("{CLAUSE_START}to be clear,")
    for text in [
        "to be clear, x",
        "\n to be clear, x",
        "a. to be clear, x",
        "a. \nto be clear, x",
        "a.\n \nto be clear, x",
        "a.\n\n   to be clear, x",
        "a.\n<!-- c -->\nto be clear, x",
        "a. <!-- c --> to be clear, x",
        "<!-- c -->\nto be clear, x",
        'he said "no." to be clear, x',
        "a.) to be clear, x",
    ]:
        assert p.search(text), text
    # Refused: a hard wrap, a mid-sentence parenthetical, and, as accepted false negatives, a
    # clause after a colon, a semicolon, or an unpunctuated heading line.
    for text in [
        "and\nto be clear, x",
        "and, to be clear, x",
        "and to be clear, x",
        "Key points: to be clear, x",
        "Costs rose; to be clear, x",
        "Background\nto be clear, x",
        # A comment end is a boundary only when the comment itself starts at one.
        "and\n<!-- c -->\nto be clear, x",
        "-->\nto be clear, x",
    ]:
        assert not p.search(text), text
