"""The v0.11 CI gate: severity, score, config keys, and their interaction with abstention."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from slopscore.cli import app

runner = CliRunner()

SLOP = (
    "In today's fast-paced digital landscape, it is crucial to leverage robust tools. Let's "
    "delve into the details. At its core, innovation underscores transformative potential. "
    "It is not just a tool, it is a revolution. Experts argue that it stands as a testament "
    "to modern engineering and plays a pivotal role in shaping the future. "
) * 4
CLEAN = (
    "The Golden Gate Bridge opened in 1937 after four years of construction. Workers poured "
    "389,000 cubic yards of concrete into its towers. The original toll was 50 cents each way. "
    "The two towers rise 746 feet above the water. Eleven workers died during the build. "
) * 3


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def test_fail_on_score_exits_1_on_slop_and_0_on_clean(tmp_path: Path) -> None:
    slop, clean = _write(tmp_path, "slop.md", SLOP), _write(tmp_path, "clean.md", CLEAN)
    assert runner.invoke(app, ["scan", str(slop), "--fail-on-score", "50"]).exit_code == 1
    assert runner.invoke(app, ["scan", str(clean), "--fail-on-score", "50"]).exit_code == 0


def test_abstained_document_never_fails_on_score(tmp_path: Path) -> None:
    short = _write(tmp_path, "short.md", "Let's delve into this robust, transformative tapestry.")
    result = runner.invoke(app, ["scan", str(short), "--fail-on-score", "10"])
    assert result.exit_code == 0


def test_score_gate_message_names_the_file(tmp_path: Path) -> None:
    slop = _write(tmp_path, "slop.md", SLOP)
    result = runner.invoke(app, ["scan", str(slop), "--fail-on-score", "50", "--format", "json"])
    assert result.exit_code == 1
    assert "slop.md" in result.output


def test_config_file_gate_keys_are_honored(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _write(tmp_path, "slop.md", SLOP)
    (tmp_path / "slopscore.toml").write_text(
        'score_threshold = 50\nfail_on = "high"\nsuggest = true\n'
    )
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["scan", "slop.md", "--format", "json"])
    assert result.exit_code == 1
    assert "SUGGEST_" in result.output or "score 50" in result.output
    shown = runner.invoke(app, ["config"])
    assert '"suggest": true' in shown.output
    assert '"score_threshold": 50.0' in shown.output


def test_invalid_fail_on_in_config_is_a_usage_error(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _write(tmp_path, "a.md", CLEAN)
    (tmp_path / "slopscore.toml").write_text('fail_on = "critical"\n')
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["scan", "a.md"]).exit_code == 2


def test_severity_gate_still_works(tmp_path: Path) -> None:
    slop = _write(tmp_path, "slop.md", SLOP)
    assert runner.invoke(app, ["scan", str(slop), "--fail-on", "high"]).exit_code == 1
    assert runner.invoke(app, ["scan", str(slop)]).exit_code == 0
