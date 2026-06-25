"""Authorship-detector adapter protocol and reference implementation.

``DetectorResult`` and the caveat live in :mod:`slopscore.models` (they are report types).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from slopscore.models import AUTHORSHIP_CAVEAT, DetectorResult


@runtime_checkable
class AuthorshipDetector(Protocol):
    """Plug-in interface. Implement this to supply your own authorship signal.

    Implementations must be deterministic and side-effect-free, and must accept that their output
    is reported separately from the slop score with the mandatory caveat.
    """

    name: str

    def detect(self, text: str) -> DetectorResult: ...


class ReferenceDetector:
    """No-op example adapter: always returns 0.5 (no information). Demonstrates the interface and
    ships nothing real. Replace with your own (e.g. a perplexity or Binoculars wrapper) behind the
    ``[detectors]`` extra if you accept the limitations in the caveat."""

    name = "reference-noop"

    def detect(self, text: str) -> DetectorResult:
        return DetectorResult(score=0.5, method=self.name)


__all__ = ["AUTHORSHIP_CAVEAT", "AuthorshipDetector", "DetectorResult", "ReferenceDetector"]
