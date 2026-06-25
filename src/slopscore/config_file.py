"""Project configuration files: ``slopscore.toml`` and ``[tool.slopscore]`` in ``pyproject.toml``.

Resolution precedence (highest first): CLI args > ``slopscore.toml`` > ``pyproject.toml``
[tool.slopscore] > built-in defaults. This module only loads the *file* layer; the CLI applies
the CLI-over-file precedence. Read-only via the stdlib ``tomllib`` (Python 3.11+), so no new
dependency.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

# Keys recognized in a config file (others are ignored with no error, like ruff).
_KEYS = {
    "profile",
    "strictness",
    "scorer",
    "min_reliable_words",
    "score_threshold",
    "fail_on",
    "disabled_dimensions",
    "disabled_rules",
    "rule_severity",
    "include",
    "exclude",
}


def _from_pyproject(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    section = data.get("tool", {}).get("slopscore", {})
    return dict(section) if isinstance(section, dict) else {}


def _from_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return dict(tomllib.load(fh))


def discover_config(start: Path | None = None) -> tuple[dict[str, Any], Path | None]:
    """Find the nearest config by walking up from ``start`` (default: cwd).

    Returns ``(config, source_path)``. ``slopscore.toml`` overrides ``pyproject.toml`` in the same
    directory; the search stops at the first directory that has either file.
    """
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        toml = directory / "slopscore.toml"
        pyproject = directory / "pyproject.toml"
        cfg: dict[str, Any] = {}
        source: Path | None = None
        if pyproject.is_file():
            section = _from_pyproject(pyproject)
            if section:
                cfg, source = section, pyproject
        if toml.is_file():
            cfg, source = {**cfg, **_from_toml(toml)}, toml
        if source is not None:
            return _clean(cfg), source
    return {}, None


def load_config(path: Path) -> dict[str, Any]:
    """Load an explicit config file (``--config``)."""
    if path.name == "pyproject.toml":
        return _clean(_from_pyproject(path))
    return _clean(_from_toml(path))


def _clean(cfg: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in cfg.items() if k in _KEYS}


def resolve_settings(
    file_cfg: dict[str, Any],
    *,
    profile: str | None = None,
    strictness: str | None = None,
    scorer: str | None = None,
    suggest: bool | None = None,
) -> Any:
    """Merge a file-config dict with explicit CLI overrides (None = not set) into a Settings.

    Precedence per field: CLI override > file config > built-in default.
    """
    from slopscore.config import Scorer, Settings, Strictness

    return Settings(
        profile=profile or file_cfg.get("profile") or "blog",
        strictness=Strictness(strictness or file_cfg.get("strictness") or "conservative"),
        scorer=Scorer(scorer or file_cfg.get("scorer") or "rules"),
        min_reliable_words=int(file_cfg.get("min_reliable_words", 300)),
        disabled_dimensions=_str_set(file_cfg, "disabled_dimensions"),
        disabled_rules=_str_set(file_cfg, "disabled_rules"),
        rule_severity=dict(file_cfg.get("rule_severity", {}) or {}),
        suggest=bool(suggest if suggest is not None else file_cfg.get("suggest", False)),
    )


def _str_set(cfg: dict[str, Any], key: str) -> frozenset[str]:
    """Read a config list of strings, rejecting a bare string (which would silently iterate into
    per-character entries)."""
    value = cfg.get(key, [])
    if isinstance(value, str):
        raise ValueError(f"`{key}` must be a list of strings, not a string ({value!r}).")
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ValueError(f"`{key}` must be a list of strings, got {type(value).__name__}.")
    return frozenset(str(v) for v in value)
