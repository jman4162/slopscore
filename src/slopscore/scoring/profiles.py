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
        Dimension.significance_inflation: 1.2,
        Dimension.unsupported_claims: 1.1,
        Dimension.cadence_sameness: 0.8,
    },
    "essay": {
        Dimension.redundancy: 1.2,
        Dimension.genericity: 1.1,
        Dimension.parallelism: 1.1,
    },
    "academic": {
        Dimension.lexical_markers: 0.8,
        Dimension.formulaic_structure: 0.9,
        Dimension.copula_avoidance: 0.7,  # "represents/constitutes" is normal in academia
        Dimension.weasel_attribution: 0.8,
    },
    "marketing": {
        Dimension.lexical_markers: 0.7,
        Dimension.genericity: 0.8,
        Dimension.significance_inflation: 0.8,
        Dimension.copula_avoidance: 0.6,  # marketing naturally uses "boasts/features"
        Dimension.formatting_tells: 0.7,
    },
    "technical": {
        Dimension.lexical_markers: 0.7,
        Dimension.cadence_sameness: 0.7,
        Dimension.copula_avoidance: 0.5,  # "serves as / functions as" is precise here
        Dimension.parallelism: 0.8,
    },
    "social": {
        Dimension.formatting_tells: 0.6,
    },
}

KNOWN_PROFILES = tuple(PROFILES)


def profile_multipliers(profile: str) -> dict[Dimension, float]:
    return PROFILES.get(profile, {})
