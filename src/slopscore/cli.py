"""slopscore command-line interface."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from slopscore.config import Scorer, Strictness
from slopscore.core import SlopScorer
from slopscore.ingest import looks_like_url
from slopscore.ingest.batch import iter_paths
from slopscore.ingest.website import WebExtraNotInstalled
from slopscore.models import Report
from slopscore.report import render_batch, render_console, to_json, to_markdown, to_sarif
from slopscore.report.batch import build_batch_report, fail_threshold_rank, max_severity
from slopscore.scoring.model import ModelNotTrained
from slopscore.scoring.profiles import KNOWN_PROFILES

app = typer.Typer(
    help="Transparent AI-slop writing-pattern analysis. Detects slop patterns, not authorship.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


class OutputFormat(StrEnum):
    console = "console"
    json = "json"
    markdown = "markdown"
    sarif = "sarif"
    html = "html"


class FailOn(StrEnum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


def _render_single(report: Report, fmt: OutputFormat) -> str | None:
    """Return serialized text for non-console formats, or None for console (rendered directly)."""
    import json as _json

    if fmt is OutputFormat.json:
        return to_json(report)
    if fmt is OutputFormat.markdown:
        return to_markdown(report)
    if fmt is OutputFormat.sarif:
        return _json.dumps(to_sarif(report), indent=2)
    if fmt is OutputFormat.html:
        from slopscore.report.html import ReportExtraNotInstalled, to_html

        try:
            return to_html(report)
        except ReportExtraNotInstalled as exc:
            err_console.print(f"[yellow]{escape(str(exc))}[/yellow]")
            raise typer.Exit(code=3) from exc
    return None


@app.command()
def scan(
    targets: list[str] = typer.Argument(
        ..., help="One or more files, a directory, a URL, or '-' for stdin."
    ),
    profile: str | None = typer.Option(
        None, "--profile", "-p", help=f"One of: {', '.join(KNOWN_PROFILES)}."
    ),
    strictness: Strictness | None = typer.Option(None, "--strictness", "-s"),
    fmt: OutputFormat = typer.Option(OutputFormat.console, "--format", "-f"),
    json_path: str | None = typer.Option(
        None, "--json-path", help="JSONPath for JSON input, e.g. $.article.body"
    ),
    baseline: str | None = typer.Option(
        None, "--baseline", "-b", help="Compare against a personal baseline from `calibrate`."
    ),
    scorer: Scorer | None = typer.Option(
        None, "--scorer", help="Scoring engine: rules (default) or ml (learned model)."
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Explicit config file (else auto-discovered)."
    ),
    detector: str | None = typer.Option(
        None, "--detector", help="Optional authorship adapter ('reference'); reported separately."
    ),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recurse into a directory."),
    diff: str | None = typer.Option(
        None, "--diff", help="Scan only files changed vs a git ref (e.g. origin/main)."
    ),
    fail_on: FailOn = typer.Option(
        FailOn.none, "--fail-on", help="Exit non-zero if any finding reaches this severity."
    ),
    baseline_file: Path | None = typer.Option(
        None, "--baseline-file", help="A findings baseline from `slopscore-lint baseline`."
    ),
    fail_on_new: bool = typer.Option(
        False, "--fail-on-new", help="With --baseline-file: exit 1 only on findings not in it."
    ),
    suggest: bool = typer.Option(False, "--suggest", help="Include rewrite suggestions."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to a file."),
) -> None:
    """Scan a file, directory, URL, or stdin for AI-slop writing patterns."""
    from slopscore.config_file import discover_config, load_config, resolve_settings

    file_cfg = load_config(config) if config else discover_config()[0]
    settings = resolve_settings(
        file_cfg,
        profile=profile,
        strictness=strictness.value if strictness else None,
        scorer=scorer.value if scorer else None,
        suggest=suggest or None,
    )
    det = None
    if detector is not None:
        if detector != "reference":
            err_console.print(
                f"[red]Unknown detector '{detector}'. slopscore bundles only 'reference' "
                "(a no-op); plug in your own via the Python API.[/red]"
            )
            raise typer.Exit(code=2)
        from slopscore.detectors.base import ReferenceDetector

        det = ReferenceDetector()
    try:
        engine = SlopScorer(baseline=baseline, settings=settings, detector=det)
    except FileNotFoundError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    paths = _resolve_batch_paths(targets, recursive=recursive, diff=diff)
    try:
        if paths is not None:
            reports = [engine.scan_file(p) for p in paths]
            _emit_batch(reports, settings.profile, settings.strictness.value, fmt, output)
        else:
            report = _scan_single(engine, targets[0], json_path)
            _emit_single(report, fmt, output)
            reports = [report]
    except WebExtraNotInstalled as exc:
        # escape() keeps the literal "[web]" in the hint from being parsed as Rich markup.
        err_console.print(f"[yellow]{escape(str(exc))}[/yellow]")
        raise typer.Exit(code=3) from exc
    except ModelNotTrained as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=3) from exc

    if baseline_file is not None and fail_on_new:
        from slopscore.report.baseline import BaselineFile, new_findings

        known = BaselineFile.model_validate_json(baseline_file.read_text("utf-8")).as_set()
        total_new = sum(new_findings(r, known) for r in reports)
        if total_new:
            err_console.print(f"[red]{total_new} new finding(s) not in the baseline.[/red]")
            raise typer.Exit(code=1)
    elif max_severity(reports) >= fail_threshold_rank(fail_on.value):
        raise typer.Exit(code=1)


_SCANNABLE_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".json"}


def _resolve_batch_paths(
    targets: list[str], *, recursive: bool, diff: str | None
) -> list[Path] | None:
    """Return a file list for batch mode, or None for single-target (file/url/stdin)."""
    if diff is not None:
        import subprocess

        out = subprocess.run(
            ["git", "diff", "--name-only", diff],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [
            Path(line)
            for line in out.splitlines()
            if Path(line).suffix.lower() in _SCANNABLE_SUFFIXES
        ]
    if len(targets) > 1:
        return [Path(t) for t in targets]
    target = targets[0]
    if target != "-" and not looks_like_url(target) and Path(target).is_dir():
        return list(iter_paths(target, recursive=recursive))
    return None


def _scan_single(scorer: SlopScorer, target: str, json_path: str | None) -> Report:
    if target == "-":
        return scorer.scan_text(typer.get_text_stream("stdin").read(), source="<stdin>")
    if looks_like_url(target):
        return scorer.scan_url(target)
    path = Path(target)
    if not path.exists():
        err_console.print(f"[red]No such file:[/red] {target}")
        raise typer.Exit(code=2)
    return scorer.scan_file(path, json_path=json_path)


def _emit_single(report: Report, fmt: OutputFormat, output: Path | None) -> None:
    rendered = _render_single(report, fmt)
    if rendered is None:  # console
        if output is not None:
            output.write_text(f"SlopScore: {report.score.slop_score}\n", encoding="utf-8")
        else:
            render_console(report, console)
        return
    if output is not None:
        output.write_text(rendered, encoding="utf-8")
        console.print(f"[dim]wrote {fmt.value} report to {output}[/dim]")
    elif fmt is OutputFormat.json or fmt is OutputFormat.sarif:
        console.print_json(rendered)
    else:
        console.print(rendered)


def _emit_batch(
    reports: list[Report], profile: str, strictness: str, fmt: OutputFormat, output: Path | None
) -> None:
    import json as _json

    if fmt is OutputFormat.sarif:
        text = _json.dumps(to_sarif(reports), indent=2)
    elif fmt is OutputFormat.json:
        text = build_batch_report(reports, profile, strictness).to_json()
    else:
        text = None  # console summary

    if text is None:
        render_batch(build_batch_report(reports, profile, strictness), console)
    elif output is not None:
        output.write_text(text, encoding="utf-8")
        console.print(f"[dim]wrote {fmt.value} report for {len(reports)} files to {output}[/dim]")
    else:
        console.print_json(text)


@app.command()
def calibrate(
    corpus: str = typer.Argument(..., help="Directory of your own writing to baseline against."),
    name: str = typer.Option(..., "--name", "-n", help="Name to save the baseline under."),
    profile: str = typer.Option("blog", "--profile", "-p"),
    recursive: bool = typer.Option(False, "--recursive", "-r"),
) -> None:
    """Build a personal baseline from your past writing, so scans flag deviations from *your*
    style rather than generic patterns. Use it later with `scan --baseline <name>`."""
    from slopscore.core import build_document
    from slopscore.ingest import from_path
    from slopscore.ingest.batch import iter_paths
    from slopscore.scoring.calibrate import build_profile, save_profile
    from slopscore.scoring.scorer import score_document

    root = Path(corpus)
    if not root.is_dir():
        err_console.print(f"[red]Not a directory:[/red] {corpus}")
        raise typer.Exit(code=2)

    settings = SlopScorer(profile=profile).settings
    per_doc = []
    total_words = 0
    for path in iter_paths(root, recursive=recursive):
        doc = build_document(from_path(path))
        if doc.word_count < 50:  # skip stubs; too short to characterize style
            continue
        report = score_document(doc, settings)
        per_doc.append(report.dimensions)
        total_words += doc.word_count

    if not per_doc:
        err_console.print("[red]No scannable documents (>=50 words) found.[/red]")
        raise typer.Exit(code=2)

    prof = build_profile(name, per_doc, total_words)
    saved = save_profile(prof)
    note = " (small corpus: robust median/MAD stats)" if prof.robust else ""
    if prof.n_docs < 10 or total_words < 5000:
        err_console.print(
            f"[yellow]Small corpus ({prof.n_docs} docs, {total_words} words): "
            "baseline will be noisy.[/yellow]"
        )
    console.print(
        f"Saved baseline [cyan]{name}[/cyan]: {prof.n_docs} docs, {total_words} words{note}\n"
        f"  -> {saved}\n  Use it with: slopscore-lint scan FILE --baseline {name}"
    )


@app.command(name="baseline")
def baseline_cmd(
    targets: list[str] = typer.Argument(..., help="Files or directories to baseline."),
    profile: str | None = typer.Option(None, "--profile", "-p"),
    recursive: bool = typer.Option(False, "--recursive", "-r"),
    output: Path = typer.Option(
        Path(".slopscore-baseline.json"), "--output", "-o", help="Where to write the baseline."
    ),
) -> None:
    """Record current findings as a baseline so future scans fail only on NEW findings."""
    from slopscore.config_file import discover_config, resolve_settings
    from slopscore.report.baseline import build_baseline

    settings = resolve_settings(discover_config()[0], profile=profile)
    engine = SlopScorer(settings=settings)
    paths = _resolve_batch_paths(targets, recursive=recursive, diff=None)
    files = paths if paths is not None else [Path(targets[0])]
    reports = [engine.scan_file(p) for p in files]
    baseline = build_baseline(reports)
    output.write_text(baseline.to_json(), encoding="utf-8")
    console.print(
        f"Wrote baseline ({len(baseline.fingerprints)} findings across {len(files)} files) "
        f"-> {output}\n  Use it with: "
        f"slopscore-lint scan ... --baseline-file {output} --fail-on-new"
    )


@app.command(name="config")
def config_cmd() -> None:
    """Show the effective configuration (merged from slopscore.toml / pyproject.toml + defaults)."""
    from slopscore.config_file import discover_config, resolve_settings

    file_cfg, source = discover_config()
    settings = resolve_settings(file_cfg)
    console.print(f"[bold]Config source:[/bold] {source or '(none — built-in defaults)'}")
    console.print_json(settings.model_dump_json(indent=2))


@app.command(name="eval")
def eval_cmd(
    dataset: Path | None = typer.Option(
        None, "--dataset", help="Labeled JSONL (text,label). Defaults to the committed seed set."
    ),
    profile: str = typer.Option("blog", "--profile", "-p"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write JSON metrics here."),
) -> None:
    """Evaluate both scorers (rules and ml) on a labeled set: TPR@FPR, PR-AUC, calibration, and
    per-subgroup false-positive rates. Reports honest numbers and the replace-if-wins decision."""
    import json as _json

    from slopscore.eval.datasets import load_jsonl, load_seed
    from slopscore.eval.harness import evaluate, should_promote
    from slopscore.scoring.model import model_available

    rows = load_jsonl(dataset) if dataset else load_seed()
    results = {"rules": evaluate(rows, profile=profile, scorer="rules")}
    if model_available():
        results["ml"] = evaluate(rows, profile=profile, scorer="ml")

    for kind, res in results.items():
        m = res["metrics"]
        console.print(
            f"[bold]{kind}[/bold]  TPR@1%FPR {m['tpr_at_1fpr']:.3f}  "
            f"TPR@5%FPR {m['tpr_at_5fpr']:.3f}  PR-AUC {m['pr_auc']:.3f}  "
            f"ECE {m['ece']:.3f}  Brier {m['brier']:.3f}"
        )
        for grp, fr in res["fairness"].items():
            console.print(
                f"    [dim]{grp}: FPR {fr['fpr']:.2f}  abstain {fr['abstention_rate']:.2f} "
                f"(n={fr['n']})[/dim]"
            )

    if "ml" in results:
        if dataset is None:
            console.print(
                "[yellow]Note: ml metrics on the seed set are in-sample (the model trained on "
                "it); see training out-of-fold numbers in MODEL_CARD.md.[/yellow]"
            )
        promote = should_promote(results["rules"], results["ml"])
        console.print(
            f"\nReplace-if-wins (TPR@1%FPR + no subgroup-FPR regression): ml "
            f"{'WOULD' if promote else 'does NOT'} qualify -> default stays "
            f"[bold]{'ml' if promote else 'rules'}[/bold]."
        )

    if output is not None:
        output.write_text(_json.dumps(results, indent=2, default=str), encoding="utf-8")
        console.print(f"[dim]wrote metrics to {output}[/dim]")


if __name__ == "__main__":
    app()
