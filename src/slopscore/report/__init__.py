"""Report serializers: console, JSON, Markdown (HTML stubbed for v0.2)."""

from slopscore.report.console import render as render_console
from slopscore.report.json_report import to_json
from slopscore.report.markdown import to_markdown

__all__ = ["render_console", "to_json", "to_markdown"]
