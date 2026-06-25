"""The committed v0.5 benchmark and the fetch source registry stay well-formed."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from slopscore.eval.datasets import load_jsonl

_ROOT = Path(__file__).resolve().parents[1]
_BENCHMARK = _ROOT / "eval" / "datasets" / "benchmark.jsonl"


def test_benchmark_schema_valid() -> None:
    rows = load_jsonl(_BENCHMARK)
    assert len(rows) >= 100
    for r in rows:
        assert r.label in (0, 1)
        assert r.text.strip()
        assert r.bucket and r.subgroup


def test_benchmark_has_fairness_slices() -> None:
    rows = load_jsonl(_BENCHMARK)
    subgroups = {r.subgroup for r in rows}
    assert {"general", "simple_english", "non_native"} <= subgroups
    # the non_native slice is mostly clean: it measures false positives on competent ESL writing
    non_native = [r for r in rows if r.subgroup == "non_native"]
    assert sum(1 for r in non_native if r.label == 0) >= len(non_native) // 2


def _load_fetch():
    spec = importlib.util.spec_from_file_location("fetch", _ROOT / "scripts" / "eval" / "fetch.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclass needs the module registered to resolve annotations
    spec.loader.exec_module(mod)
    return mod


def test_eval_only_sources_are_not_train_eligible() -> None:
    sources = _load_fetch().SOURCES
    # Subjective or non-commercial sources must never be marked train-eligible.
    for name in ("wiki_aicleanup", "hc3"):
        assert sources[name].train_eligible is False
