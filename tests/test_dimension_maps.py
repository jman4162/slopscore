"""Every place that enumerates dimensions must agree, or a new dimension silently vanishes from a
report table (which happened to insight_signaling for two releases)."""

from __future__ import annotations

from slopscore.cli import _DIMENSION_GUIDE
from slopscore.models import Dimension, Dimensions
from slopscore.report.markdown import _DIMENSION_LABELS
from slopscore.scoring.weights import DEFAULT_WEIGHTS


def test_dimension_maps_are_in_sync() -> None:
    enum_names = {d.value for d in Dimension}
    model_fields = set(Dimensions.model_fields) - {"optional_ai_detector"}
    assert model_fields == enum_names
    assert {d.value for d in DEFAULT_WEIGHTS} == enum_names
    assert set(_DIMENSION_LABELS) == enum_names
    assert set(_DIMENSION_GUIDE) == enum_names
