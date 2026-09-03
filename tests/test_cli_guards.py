"""CLI guard rails added in v0.9.2: usage errors exit 2, never a silent 0 or a traceback."""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from slopscore.cli import app

runner = CliRunner()


def test_fail_on_new_without_baseline_file_is_a_usage_error(tmp_path: Path) -> None:
    src = tmp_path / "a.md"
    src.write_text("Let's delve into this. In conclusion, it is a game-changer.\n" * 20)
    result = runner.invoke(app, ["scan", str(src), "--fail-on-new"])
    assert result.exit_code == 2
    # Rich styles the usage error on a terminal-like CI runner; strip the escapes before matching.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--baseline-file" in plain


def test_directory_among_multiple_targets_is_walked(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("The bridge opened in 1937. It cost 35 million dollars.\n")
    sub = tmp_path / "docs"
    sub.mkdir()
    (sub / "b.md").write_text("Workers poured 389,000 cubic yards of concrete.\n")
    result = runner.invoke(app, ["scan", str(tmp_path / "a.md"), str(sub), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert "b.md" in result.output and "a.md" in result.output


def test_diff_with_bad_ref_exits_2_with_message(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    result = runner.invoke(app, ["scan", ".", "--diff", "no-such-ref-xyz"])
    assert result.exit_code == 2
    assert "git diff" in result.output
