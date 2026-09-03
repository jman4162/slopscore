"""Directory / recursive batch ingestion with include/exclude filtering."""

from __future__ import annotations

import os
from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import Path

from slopscore.config import DEFAULT_EXCLUDES
from slopscore.ingest.code import CODE_SUFFIXES

_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".json"} | CODE_SUFFIXES


def _matches(rel: str, name: str, patterns: tuple[str, ...]) -> bool:
    """A pattern matches by bare name ("node_modules"), by root-relative path glob
    ("docs/**", "*.generated.md"), or by any path prefix so "build" also skips "build/x/y.md"."""
    for pat in patterns:
        if name == pat or fnmatch(name, pat) or fnmatch(rel, pat):
            return True
        if "/" not in pat and any(part == pat for part in rel.split("/")):
            return True
    return False


def iter_paths(
    root: str | Path,
    *,
    recursive: bool = False,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = DEFAULT_EXCLUDES,
) -> Iterator[Path]:
    """Yield scannable files under ``root``.

    Excluded directories are pruned during the walk (never entered), so a repository with a large
    ``node_modules`` or ``.venv`` is not traversed. ``include`` is applied to files only: when
    non-empty, a file must match one include pattern to be yielded.
    """
    base = Path(root)
    for dirpath, dirnames, filenames in os.walk(base):
        rel_dir = Path(dirpath).relative_to(base).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir
        dirnames[:] = sorted(
            d for d in dirnames if not _matches(f"{rel_dir}/{d}" if rel_dir else d, d, exclude)
        )
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if _matches(rel, name, exclude):
                continue
            if include and not _matches(rel, name, include):
                continue
            yield p
        if not recursive:
            break
