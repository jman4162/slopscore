"""Optional authorship-signal adapters — interface only, kept strictly separate from the score.

slopscore deliberately ships **no** authorship detector. Research (Binoculars, Fast-DetectGPT,
GLTR, SynthID) shows they collapse on paraphrase, are biased against non-native English, are
academic-only, or cover almost no models. So this package provides only a pluggable
``AuthorshipDetector`` protocol and a no-op reference adapter. A detector's output is reported in a
**separate** field with a mandatory caveat and is NEVER merged into the SlopScore. Bring your own
detector behind the ``[detectors]`` extra if you understand the limitations.
"""

from slopscore.detectors.base import (
    AUTHORSHIP_CAVEAT,
    AuthorshipDetector,
    DetectorResult,
    ReferenceDetector,
)

__all__ = [
    "AUTHORSHIP_CAVEAT",
    "AuthorshipDetector",
    "DetectorResult",
    "ReferenceDetector",
]
