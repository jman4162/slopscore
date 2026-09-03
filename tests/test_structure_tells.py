"""Structure tells from Markdown block metadata (v0.13)."""

from __future__ import annotations

from slopscore import scan_text
from slopscore.core import build_document
from slopscore.ingest import from_string
from slopscore.ingest.markdown import ingest_markdown, markdown_to_prose_with_blocks

LISTICLE = """\
# 🚀 Why This Matters

Here is what the release brings for the team this quarter and beyond.

---

## ✨ Key Takeaways

- **Speed:** the new parser runs faster on every input we tried.
- **Cost:** the hosted plan is cheaper per seat for small teams.
- **Reach:** the connector ships with support for three more sources.
- **Safety:** every write is checked twice before it lands.

---

#### Getting Started With The New Release

Install the package, run the scan, and read the report. **Nothing else** is required, and the
**defaults** are safe. The team wrote the spec in March and shipped in June.

---

## 💡 Final Thoughts

That is the whole story of the release.
"""

README = """\
# slopscore

A linter for AI-slop writing patterns.

## Install

Run `pip install slopscore-lint`. The default install is lean.

## Usage

- Scan a file with `slopscore-lint scan FILE`.
- Scan a directory with `--recursive`.
- Write SARIF with `--format sarif`.

## Configuration

Settings live in `slopscore.toml`; see the docs for the keys.
"""


def _ids(md: str) -> set[str]:
    return {e.rule_id for e in scan_text(md).evidence}


def test_blocks_index_the_extracted_prose() -> None:
    prose, blocks = markdown_to_prose_with_blocks(LISTICLE)
    assert blocks and all(prose[b.start : b.end] for b in blocks)
    kinds = [b.kind for b in blocks]
    assert kinds.count("heading") == 4 and kinds.count("list_item") == 4
    assert [b.level for b in blocks if b.kind == "heading"] == [1, 2, 4, 2]
    assert sum(b.bold_lead for b in blocks) == 4
    assert sum(b.emoji_lead for b in blocks) == 3
    assert sum(b.break_before for b in blocks) == 3


def test_listicle_shape_fires_the_structure_rules() -> None:
    ids = _ids(LISTICLE)
    assert {
        "STRUCTURE_EMOJI_HEADING",
        "STRUCTURE_INLINE_HEADER_LIST",
        "STRUCTURE_SKIPPED_HEADING_LEVEL",
        "STRUCTURE_THEMATIC_BREAKS",
        "STRUCTURE_TITLE_CASE_HEADING",
    } <= ids
    report = scan_text(LISTICLE)
    assert report.dimensions.structure_tells > 0.5
    for e in report.evidence:
        assert report.original_text[e.start_char : e.end_char] == e.span


def test_plain_readme_structure_is_quiet() -> None:
    report = scan_text(README)
    assert not {e.rule_id for e in report.evidence if e.rule_id.startswith("STRUCTURE_")}
    assert report.dimensions.structure_tells == 0.0


def test_plain_prose_has_no_blocks_and_scores_zero(clean_text: str) -> None:
    doc = build_document(from_string(clean_text))
    assert doc.blocks == []
    assert scan_text(clean_text).dimensions.structure_tells == 0.0


def test_technical_profile_softens_structure() -> None:
    blog = scan_text(LISTICLE, profile="blog").breakdown
    tech = scan_text(LISTICLE, profile="technical").breakdown
    assert blog is not None and tech is not None
    b = next(r for r in blog.contributions if r.dimension == "structure_tells")
    t = next(r for r in tech.contributions if r.dimension == "structure_tells")
    assert t.multiplier < b.multiplier


def test_cadence_ignores_headings_and_bullets() -> None:
    bullets = "\n".join(f"- Item {i} does the same thing again." for i in range(8))
    prose = (
        "The plant opened in 1962. It closed after 27 years, when the parent company moved "
        "production to Mexico and the town lost 1,200 jobs in a single quarter."
    )
    md = "# Title\n\n" + bullets + "\n\n" + prose + "\n"
    report = scan_text(md)
    assert report.dimensions.cadence_sameness == 0.0  # only two prose sentences remain
    assert ingest_markdown(md).blocks
