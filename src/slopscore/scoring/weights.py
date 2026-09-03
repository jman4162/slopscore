"""Default linear weights combining dimensions into a SlopScore logit.

Hand-set (a trained model is the opt-in ``--scorer ml``). The scorer computes
``BIAS + gain * sum(w_d * m_d * gate_d * dim_d) + w_human * human`` and applies a sigmoid.
``human_writing_signals`` has a NEGATIVE weight: dense human-writing markers pull the score down.
``WEAK_DIMENSIONS`` are always damped by the corroboration gate unless a strong, span-backed
dimension is also elevated (a lone fancy word or em dash should not, by itself, reach "severe").
"""

from __future__ import annotations

from slopscore.models import Dimension

BIAS = -2.6

DEFAULT_WEIGHTS: dict[Dimension, float] = {
    # high-confidence / strong
    Dimension.prompt_residue: 4.5,
    Dimension.superficial_analysis: 2.8,
    Dimension.significance_inflation: 2.8,
    Dimension.formulaic_structure: 2.6,
    # Insight-signaling (v0.7): a real tell when dense, but more register-dependent than the
    # legacy-puffery of significance_inflation, so it sits a notch lower and is genre-softened.
    Dimension.insight_signaling: 2.4,
    Dimension.weasel_attribution: 2.0,
    Dimension.unsupported_claims: 1.6,
    # Genericity is statistical and span-less, and it reads 1.0 on abstract HUMAN prose (a
    # reflective first-person paragraph with no names or numbers) exactly as it does on slop. At
    # 1.6 it put such prose at ~44 "mild" with zero findings; at 0.8 it stays under 25.
    Dimension.genericity: 0.8,
    Dimension.redundancy: 1.2,
    Dimension.cadence_sameness: 0.9,
    # weak-alone (damped by the corroboration gate unless a strong dimension co-fires)
    Dimension.lexical_markers: 2.2,
    Dimension.parallelism: 1.6,
    Dimension.copula_avoidance: 1.4,
    Dimension.formatting_tells: 0.8,
    # Performative candor (v0.9): sits below weasel_attribution because sincerity markers are core
    # spoken English in a way that "studies show" is not. Weak-alone, so a chatty-but-concrete
    # human post is damped rather than convicted on candor alone.
    Dimension.performative_candor: 1.8,
    # negative counterweight
    Dimension.human_writing_signals: -2.2,
}

# Dimensions that are weak on their own and need corroboration to count at full weight.
WEAK_DIMENSIONS: frozenset[Dimension] = frozenset(
    {
        Dimension.lexical_markers,
        Dimension.parallelism,
        Dimension.copula_avoidance,
        Dimension.formatting_tells,
        Dimension.performative_candor,
    }
)

# Statistical dimensions: no evidence spans, and (for genericity) a high resting value on almost
# all prose. They never unlock a weak dimension, otherwise genericity alone would corroborate
# everything and the gate would be decorative.
STATISTICAL_DIMENSIONS: frozenset[Dimension] = frozenset(
    {
        Dimension.genericity,
        Dimension.cadence_sameness,
        Dimension.redundancy,
        Dimension.human_writing_signals,
    }
)

# The dimensions whose elevation unlocks full weight for the weak ones: strong AND span-backed.
CORROBORATING_DIMENSIONS: frozenset[Dimension] = (
    frozenset(DEFAULT_WEIGHTS) - WEAK_DIMENSIONS - STATISTICAL_DIMENSIONS
)

# How much a weak dimension's contribution is kept when nothing strong corroborates it.
LONE_WEAK_DAMP = 0.3

# The gate ramps linearly from LONE_WEAK_DAMP at a strongest-corroborator value of RAMP_LO to
# full weight at RAMP_HI, so the score is continuous and non-decreasing in every dimension.
RAMP_LO = 0.25
RAMP_HI = 0.5

# A dimension counts as "elevated" above this score (reporting only; the gate uses the ramp).
ELEVATED = 0.5


def weak_gate(strongest_corroborator: float) -> float:
    """Multiplier applied to every weak dimension, in [LONE_WEAK_DAMP, 1.0]."""
    ramp = (strongest_corroborator - RAMP_LO) / (RAMP_HI - RAMP_LO)
    ramp = min(1.0, max(0.0, ramp))
    return LONE_WEAK_DAMP + (1.0 - LONE_WEAK_DAMP) * ramp
