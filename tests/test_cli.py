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


def test_calibrate_builds_and_scan_uses_baseline(tmp_path: Path, monkeypatch) -> None:
    import slopscore.scoring.calibrate as cal

    monkeypatch.setattr(cal, "_PROFILE_DIR", tmp_path / "profiles")
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.txt").write_text(
        "The shop opened in 1998 on Pine Street. It sold about 200 records a week. "
        "I worked there three years and learned to grade vinyl by eye. Dave kept a "
        "ledger in pencil and never trusted the register. We sorted jazz on Tuesdays. "
        "Most customers paid cash and argued about which pressing sounded better, and "
        "a few drove in from two towns over just to flip through the dollar bins.",
        encoding="utf-8",
    )
    (corpus / "b.txt").write_text(
        "We drove to Bend in October. The pass was icy near the summit and the wipers "
        "froze twice on the way up. Gas cost three dollars and we split a sandwich at "
        "a diner outside Sisters. The motel had one working heater that night. In the "
        "morning the truck would not start until I cleaned the battery terminals with "
        "a wire brush I found in the bed under a tarp.",
        encoding="utf-8",
    )
    build = runner.invoke(app, ["calibrate", str(corpus), "--name", "me"])
    assert build.exit_code == 0
    assert (tmp_path / "profiles" / "me.json").exists()

    target = tmp_path / "post.txt"
    target.write_text(
        "This transformative platform stands as a testament to innovation, leveraging a "
        "robust, holistic tapestry and underscoring its enduring significance throughout.",
        encoding="utf-8",
    )
    scan_out = runner.invoke(app, ["scan", str(target), "--baseline", "me", "--format", "json"])
    assert scan_out.exit_code == 0
    payload = json.loads(scan_out.stdout)
    assert payload["baseline"]["profile_name"] == "me"


def test_scan_unknown_baseline_errors(tmp_path: Path) -> None:
    target = tmp_path / "x.txt"
    target.write_text("hello world", encoding="utf-8")
    result = runner.invoke(app, ["scan", str(target), "--baseline", "nope-not-here"])
    assert result.exit_code == 2


def test_fail_on_exits_nonzero_for_slop(tmp_path: Path, slop_text: str) -> None:
    p = _write(tmp_path, "slop.txt", slop_text)
    assert runner.invoke(app, ["scan", str(p), "--fail-on", "medium"]).exit_code == 1


def test_fail_on_exits_zero_for_clean(tmp_path: Path, clean_text: str) -> None:
    p = _write(tmp_path, "clean.txt", clean_text)
    assert runner.invoke(app, ["scan", str(p), "--fail-on", "high"]).exit_code == 0


def test_batch_directory_json(tmp_path: Path, slop_text: str, clean_text: str) -> None:
    _write(tmp_path, "a.txt", slop_text)
    _write(tmp_path, "b.txt", clean_text)
    result = runner.invoke(app, ["scan", str(tmp_path), "--recursive", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["total_files"] == 2


def test_sarif_format_valid(tmp_path: Path, slop_text: str) -> None:
    p = _write(tmp_path, "slop.txt", slop_text)
    result = runner.invoke(app, ["scan", str(p), "--format", "sarif"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["version"] == "2.1.0"


def test_baseline_then_fail_on_new(tmp_path: Path) -> None:
    base_text = "Everyone knows this stands as a testament to innovation."
    src = _write(tmp_path, "a.txt", base_text)
    bl = tmp_path / "baseline.json"
    assert runner.invoke(app, ["baseline", str(src), "-o", str(bl)]).exit_code == 0
    assert bl.is_file()
    # Unchanged input: no new findings -> exit 0.
    unchanged = runner.invoke(app, ["scan", str(src), "--baseline-file", str(bl), "--fail-on-new"])
    assert unchanged.exit_code == 0
    # A new finding -> exit 1.
    src.write_text(base_text + " In an increasingly digital world, teams must adapt.", "utf-8")
    changed = runner.invoke(app, ["scan", str(src), "--baseline-file", str(bl), "--fail-on-new"])
    assert changed.exit_code == 1


def test_output_creates_parent_dirs(tmp_path: Path, slop_text: str) -> None:
    path = _write(tmp_path, "slop.txt", slop_text)
    out = tmp_path / "nested" / "deep" / "report.json"
    result = runner.invoke(app, ["scan", str(path), "--format", "json", "-o", str(out)])
    assert result.exit_code == 0
    assert out.is_file()
    json.loads(out.read_text("utf-8"))


def test_malformed_baseline_file_exits_2(tmp_path: Path, slop_text: str) -> None:
    path = _write(tmp_path, "slop.txt", slop_text)
    bad = _write(tmp_path, "bad.json", "{not valid json")
    result = runner.invoke(app, ["scan", str(path), "--baseline-file", str(bad), "--fail-on-new"])
    assert result.exit_code == 2


def test_string_disabled_rules_in_config_errors(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "slopscore.toml").write_text('disabled_rules = "FOO"\n', encoding="utf-8")
    path = _write(tmp_path, "slop.txt", "Everyone knows this is the future.")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["scan", str(path)])
    assert result.exit_code == 2  # invalid config is a usage error
