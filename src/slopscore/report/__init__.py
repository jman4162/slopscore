"""Report serializers: console, JSON, Markdown (HTML stubbed for v0.2)."""

from slopscore.report.console import render as render_console
from slopscore.report.console import render_batch
from slopscore.report.json_report import to_json
from slopscore.report.markdown import to_markdown
from slopscore.report.sarif import to_sarif

__all__ = ["render_batch", "render_console", "to_json", "to_markdown", "to_sarif"]
