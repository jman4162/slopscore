"""Personal-baseline calibration: build, save/load, and z-score deviation."""

from __future__ import annotations

from slopscore.config import Settings
from slopscore.core import build_document
from slopscore.ingest import from_string
from slopscore.models import Dimensions
from slopscore.scoring.calibrate import (
    CalibrationProfile,
    build_profile,
    load_profile,
    save_profile,
)
from slopscore.scoring.scorer import score_document

_CLEAN_DOCS = [
    "The shop opened in 1998 on Pine Street. It sold about 200 records a week. "
    "I worked there three years and learned to grade vinyl by eye.",
    "We drove to Bend in October. The pass was icy near the summit. Gas cost three "
    "dollars and we split a sandwich at a diner outside Sisters.",
    "The bug was a race condition in the cache. I added a lock, ran the tests fifty "
    "times, and it stopped failing. We shipped it on Friday.",
]


def _dims(text: str) -> Dimensions:
    return score_document(build_document(from_string(text)), Settings()).dimensions


def test_build_profile_uses_robust_stats_for_small_corpus() -> None:
    profile = build_profile("me", [_dims(t) for t in _CLEAN_DOCS], n_words=120)
    assert profile.robust is True
    assert profile.n_docs == 3
    assert "lexical_markers" in profile.dimensions


def test_slop_deviates_above_clean_baseline() -> None:
    profile = build_profile("me", [_dims(t) for t in _CLEAN_DOCS], n_words=120)
    slop = _dims(
        "This transformative platform stands as a testament to innovation, leveraging "
        "a robust, holistic tapestry and underscoring its enduring significance."
    )
    comparison = profile.compare(slop)
    assert comparison.deviations["significance_inflation"] > 1.0
    assert comparison.deviations["lexical_markers"] > 1.0


def test_save_and_load_round_trip(tmp_path, monkeypatch) -> None:
    import slopscore.scoring.calibrate as cal

    monkeypatch.setattr(cal, "_PROFILE_DIR", tmp_path)
    profile = build_profile("me", [_dims(t) for t in _CLEAN_DOCS], n_words=120)
    save_profile(profile)
    loaded = load_profile("me")
    assert isinstance(loaded, CalibrationProfile)
    assert loaded.n_docs == profile.n_docs
    assert load_profile("does-not-exist") is None
