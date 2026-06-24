"""Rich console report."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from slopscore.models import Label, Report
from slopscore.report.markdown import _DIMENSION_LABELS

_LABEL_STYLE: dict[Label, str] = {
    Label.low: "green",
    Label.mild: "yellow",
    Label.elevated: "dark_orange",
    Label.severe: "red",
}


def render(report: Report, console: Console | None = None) -> None:
    console = console or Console()
    s = report.score
    style = _LABEL_STYLE[s.label]

    header = Text.assemble(
        ("SlopScore ", "bold"),
        (f"{s.slop_score}/100 ", f"bold {style}"),
        (f"({s.label.value})", style),
    )
    meta = (
        f"confidence {s.confidence}  ·  profile {report.input.profile}  ·  "
        f"strictness {s.strictness}  ·  {report.input.word_count} words  ·  "
        f"{report.input.language}"
    )
    console.print(Panel(Text.assemble(header, "\n", (meta, "dim")), expand=False))

    table = Table(title="Dimensions", show_edge=False, pad_edge=False)
    table.add_column("Dimension")
    table.add_column("Score", justify="right")
    dims = report.dimensions.model_dump()
    for key, label in _DIMENSION_LABELS.items():
        value = dims.get(key)
        if value is None:
            continue
        bar = "█" * round(value * 10)
        table.add_row(label, f"[{_bar_style(value)}]{value:.2f} {bar}[/]")
    console.print(table)

    if report.evidence:
        console.print("\n[bold]Evidence[/bold]")
        for e in report.evidence[:25]:
            snippet = e.span.replace("\n", " ").strip()
            console.print(
                f"  [dim]{e.start_char:>5}[/dim] [cyan]{e.rule_id}[/cyan] "
                f"[{_sev_style(e.severity.value)}]{e.severity.value}[/]: "
                f'"{snippet}" [dim]— {e.explanation}[/dim]'
            )

    console.print()
    for w in report.warnings:
        console.print(f"[dim]> {w}[/dim]")


def _bar_style(value: float) -> str:
    if value >= 0.66:
        return "red"
    if value >= 0.33:
        return "yellow"
    return "green"


def _sev_style(severity: str) -> str:
    return {"high": "red", "medium": "yellow", "low": "dim"}.get(severity, "white")
