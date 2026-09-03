"""Runtime configuration for a scan."""

from __future__ import annotations

from enum import StrEnum
from importlib import resources

from pydantic import BaseModel


class Strictness(StrEnum):
    conservative = "conservative"
    balanced = "balanced"
    sensitive = "sensitive"


# Strictness scales the positive evidence sum (not the bias, and not the human-signal
# counterweight): conservative needs 25% more evidence to reach a given score, sensitive 20% less,
# and the zero-evidence floor is the same at every setting.
STRICTNESS_GAIN: dict[Strictness, float] = {
    Strictness.conservative: 0.8,
    Strictness.balanced: 1.0,
    Strictness.sensitive: 1.25,
}


class Scorer(StrEnum):
    rules = "rules"  # hand-set weights + corroboration gate
    ml = "ml"  # learned logistic-regression model (data/model/slopscore-v0.3.json)


# Directory names / glob patterns skipped by directory and multi-target scans unless a config
# `exclude` replaces them.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    "node_modules",
    ".venv",
    "venv",
    ".git",
    "vendor",
    "dist",
    "build",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "site",
)


class Settings(BaseModel):
    profile: str = "blog"
    strictness: Strictness = Strictness.conservative
    scorer: Scorer = Scorer.rules
    # Below this word count, confidence is heavily suppressed (spec: <300 words).
    min_reliable_words: int = 300
    # Linter config (v0.4). Dimension/rule names that should not contribute findings; per-rule
    # severity overrides. Disabled dimensions skip their feature entirely (score -> 0); disabled
    # rules and severity overrides are applied as an evidence post-filter.
    disabled_dimensions: frozenset[str] = frozenset()
    disabled_rules: frozenset[str] = frozenset()
    rule_severity: dict[str, str] = {}
    # Include opt-in, advisory rewrite suggestions (does not affect the score or --fail-on).
    suggest: bool = False
    # Include the opt-in "broad" tier of insight_signaling rules (rationalist/essayist jargon with
    # higher false-positive risk). Off by default; affects the score, evidence, and --fail-on.
    broad_rules: bool = False
    # CI gate (v0.11). `fail_on`: exit 1 when any FINDING reaches this severity (none|low|medium|
    # high). `score_threshold`: exit 1 when any non-abstained document scores at or above it.
    # Either condition fails the scan; abstained documents never fail on score.
    fail_on: str = "none"
    score_threshold: float | None = None
    # Batch walker filters: root-relative glob patterns (fnmatch) or bare directory names.
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = DEFAULT_EXCLUDES


def data_path(*parts: str) -> resources.abc.Traversable:
    """Locate a packaged data file, e.g. ``data_path("lexicons", "markers.yaml")``."""
    return resources.files("slopscore").joinpath("data", *parts)
