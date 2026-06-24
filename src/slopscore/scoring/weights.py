"""Default linear weights combining dimensions into a SlopScore logit.

Hand-set for v0.2 (a trained model is v0.3). The scorer computes ``b0 + sum(w_d * dim_d)`` with
a corroboration gate, then a sigmoid. ``human_writing_signals`` has a NEGATIVE weight: dense
human-writing markers pull the score down. ``WEAK_DIMENSIONS`` are damped when they fire alone
(weak-alone tells: a lone fancy word or em dash should not, by itself, reach "severe").
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
    Dimension.weasel_attribution: 2.0,
    Dimension.genericity: 1.6,
    Dimension.unsupported_claims: 1.6,
    Dimension.redundancy: 1.2,
    Dimension.cadence_sameness: 0.9,
    # weak-alone (damped by the corroboration gate unless another dimension co-fires)
    Dimension.lexical_markers: 2.2,
    Dimension.parallelism: 1.6,
    Dimension.copula_avoidance: 1.4,
    Dimension.formatting_tells: 0.8,
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
    }
)

# How much a weak dimension's contribution is kept when it fires with no corroboration.
LONE_WEAK_DAMP = 0.3

# A dimension counts as "elevated" (corroborating) above this score.
ELEVATED = 0.5
