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
) -> None:
    """Scan a file, URL, or stdin for AI-slop writing patterns."""
    scorer = SlopScorer(profile=profile, strictness=strictness)
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
    profile: str = typer.Option("custom", "--profile", "-p"),
) -> None:
    """Build a personal baseline profile from your past writing. (Coming in v0.2.)"""
    err_console.print(
        "[yellow]`calibrate` is planned for v0.2[/yellow] — it will baseline your own corpus "
        f"({corpus!r}) so scans flag deviations from your style, not generic patterns."
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
