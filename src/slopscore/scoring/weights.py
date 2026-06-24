"""Default linear weights combining dimensions into a SlopScore logit.

v0.1 uses hand-set weights (no trained model yet — that is v0.3). The scorer computes
``b0 + sum(w_d * dimension_d)`` then a sigmoid. Weights reflect confidence in each signal:
prompt residue is near-certain, lexical/formulaic are strong, genericity/redundancy/cadence
are softer auxiliary signals.
"""

from __future__ import annotations

from slopscore.models import Dimension

BIAS = -2.2

DEFAULT_WEIGHTS: dict[Dimension, float] = {
    Dimension.prompt_residue: 4.5,
    Dimension.formulaic_structure: 3.0,
    Dimension.lexical_markers: 2.6,
    Dimension.genericity: 1.8,
    Dimension.unsupported_claims: 1.8,
    Dimension.redundancy: 1.4,
    Dimension.cadence_sameness: 1.0,
}
