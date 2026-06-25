"""Rich console report."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from slopscore.models import Label, Report
from slopscore.report.batch import BatchReport
from slopscore.report.markdown import _DIMENSION_LABELS

_LABEL_STYLE: dict[Label, str] = {
    Label.low: "green",
    Label.mild: "yellow",
    Label.elevated: "dark_orange",
    Label.severe: "red",
}


def render_batch(batch: BatchReport, console: Console | None = None) -> None:
    console = console or Console()
    s = batch.summary
    console.print(
        Panel(
            Text.assemble(
                ("slopscore batch", "bold"),
                (
                    f"  {s.total_files} files · {s.total_findings} findings · "
                    f"profile {batch.profile}",
                    "dim",
                ),
            ),
            expand=False,
        )
    )
    dist = "  ".join(f"{lbl}:{n}" for lbl, n in sorted(s.by_label.items()))
    console.print(f"[bold]Labels[/bold]  {dist or '(none)'}")
    if s.worst:
        console.print("\n[bold]Worst files[/bold]")
        for f in s.worst:
            style = _LABEL_STYLE[f.label]
            mark = " (abstained)" if f.abstained else ""
            console.print(f"  [{style}]{f.slop_score:>5}[/] {f.label.value:<8} {f.path}{mark}")


def render(report: Report, console: Console | None = None) -> None:
    console = console or Console()
    s = report.score
    style = _LABEL_STYLE[s.label]

    header = Text.assemble(
        ("SlopScore ", "bold"),
        (f"{s.slop_score}/100 ", f"bold {style}"),
        (f"({s.label.value})", style),
    )
    if s.abstained:
        header.append("  ABSTAINED", style="bold yellow")
    meta = (
        f"confidence {s.confidence}  ·  profile {report.input.profile}  ·  "
        f"strictness {s.strictness}  ·  {report.input.word_count} words  ·  "
        f"{report.input.language}"
    )
    body = Text.assemble(header, "\n", (meta, "dim"))
    if s.abstained and s.abstention_reason:
        body.append("\n" + s.abstention_reason, style="yellow")
    console.print(Panel(body, expand=False))

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
            fix = ""
            if e.suggestion is not None:
                target = "delete" if e.suggestion.text == "" else f"→ '{e.suggestion.text}'"
                fix = f" [green]suggest {target}[/green]"
            console.print(
                f"  [dim]{e.start_char:>5}[/dim] [cyan]{e.rule_id}[/cyan] "
                f"[{_sev_style(e.severity.value)}]{e.severity.value}[/]: "
                f'"{snippet}" [dim]— {e.explanation}[/dim]{fix}'
            )

    if report.baseline is not None:
        top = sorted(report.baseline.deviations.items(), key=lambda kv: abs(kv[1]), reverse=True)[
            :5
        ]
        console.print(
            f"\n[bold]Deviation from baseline '{report.baseline.profile_name}'[/bold] (z-score)"
        )
        for dim, z in top:
            mark = "red" if abs(z) >= 2 else "yellow" if abs(z) >= 1 else "dim"
            console.print(f"  [{mark}]{z:+.1f}σ[/]  {dim}")

    if report.authorship is not None:
        a = report.authorship
        console.print(
            f"\n[bold]Authorship signal[/bold] [dim](separate; not part of the score)[/dim]: "
            f"{a.score:.2f} via {a.method}"
        )
        console.print(f"  [yellow]{a.caveat}[/yellow]")

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
