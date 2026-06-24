"""JSON ingestion and the website-extra guard."""

from __future__ import annotations

import builtins
import json

import pytest

from slopscore.ingest.json_source import ingest_json
from slopscore.ingest.website import WebExtraNotInstalled, ingest_url


def test_json_path_selects_field() -> None:
    raw = json.dumps({"article": {"body": "delve into the robust tapestry", "tags": ["x"]}})
    src = ingest_json(raw, json_path="$.article.body")
    assert src.text == "delve into the robust tapestry"


def test_json_without_path_collects_strings() -> None:
    raw = json.dumps({"title": "Hello", "meta": {"author": "World"}, "n": 3})
    src = ingest_json(raw)
    assert "Hello" in src.text
    assert "World" in src.text


def test_website_hint_when_extra_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args, **kwargs):
        if name == "trafilatura":
            raise ImportError("absent")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(WebExtraNotInstalled) as exc:
        ingest_url("https://example.com/post")
    assert "slopscore[web]" in str(exc.value)
