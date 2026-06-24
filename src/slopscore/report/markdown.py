"""Markdown report."""

from __future__ import annotations

from slopscore.models import Dimension, Report

_DIMENSION_LABELS: dict[str, str] = {
    Dimension.lexical_markers.value: "AI-marker phrase density",
    Dimension.formulaic_structure.value: "Formulaic structure",
    Dimension.significance_inflation.value: "Significance inflation",
    Dimension.superficial_analysis.value: "Superficial '-ing' analysis",
    Dimension.weasel_attribution.value: "Vague / over-attribution",
    Dimension.parallelism.value: "Negative parallelism / rule of three",
    Dimension.copula_avoidance.value: "Copula avoidance",
    Dimension.genericity.value: "Genericity / low specificity",
    Dimension.redundancy.value: "Redundancy",
    Dimension.cadence_sameness.value: "Cadence sameness",
    Dimension.unsupported_claims.value: "Unsupported claims",
    Dimension.formatting_tells.value: "Formatting tells (weak)",
    Dimension.prompt_residue.value: "Prompt residue",
    Dimension.human_writing_signals.value: "Human-writing signals (lowers score)",
}


def to_markdown(report: Report) -> str:
    s = report.score
    abstain = f" — ABSTAINED: {s.abstention_reason}" if s.abstained else ""
    lines = [
        f"# SlopScore: {s.slop_score} / 100 ({s.label.value}){abstain}",
        "",
        f"- **Confidence:** {s.confidence}",
        f"- **Profile:** {report.input.profile} · **Strictness:** {s.strictness}",
        f"- **Words analyzed:** {report.input.word_count} · **Language:** {report.input.language}",
        "",
        "## Dimensions",
        "",
        "| Dimension | Score |",
        "| --- | ---: |",
    ]
    dims = report.dimensions.model_dump()
    for key, label in _DIMENSION_LABELS.items():
        value = dims.get(key)
        if value is not None:
            lines.append(f"| {label} | {value:.2f} |")

    lines += ["", "## Evidence", ""]
    if not report.evidence:
        lines.append("_No pattern matches._")
    for e in report.evidence[:50]:
        snippet = e.span.replace("\n", " ").strip()
        lines.append(
            f"- `{e.rule_id}` ({e.severity.value}, chars {e.start_char}-{e.end_char}): "
            f'"{snippet}" — {e.explanation}'
        )

    lines += ["", "## Notes", ""]
    lines += [f"> {w}" for w in report.warnings]
    return "\n".join(lines) + "\n"
