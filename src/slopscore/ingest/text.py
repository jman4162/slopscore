"""Plain-text / pasted-string ingestion (passthrough)."""

from __future__ import annotations

from slopscore.ingest import RawSource
from slopscore.models import SourceType


def ingest_text(text: str, source: str = "<string>") -> RawSource:
    return RawSource(text=text, source_type=SourceType.text, source=source)
