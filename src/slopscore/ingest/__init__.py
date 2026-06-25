"""Turn a source (string, file, URL, JSON) into analyzable prose.

Each ingester returns a :class:`RawSource`: the prose text to analyze plus where it came
from. Offsets in the final report index this prose (for Markdown that means the extracted
prose, with code blocks and tables removed).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slopscore.models import SourceType


@dataclass
class RawSource:
    text: str
    source_type: SourceType
    source: str


def from_string(text: str, source: str = "<string>") -> RawSource:
    from slopscore.ingest.text import ingest_text

    return ingest_text(text, source=source)


def from_path(path: str | Path, *, json_path: str | None = None) -> RawSource:
    """Dispatch a file to the right ingester by extension."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in {".md", ".markdown", ".mdx"}:
        from slopscore.ingest.markdown import ingest_markdown

        return ingest_markdown(p.read_text(encoding="utf-8"), source=str(p))
    if suffix == ".json":
        from slopscore.ingest.json_source import ingest_json

        return ingest_json(p.read_text(encoding="utf-8"), json_path=json_path, source=str(p))
    from slopscore.ingest.code import is_code_suffix

    if is_code_suffix(suffix):
        from slopscore.ingest.code import ingest_code

        return ingest_code(p.read_text(encoding="utf-8"), suffix=suffix, source=str(p))
    from slopscore.ingest.text import ingest_text

    return ingest_text(p.read_text(encoding="utf-8"), source=str(p))


def from_url(url: str) -> RawSource:
    from slopscore.ingest.website import ingest_url

    return ingest_url(url)


def looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


__all__ = ["RawSource", "from_path", "from_string", "from_url", "looks_like_url"]
