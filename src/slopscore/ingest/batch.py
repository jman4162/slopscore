"""Directory / recursive batch ingestion. STUB — implemented in v0.2."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from slopscore.ingest.code import CODE_SUFFIXES

_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".json"} | CODE_SUFFIXES


def iter_paths(root: str | Path, *, recursive: bool = False) -> Iterator[Path]:
    """Yield scannable files under ``root``.

    The walk is implemented; wiring it into a batch report (aggregate scoring across files)
    is deferred to v0.2.
    """
    base = Path(root)
    paths = base.rglob("*") if recursive else base.glob("*")
    for p in sorted(paths):
        if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES:
            yield p
