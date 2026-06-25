"""Prose-in-code ingestion: extract docstrings/comments/JSDoc; offsets round-trip."""

from __future__ import annotations

import textwrap
from pathlib import Path

from slopscore import scan_path, scan_text
from slopscore.ingest.code import code_to_prose, ingest_code
from slopscore.models import SourceType

_PY = textwrap.dedent('''
    """This module leverages a robust, holistic framework to empower users."""
    import os

    # This comment plays a pivotal role and is crucial.
    def add(a, b):
        """Delve into the intricate tapestry of addition."""
        return a + b  # add them
''')

_JS = textwrap.dedent("""
    /** This function leverages a seamless, robust approach. */
    function add(a, b) {
      // it is crucial to return the sum
      return a + b;
    }
""")


def test_python_extracts_docstrings_and_comments() -> None:
    prose = code_to_prose(_PY, ".py")
    assert "leverages a robust" in prose  # module docstring
    assert "intricate tapestry" in prose  # function docstring
    assert "pivotal role" in prose  # comment
    assert "import os" not in prose  # code is not prose
    assert "return a + b" not in prose


def test_js_extracts_jsdoc_and_line_comments() -> None:
    prose = code_to_prose(_JS, ".js")
    assert "seamless, robust" in prose
    assert "crucial to return the sum" in prose
    assert "function add" not in prose


def test_ingest_code_source_type() -> None:
    raw = ingest_code(_PY, suffix=".py")
    assert raw.source_type is SourceType.code


def test_offsets_round_trip_to_extracted_prose() -> None:
    raw = ingest_code(_PY, suffix=".py")
    report = scan_text(raw.text)  # the extracted prose is what offsets index
    for e in report.evidence:
        assert report.original_text[e.start_char : e.end_char] == e.span


def test_scan_path_routes_py(tmp_path: Path) -> None:
    p = tmp_path / "mod.py"
    p.write_text(_PY, encoding="utf-8")
    report = scan_path(p)
    assert report.input.source_type is SourceType.code
    assert any(e.rule_id.startswith("LEXICAL_") for e in report.evidence)
    # clean code with no prose slop should score lower than the sloppy docstrings
    clean = tmp_path / "clean.py"
    clean_src = '"""Return the sum of a and b."""\ndef add(a, b):\n    return a + b\n'
    clean.write_text(clean_src, encoding="utf-8")
    assert scan_path(clean).score.slop_score < scan_path(p).score.slop_score


def test_fenced_code_does_not_inflate_prompt_residue() -> None:
    # Regression: a Markdown post with code blocks, scanned as raw text, must not read as slop
    # because of the ``` fences (prompt_residue inflation). See ingest.text.strip_fenced_code.
    md = (
        "Here is a note about a small script I wrote and tested last week on three files.\n\n"
        "```python\ndef count(path):\n    return len(open(path).read().split())\n```\n\n"
        "It ran in well under a second on a two megabyte input, which surprised me."
    )
    report = scan_text(md)
    assert report.dimensions.prompt_residue == 0.0
    assert not any(e.rule_id == "RESIDUE_CODE_FENCE" for e in report.evidence)
    assert report.score.slop_score < 40
