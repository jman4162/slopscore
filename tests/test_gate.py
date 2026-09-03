"""The corroboration gate is monotone and only strong, span-backed dimensions unlock it."""

from __future__ import annotations

from itertools import pairwise

from slopscore.config import Settings, Strictness
from slopscore.models import Dimension
from slopscore.scoring.scorer import _score_rules
from slopscore.scoring.weights import LONE_WEAK_DAMP, RAMP_HI, RAMP_LO, weak_gate

_S = Settings()
_LEX = Dimension.lexical_markers
_FMT = Dimension.formatting_tells
_SIG = Dimension.significance_inflation


def _score(by_dim: dict[Dimension, float], settings: Settings = _S) -> float:
    return _score_rules(by_dim, settings)[0]


def test_breakdown_reproduces_the_score() -> None:
    import math

    by_dim = {_LEX: 0.7, _SIG: 0.4, Dimension.genericity: 0.6, Dimension.human_writing_signals: 0.3}
    score, _, b = _score_rules(by_dim, _S)
    logit = b.bias + sum(r.logit for r in b.contributions)
    assert round(100 / (1 + math.exp(-logit)), 1) == score
    assert b.statistical_logit != 0.0
    assert {r.dimension for r in b.contributions if r.statistical} == {
        "genericity",
        "cadence_sameness",
        "redundancy",
        "human_writing_signals",
    }


def test_weak_dimension_is_monotone_in_its_own_value() -> None:
    scores = [_score({_LEX: x / 50}) for x in range(51)]
    assert all(a <= b for a, b in pairwise(scores)), scores


def test_two_weak_dimensions_do_not_corroborate_each_other() -> None:
    both, notes, _ = _score_rules({_LEX: 1.0, _FMT: 1.0}, _S)
    with_strong = _score({_LEX: 1.0, _SIG: 1.0})
    assert notes == ["formatting_tells", "lexical_markers"]
    assert both < 40 < with_strong


def test_statistical_dimensions_do_not_unlock_weak_ones() -> None:
    lone = _score({_LEX: 1.0})
    with_generic = _score({_LEX: 1.0, Dimension.genericity: 1.0})
    with_strong = _score({_LEX: 1.0, _SIG: 1.0})
    # genericity adds its own weight but must not lift the gate: the lexical contribution stays
    # damped, so the jump is far smaller than with a strong corroborator.
    assert with_generic - lone < with_strong - lone


def test_gate_ramp_values() -> None:
    assert weak_gate(0.0) == LONE_WEAK_DAMP
    assert weak_gate(RAMP_LO) == LONE_WEAK_DAMP
    assert LONE_WEAK_DAMP < weak_gate((RAMP_LO + RAMP_HI) / 2) < 1.0
    assert weak_gate(RAMP_HI) == 1.0
    assert weak_gate(1.0) == 1.0


def test_zero_evidence_floor_is_strictness_independent() -> None:
    floors = {_score({}, Settings(strictness=s)) for s in Strictness}
    assert len(floors) == 1
    assert floors.pop() < 10


def test_strictness_is_ordered_on_every_input() -> None:
    for by_dim in ({}, {_LEX: 0.4}, {_SIG: 0.6}):
        c, b, s = (_score(by_dim, Settings(strictness=x)) for x in Strictness)
        assert c <= b <= s
