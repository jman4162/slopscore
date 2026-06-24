"""Markdown ingestion strips code/blockquotes but keeps prose and headings."""

from __future__ import annotations

from slopscore.ingest.markdown import markdown_to_prose


def test_code_block_is_dropped(markdown_text: str) -> None:
    prose = markdown_to_prose(markdown_text)
    assert 'x = "delve delve delve"' not in prose
    assert "must be ignored" not in prose


def test_blockquote_is_dropped(markdown_text: str) -> None:
    prose = markdown_to_prose(markdown_text)
    assert "should be skipped" not in prose


def test_prose_and_heading_kept(markdown_text: str) -> None:
    prose = markdown_to_prose(markdown_text)
    assert "Heading" in prose
    assert "real paragraph with the word delve" in prose
    assert "Another paragraph here." in prose


def test_inline_code_span_dropped() -> None:
    prose = markdown_to_prose("Use the `delve()` function carefully.")
    assert "delve" not in prose
    assert "function carefully" in prose
