"""Personal baseline calibration.

``slopscore-lint calibrate ./my-writing --profile me`` scores each document in a corpus and stores
robust per-dimension statistics. Later scans compare new text against that baseline and report
how far each dimension deviates (a z-score), reframing the question from "does this look like
AI?" to "does this deviate from *my* usual style in sloppy ways?". Robust stats (median/MAD)
are used for small corpora; mean/std otherwise. Prior art: Burrows's Delta (stylometry).
"""

from __future__ import annotations

import math
import statistics
from pathlib import Path

from pydantic import BaseModel, Field

from slopscore.models import SCHEMA_VERSION, BaselineComparison, Dimensions

_PROFILE_DIR = Path.home() / ".slopscore" / "profiles"
# Below this many documents, mean/std is unstable; use median/MAD instead.
_ROBUST_BELOW_DOCS = 50
# 1.4826 * MAD approximates the std of a normal distribution (robust scale estimate).
_MAD_TO_STD = 1.4826


class DimensionStats(BaseModel):
    mean: float
    std: float
    median: float
    mad: float

    def zscore(self, value: float, *, robust: bool) -> float:
        center, scale = (self.median, self.mad * _MAD_TO_STD) if robust else (self.mean, self.std)
        if scale <= 1e-9:
            # No baseline variance: report a capped deviation when the value clearly differs.
            if abs(value - center) <= 1e-6:
                return 0.0
            return math.copysign(3.0, value - center)
        return max(-3.0, min(3.0, (value - center) / scale))


class CalibrationProfile(BaseModel):
    version: str = SCHEMA_VERSION
    profile_name: str
    n_docs: int
    n_words: int
    robust: bool  # True when built from a small corpus (use median/MAD for z-scores)
    dimensions: dict[str, DimensionStats] = Field(default_factory=dict)

    def compare(self, dims: Dimensions) -> BaselineComparison:
        observed = dims.model_dump()
        deviations = {
            name: round(stats.zscore(float(observed.get(name, 0.0)), robust=self.robust), 2)
            for name, stats in self.dimensions.items()
        }
        return BaselineComparison(profile_name=self.profile_name, deviations=deviations)


def build_profile(
    name: str, per_doc_dimensions: list[Dimensions], n_words: int
) -> CalibrationProfile:
    """Aggregate per-document dimension vectors into a baseline profile."""
    n = len(per_doc_dimensions)
    robust = n < _ROBUST_BELOW_DOCS
    field_names = list(Dimensions.model_fields)
    stats: dict[str, DimensionStats] = {}
    for field in field_names:
        values = [
            float(getattr(d, field)) for d in per_doc_dimensions if getattr(d, field) is not None
        ]
        if not values:
            continue
        med = statistics.median(values)
        mad = statistics.median([abs(v - med) for v in values])
        stats[field] = DimensionStats(
            mean=statistics.fmean(values),
            std=statistics.pstdev(values) if len(values) > 1 else 0.0,
            median=med,
            mad=mad,
        )
    return CalibrationProfile(
        profile_name=name, n_docs=n, n_words=n_words, robust=robust, dimensions=stats
    )


def profile_path(name: str) -> Path:
    return _PROFILE_DIR / f"{name}.json"


def save_profile(profile: CalibrationProfile) -> Path:
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    path = profile_path(profile.profile_name)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_profile(name: str) -> CalibrationProfile | None:
    path = profile_path(name)
    if not path.exists():
        return None
    return CalibrationProfile.model_validate_json(path.read_text(encoding="utf-8"))
