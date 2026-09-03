"""GFM tables are dropped and link URLs kept (v0.9.2)."""

from __future__ import annotations

from slopscore.ingest.markdown import markdown_to_prose


def test_pipe_table_is_not_scored_as_prose() -> None:
    md = "Intro line.\n\n| Column | Delve |\n| --- | --- |\n| robust | tapestry |\n\nOutro line.\n"
    prose = markdown_to_prose(md)
    assert "|" not in prose
    assert "tapestry" not in prose
    assert prose == "Intro line.\n\nOutro line."


def test_http_link_keeps_its_url_for_specificity() -> None:
    prose = markdown_to_prose("See [the docs](https://example.com/x) and [local](./a.md).")
    assert prose == "See the docs (https://example.com/x) and local."
