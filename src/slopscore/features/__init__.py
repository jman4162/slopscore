"""Feature extractors. Importing this package registers every dimension's feature."""

from slopscore.features import (  # noqa: F401  (imported for registration side effects)
    cadence,
    formulaic_patterns,
    lexical_markers,
    prompt_residue,
    redundancy,
    specificity,
)
from slopscore.features.base import Feature, registry

__all__ = ["Feature", "registry"]
