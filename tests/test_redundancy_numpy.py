"""The numpy redundancy path: lexical overlap and templated frames, without scikit-learn."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from slopscore.features.redundancy import lexical_redundancy


def test_templated_neighbours_are_redundant() -> None:
    sentences = [
        "The get_user function returns a user object from the primary store.",
        "The get_group function returns a group object from the primary store.",
        "The get_role function returns a role object from the primary store.",
    ]
    assert lexical_redundancy(sentences) == 1.0


def test_repeated_sentences_are_redundant() -> None:
    s = "The bridge opened in 1937 after four years of construction."
    assert lexical_redundancy([s, s]) == 1.0


def test_ordinary_prose_is_not_redundant(clean_text: str) -> None:
    from slopscore.core import build_document
    from slopscore.ingest import from_string

    doc = build_document(from_string(clean_text))
    assert lexical_redundancy([s.text for s in doc.sentences]) == 0.0


def test_short_plain_sentences_do_not_count_as_frames() -> None:
    assert lexical_redundancy(["I like the sea.", "I like the hills.", "I like my town."]) == 0.0


def test_scan_path_does_not_import_sklearn() -> None:
    # A fresh interpreter: other tests import scikit-learn (the eval harness), so checking
    # sys.modules in-process would depend on test order.
    code = (
        "import sys; from slopscore import scan_text; "
        "scan_text('Let us delve into this robust tapestry. ' * 30); "
        "print(any(m == 'sklearn' or m.startswith('sklearn.') for m in sys.modules))"
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, env=env
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False", "scikit-learn must not be imported at scan time"
