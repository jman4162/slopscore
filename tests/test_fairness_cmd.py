"""The fairness-audit command reports per-rule false positives on the plain/ESL slices."""

from __future__ import annotations

from typer.testing import CliRunner

from slopscore.cli import app

runner = CliRunner()


def test_fairness_runs_and_reports_slices() -> None:
    result = runner.invoke(app, ["fairness"])
    assert result.exit_code == 0
    assert "simple_english" in result.stdout
    assert "non_native" in result.stdout
    assert "FPR" in result.stdout


def test_fairness_threshold_option() -> None:
    # A very low threshold must not crash and still produces output.
    result = runner.invoke(app, ["fairness", "--threshold", "0.01"])
    assert result.exit_code == 0
