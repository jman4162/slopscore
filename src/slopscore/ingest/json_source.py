"""JSON ingestion: select a field with a JSONPath expression."""

from __future__ import annotations

import json

from jsonpath_ng.ext import parse as parse_jsonpath

from slopscore.ingest import RawSource
from slopscore.models import SourceType


def ingest_json(
    raw: str,
    *,
    json_path: str | None = None,
    source: str = "<string>",
) -> RawSource:
    """Extract text from JSON. With ``json_path`` (e.g. ``$.article.body``) select that
    field; without it, concatenate all string leaves."""
    data = json.loads(raw)
    if json_path:
        matches = [m.value for m in parse_jsonpath(json_path).find(data)]
        text = "\n\n".join(str(m) for m in matches if isinstance(m, str))
    else:
        text = "\n\n".join(_string_leaves(data))
    return RawSource(text=text, source_type=SourceType.json, source=source)


def _string_leaves(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _string_leaves(v)]
    if isinstance(node, list):
        return [s for v in node for s in _string_leaves(v)]
    return []
