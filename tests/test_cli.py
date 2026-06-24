"""CLI smoke tests via Typer's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from slopscore.cli import app

runner = CliRunner()


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_scan_console(tmp_path: Path, slop_text: str) -> None:
    path = _write(tmp_path, "slop.txt", slop_text)
    result = runner.invoke(app, ["scan", str(path)])
    assert result.exit_code == 0
    assert "SlopScore" in result.stdout


def test_scan_json_is_valid(tmp_path: Path, slop_text: str) -> None:
    path = _write(tmp_path, "slop.txt", slop_text)
    result = runner.invoke(app, ["scan", str(path), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["score"]["label"] == "severe"
    assert payload["input"]["word_count"] > 0


def test_clean_text_is_low(tmp_path: Path, clean_text: str) -> None:
    path = _write(tmp_path, "clean.txt", clean_text)
    result = runner.invoke(app, ["scan", str(path), "--format", "json"])
    payload = json.loads(result.stdout)
    assert payload["score"]["slop_score"] < 50


def test_missing_file_exits_2() -> None:
    result = runner.invoke(app, ["scan", "/no/such/file.txt"])
    assert result.exit_code == 2


def test_url_without_web_extra_hints(monkeypatch) -> None:
    # Simulate the [web] extra being absent.
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "trafilatura":
            raise ImportError("no trafilatura")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = runner.invoke(app, ["scan", "https://example.com/post"])
    # Exit code 3 is the dedicated "install the [web] extra" signal. The hint text itself is
    # asserted in test_website_hint (Rich writes it to a stderr CliRunner doesn't capture).
    assert result.exit_code == 3


def test_calibrate_is_stub(tmp_path: Path) -> None:
    result = runner.invoke(app, ["calibrate", str(tmp_path)])
    assert result.exit_code == 1
