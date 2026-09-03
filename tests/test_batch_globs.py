"""Batch walker include/exclude filtering (v0.11)."""

from __future__ import annotations

from pathlib import Path

from slopscore.ingest.batch import iter_paths


def _tree(tmp_path: Path) -> None:
    for rel in [
        "README.md",
        "docs/guide.md",
        "docs/api/ref.md",
        "node_modules/pkg/README.md",
        ".venv/lib/x.md",
        "build/out.md",
        "src/app.py",
        "notes.generated.md",
    ]:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("text\n")


def _rel(tmp_path: Path, paths) -> set[str]:  # type: ignore[no-untyped-def]
    return {p.relative_to(tmp_path).as_posix() for p in paths}


def test_default_excludes_prune_vendored_and_build_dirs(tmp_path: Path) -> None:
    _tree(tmp_path)
    found = _rel(tmp_path, iter_paths(tmp_path, recursive=True))
    assert "node_modules/pkg/README.md" not in found
    assert ".venv/lib/x.md" not in found
    assert "build/out.md" not in found
    assert {"README.md", "docs/guide.md", "docs/api/ref.md", "src/app.py"} <= found


def test_include_globs_limit_the_walk(tmp_path: Path) -> None:
    _tree(tmp_path)
    found = _rel(tmp_path, iter_paths(tmp_path, recursive=True, include=("docs/*",)))
    assert found == {"docs/guide.md", "docs/api/ref.md"}


def test_exclude_glob_on_files(tmp_path: Path) -> None:
    _tree(tmp_path)
    found = _rel(
        tmp_path, iter_paths(tmp_path, recursive=True, exclude=("*.generated.md", "node_modules"))
    )
    assert "notes.generated.md" not in found
    assert "node_modules/pkg/README.md" not in found
    assert "build/out.md" in found  # the default excludes were replaced


def test_non_recursive_stays_at_the_top_level(tmp_path: Path) -> None:
    _tree(tmp_path)
    assert _rel(tmp_path, iter_paths(tmp_path)) == {"README.md", "notes.generated.md"}
