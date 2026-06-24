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
from slopscore.ingest.website import WebExtraNotInstalled
from slopscore.report import render_console, to_json, to_markdown
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


@app.command()
def scan(
    target: str = typer.Argument(..., help="File path, URL, or '-' to read stdin."),
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
) -> None:
    """Scan a file, URL, or stdin for AI-slop writing patterns."""
    try:
        scorer = SlopScorer(profile=profile, strictness=strictness, baseline=baseline)
    except FileNotFoundError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    try:
        if target == "-":
            report = scorer.scan_text(typer.get_text_stream("stdin").read(), source="<stdin>")
        elif looks_like_url(target):
            report = scorer.scan_url(target)
        else:
            path = Path(target)
            if not path.exists():
                err_console.print(f"[red]No such file:[/red] {target}")
                raise typer.Exit(code=2)
            report = scorer.scan_file(path, json_path=json_path)
    except WebExtraNotInstalled as exc:
        # escape() keeps the literal "[web]" in the hint from being parsed as Rich markup.
        err_console.print(f"[yellow]{escape(str(exc))}[/yellow]")
        raise typer.Exit(code=3) from exc

    if fmt is OutputFormat.json:
        console.print_json(to_json(report))
    elif fmt is OutputFormat.markdown:
        console.print(to_markdown(report))
    else:
        render_console(report, console)


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
