"""Inline suppression works end-to-end in Markdown (control comments survive prose extraction)."""

from __future__ import annotations

from pathlib import Path

from slopscore import scan_path

# A sentence that reliably triggers SIGNIF_STANDS_AS_TESTAMENT.
_SENT = "The museum stands as a testament to the city history and the long work of many people."


def _rule_ids(p: Path) -> set[str]:
    return {e.rule_id for e in scan_path(p).evidence}


def test_sentence_fires_without_comment(tmp_path: Path) -> None:
    p = tmp_path / "a.md"
    p.write_text(f"# Title\n\n{_SENT}\n", encoding="utf-8")
    assert "SIGNIF_STANDS_AS_TESTAMENT" in _rule_ids(p)


def test_disable_next_line_in_markdown(tmp_path: Path) -> None:
    p = tmp_path / "b.md"
    p.write_text(
        f"# Title\n\n<!-- slopscore-disable-next-line SIGNIF_STANDS_AS_TESTAMENT -->\n{_SENT}\n",
        encoding="utf-8",
    )
    assert "SIGNIF_STANDS_AS_TESTAMENT" not in _rule_ids(p)


def test_disable_block_in_markdown(tmp_path: Path) -> None:
    p = tmp_path / "c.md"
    p.write_text(
        "<!-- slopscore-disable SIGNIF_STANDS_AS_TESTAMENT -->\n"
        f"{_SENT}\n\n"
        "<!-- slopscore-enable SIGNIF_STANDS_AS_TESTAMENT -->\n",
        encoding="utf-8",
    )
    assert "SIGNIF_STANDS_AS_TESTAMENT" not in _rule_ids(p)


def test_disable_file_in_markdown(tmp_path: Path) -> None:
    p = tmp_path / "d.md"
    p.write_text(f"<!-- slopscore-disable-file -->\n{_SENT}\n", encoding="utf-8")
    assert not [e for e in scan_path(p).evidence if not e.rule_id.startswith("SUGGEST_")]


def test_non_slopscore_comment_is_dropped_and_does_not_suppress(tmp_path: Path) -> None:
    p = tmp_path / "e.md"
    p.write_text(f"# Title\n\n<!-- TODO: rewrite -->\n{_SENT}\n", encoding="utf-8")
    report = scan_path(p)
    assert "TODO" not in report.original_text  # other HTML still stripped
    assert "SIGNIF_STANDS_AS_TESTAMENT" in {e.rule_id for e in report.evidence}


def test_inline_disable_line_still_works(tmp_path: Path) -> None:
    p = tmp_path / "f.md"
    p.write_text(
        f"# Title\n\n{_SENT} <!-- slopscore-disable-line SIGNIF_STANDS_AS_TESTAMENT -->\n",
        encoding="utf-8",
    )
    assert "SIGNIF_STANDS_AS_TESTAMENT" not in _rule_ids(p)
