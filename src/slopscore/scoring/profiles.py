"""Genre profiles: per-dimension weight multipliers.

A profile reweights dimensions for a genre. v0.1 ships a tuned ``blog`` default and neutral
placeholders for the other genres named in the spec; these get distinct tunings in v0.2.
"""

from __future__ import annotations

from slopscore.models import Dimension

# multiplier applied on top of DEFAULT_WEIGHTS; 1.0 = unchanged.
PROFILES: dict[str, dict[Dimension, float]] = {
    "blog": {
        Dimension.formulaic_structure: 1.2,
        Dimension.genericity: 1.2,
        Dimension.unsupported_claims: 1.1,
        Dimension.cadence_sameness: 0.8,
    },
    "essay": {
        Dimension.redundancy: 1.2,
        Dimension.genericity: 1.1,
    },
    "academic": {
        Dimension.lexical_markers: 0.8,
        Dimension.formulaic_structure: 0.9,
    },
    "marketing": {
        Dimension.lexical_markers: 0.7,
        Dimension.genericity: 0.8,
    },
    "technical": {
        Dimension.lexical_markers: 0.7,
        Dimension.cadence_sameness: 0.7,
    },
    "social": {},
}

KNOWN_PROFILES = tuple(PROFILES)


def profile_multipliers(profile: str) -> dict[Dimension, float]:
    return PROFILES.get(profile, {})
