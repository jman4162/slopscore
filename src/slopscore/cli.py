"""slopscore command-line interface."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from slopscore.config import Strictness
from slopscore.core import SlopScorer
from slopscore.ingest import looks_like_url
from slopscore.ingest.batch import iter_paths
from slopscore.ingest.website import WebExtraNotInstalled
from slopscore.models import Report
from slopscore.report import render_batch, render_console, to_json, to_markdown, to_sarif
from slopscore.report.batch import build_batch_report, fail_threshold_rank, max_severity
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
    profile: str = typer.Option(
        "blog", "--profile", "-p", help=f"One of: {', '.join(KNOWN_PROFILES)}."
    ),
    strictness: Strictness = typer.Option(Strictness.conservative, "--strictness", "-s"),
    fmt: OutputFormat = typer.Option(OutputFormat.console, "--format", "-f"),
    json_path: str | None = typer.Option(
        None, "--json-path", help="JSONPath for JSON input, e.g. $.article.body"
    ),
    baseline: str | None = typer.Option(
        None, "--baseline", "-b", help="Compare against a personal baseline from `calibrate`."
    ),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recurse into a directory."),
    diff: str | None = typer.Option(
        None, "--diff", help="Scan only files changed vs a git ref (e.g. origin/main)."
    ),
    fail_on: FailOn = typer.Option(
        FailOn.none, "--fail-on", help="Exit non-zero if any finding reaches this severity."
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write report to a file."),
) -> None:
    """Scan a file, directory, URL, or stdin for AI-slop writing patterns."""
    try:
        scorer = SlopScorer(profile=profile, strictness=strictness, baseline=baseline)
    except FileNotFoundError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc

    paths = _resolve_batch_paths(targets, recursive=recursive, diff=diff)
    try:
        if paths is not None:
            reports = [scorer.scan_file(p) for p in paths]
            _emit_batch(reports, profile, strictness.value, fmt, output)
        else:
            report = _scan_single(scorer, targets[0], json_path)
            _emit_single(report, fmt, output)
            reports = [report]
    except WebExtraNotInstalled as exc:
        # escape() keeps the literal "[web]" in the hint from being parsed as Rich markup.
        err_console.print(f"[yellow]{escape(str(exc))}[/yellow]")
        raise typer.Exit(code=3) from exc

    if max_severity(reports) >= fail_threshold_rank(fail_on.value):
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
        f"  -> {saved}\n  Use it with: slopscore scan FILE --baseline {name}"
    )


if __name__ == "__main__":
    app()
