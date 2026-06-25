"""slopscore — transparent AI-slop writing-pattern analysis.

Detects formulaic, generic, low-specificity, over-polished writing patterns and reports a
0-100 SlopScore with evidence spans. It does NOT determine AI authorship.
"""

from __future__ import annotations

from slopscore.core import SlopScorer, scan_path, scan_text, scan_url
from slopscore.models import Report

__version__ = "0.3.0"

__all__ = ["Report", "SlopScorer", "__version__", "scan_path", "scan_text", "scan_url"]
