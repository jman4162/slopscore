"""slopscore — transparent AI-slop writing-pattern analysis.

Detects formulaic, generic, low-specificity, over-polished writing patterns and reports a
0-100 SlopScore with evidence spans. It does NOT determine AI authorship.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

from slopscore.core import SlopScorer, scan_path, scan_text, scan_url
from slopscore.models import Report

# Read from the installed distribution rather than a hand-maintained literal. The literal
# drifted once: 0.9.0 shipped with "0.8.1" here, and report/sarif.py publishes this as
# tool.driver.version, so code-scanning dashboards were told the wrong version.
try:
    __version__ = _distribution_version("slopscore-lint")
except PackageNotFoundError:  # imported from a source tree with no install
    __version__ = "0.0.0.dev0"

__all__ = ["Report", "SlopScorer", "__version__", "scan_path", "scan_text", "scan_url"]
