"""Config files: discovery, precedence, and dimension disabling."""

from __future__ import annotations

from pathlib import Path

from slopscore import scan_text
from slopscore.config_file import discover_config, load_config, resolve_settings
from slopscore.core import SlopScorer


def test_slopscore_toml_overrides_pyproject(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.slopscore]\nprofile = "academic"\n', encoding="utf-8"
    )
    (tmp_path / "slopscore.toml").write_text('profile = "technical"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg, source = discover_config()
    assert cfg["profile"] == "technical"  # slopscore.toml wins
    assert source.name == "slopscore.toml"


def test_cli_override_beats_file() -> None:
    cfg = {"profile": "academic", "strictness": "sensitive"}
    settings = resolve_settings(cfg, profile="marketing")
    assert settings.profile == "marketing"  # CLI override
    assert settings.strictness.value == "sensitive"  # from file


def test_defaults_when_no_file() -> None:
    settings = resolve_settings({})
    assert settings.profile == "blog"
    assert settings.strictness.value == "conservative"
    assert settings.scorer.value == "rules"


def test_explicit_config_file(tmp_path: Path) -> None:
    p = tmp_path / "myconf.toml"
    p.write_text('disabled_rules = ["LEXICAL_OVERPOLISHED_VERBS"]\n', encoding="utf-8")
    cfg = load_config(p)
    assert "LEXICAL_OVERPOLISHED_VERBS" in cfg["disabled_rules"]


def test_disabled_dimension_zeroes_score() -> None:
    text = (
        "This transformative platform leverages a comprehensive, holistic ecosystem to foster "
        "synergy and unlock seamless value across the evolving landscape of the industry today."
    )
    base = scan_text(text)
    settings = resolve_settings({"disabled_dimensions": ["lexical_markers"]})
    disabled = SlopScorer(settings=settings).scan_text(text)
    assert base.dimensions.lexical_markers > 0
    assert disabled.dimensions.lexical_markers == 0.0
    # No lexical findings survive when the dimension is off.
    assert not any(e.rule_id.startswith("LEXICAL_") for e in disabled.evidence)


def test_string_disabled_rules_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="list of strings"):
        resolve_settings({"disabled_rules": "FOO"})


def test_string_disabled_dimensions_rejected() -> None:
    import pytest

    with pytest.raises(ValueError, match="list of strings"):
        resolve_settings({"disabled_dimensions": "genericity"})


def test_list_disabled_rules_ok() -> None:
    settings = resolve_settings({"disabled_rules": ["A", "B"]})
    assert settings.disabled_rules == frozenset({"A", "B"})
