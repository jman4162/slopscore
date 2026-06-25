"""Self-contained HTML report with highlighted evidence spans.

Requires the optional ``[report]`` extra (Jinja2, for autoescaping user text safely). The output
is a single file with inline CSS — no external assets. Evidence spans are highlighted in the
source text (color + a severity glyph, so it doesn't rely on color alone); dark mode follows the
reader's ``prefers-color-scheme``.
"""

from __future__ import annotations

from slopscore.models import Evidence, Report

_HINT = (
    "HTML reports require the optional report extra. "
    'Install it with: pip install "slopscore[report]"'
)


class ReportExtraNotInstalled(RuntimeError):
    """Raised when an HTML report is requested but the ``[report]`` extra is missing."""


_SEVERITY_GLYPH = {"high": "⚠", "medium": "⚡", "low": "ℹ"}


def to_html(report: Report) -> str:
    try:
        from jinja2 import Environment, select_autoescape
    except ImportError as exc:  # pragma: no cover - exercised via guarded path
        raise ReportExtraNotInstalled(_HINT) from exc

    env = Environment(autoescape=select_autoescape(default=True))
    escape = env.filters["e"]

    highlighted = _render_highlight(report, escape)
    template = env.from_string(_TEMPLATE)
    dims = {k: v for k, v in report.dimensions.model_dump().items() if v is not None}
    return str(
        template.render(
            report=report,
            score=report.score,
            meta=report.input,
            dims=dims,
            highlighted=highlighted,
            warnings=report.warnings,
        )
    )


def _render_highlight(report: Report, escape) -> str:  # type: ignore[no-untyped-def]
    """Build the highlighted source as one safe HTML string (spans opened+closed in order)."""
    text = report.original_text
    spans = sorted(report.evidence, key=lambda e: (e.start_char, -(e.end_char - e.start_char)))
    chosen: list[Evidence] = []
    last_end = -1
    for e in spans:
        if e.start_char >= last_end and e.end_char <= len(text):
            chosen.append(e)
            last_end = e.end_char

    parts: list[str] = []
    cursor = 0
    for e in chosen:
        parts.append(str(escape(text[cursor : e.start_char])))
        glyph = _SEVERITY_GLYPH.get(e.severity.value, "")
        title = str(escape(f"{e.rule_id}: {e.explanation}"))
        snippet = str(escape(text[e.start_char : e.end_char]))
        parts.append(
            f'<mark class="sev-{e.severity.value}" title="{title}">'
            f"{snippet}<sup>{glyph}</sup></mark>"
        )
        cursor = e.end_char
    parts.append(str(escape(text[cursor:])))
    return "".join(parts)


_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>slopscore report</title>
<style>
:root { color-scheme: light dark; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       line-height: 1.6; max-width: 860px; margin: 2rem auto; padding: 0 1rem; }
.score { font-size: 2.6rem; font-weight: 700; }
.low { color: #22c55e; } .mild { color: #3b82f6; }
.elevated { color: #f59e0b; } .severe { color: #ef4444; }
.meta { color: #888; font-size: .9rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
td { padding: .2rem .5rem; border-bottom: 1px solid #8884; }
td.v { text-align: right; font-variant-numeric: tabular-nums; }
pre.src { white-space: pre-wrap; word-wrap: break-word; background: #8881;
          padding: 1rem; border-radius: 6px; }
mark { border-radius: 3px; padding: 0 .1em; }
mark.sev-high { background: #ef444455; } mark.sev-medium { background: #f59e0b55; }
mark.sev-low { background: #3b82f655; }
mark sup { font-size: .7em; }
.warn { color: #b45309; font-size: .9rem; }
</style>
</head>
<body>
<h1>slopscore</h1>
<div class="score {{ score.label.value }}">{{ score.slop_score }} / 100
  <span style="font-size:1rem">({{ score.label.value }}{% if score.abstained %}, abstained{% endif %})</span>
</div>
<p class="meta">confidence {{ score.confidence }} &middot; profile {{ meta.profile }} &middot;
  {{ meta.word_count }} words &middot; {{ meta.language }}</p>
{% if score.abstained %}<p class="warn">Abstained: {{ score.abstention_reason }}</p>{% endif %}

<h2>Dimensions</h2>
<table>
{% for name, value in dims.items() %}<tr><td>{{ name }}</td><td class="v">{{ "%.2f"|format(value) }}</td></tr>
{% endfor %}</table>

<h2>Text with evidence highlighted</h2>
<pre class="src">{{ highlighted|safe }}</pre>

<h2>Notes</h2>
{% for w in warnings %}<p class="warn">{{ w }}</p>
{% endfor %}
</body>
</html>
"""
