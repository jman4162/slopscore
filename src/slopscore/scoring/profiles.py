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
        Dimension.insight_signaling: 1.15,
        Dimension.performative_candor: 1.1,
        Dimension.unsupported_claims: 1.1,
        Dimension.cadence_sameness: 0.8,
        Dimension.metadiscourse: 1.15,
    },
    "essay": {
        Dimension.redundancy: 1.2,
        Dimension.genericity: 1.1,
        Dimension.parallelism: 1.1,
        Dimension.insight_signaling: 1.2,  # essayist register is where this slop concentrates
        Dimension.performative_candor: 1.1,  # confessional-essay register
        Dimension.metadiscourse: 1.1,
    },
    "academic": {
        Dimension.structure_tells: 0.8,
        Dimension.lexical_markers: 0.8,
        Dimension.formulaic_structure: 0.9,
        Dimension.copula_avoidance: 0.7,  # "represents/constitutes" is normal in academia
        Dimension.weasel_attribution: 0.8,
        Dimension.insight_signaling: 0.6,  # "first principles / the crux" are legitimate here
        # IMRaD signposts by design: "In this section we describe...", "In summary,".
        Dimension.metadiscourse: 0.5,
    },
    "marketing": {
        Dimension.structure_tells: 1.1,  # the emoji-bullet listicle is marketing's slop shape
        Dimension.lexical_markers: 0.7,
        Dimension.genericity: 0.8,
        Dimension.significance_inflation: 0.8,
        Dimension.copula_avoidance: 0.6,  # marketing naturally uses "boasts/features"
        Dimension.formatting_tells: 0.7,
        Dimension.insight_signaling: 0.9,
        # Manufactured sincerity is marketing's native failure mode ("real talk", "let's be real",
        # "cards on the table"), so this is boosted where insight_signaling is softened.
        Dimension.performative_candor: 1.2,
    },
    "technical": {
        Dimension.structure_tells: 0.7,  # headings, bullets, and bold labels are documentation
        Dimension.lexical_markers: 0.7,
        Dimension.cadence_sameness: 0.7,
        Dimension.copula_avoidance: 0.5,  # "serves as / functions as" is precise here
        Dimension.parallelism: 0.8,
        Dimension.insight_signaling: 0.6,  # "load-bearing / pressure-test" are apt in eng writing
        Dimension.performative_candor: 0.8,  # RFCs and code comments hedge colloquially
        Dimension.metadiscourse: 0.5,  # reference docs signpost and cross-reference by design
    },
    "social": {
        Dimension.formatting_tells: 0.6,
        Dimension.structure_tells: 0.8,
        Dimension.insight_signaling: 1.15,
        # Inverted against insight_signaling above, for the same reason performative_candor is:
        # "TL;DR" and "to be clear," are native register in a thread, not slop.
        Dimension.metadiscourse: 0.9,
        # Inverted relative to insight_signaling above: conversational "honestly" and "to be fair"
        # are native human speech here, not slop. This split is the reason performative_candor is
        # its own dimension rather than extra rules in the insight_signaling pack.
        Dimension.performative_candor: 0.6,
    },
}

KNOWN_PROFILES = tuple(PROFILES)


def profile_multipliers(profile: str) -> dict[Dimension, float]:
    return PROFILES.get(profile, {})
