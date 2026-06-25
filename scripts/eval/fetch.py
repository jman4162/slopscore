"""Fetch large public evaluation corpora into the local cache (not committed to the repo).

These corpora are the backbone for full evaluation runs. The SHIPPED model is trained only on
permissive / CC-BY / CC-BY-SA sources (see DATA_SOURCES.md); CC-BY-NC corpora (HC3) are used for
local evaluation only and never redistributed or used for training. Downloaded files land in
``~/.cache/slopscore/`` and are loaded with ``slopscore.eval.datasets.load_jsonl``.

This script requires network access (and, for HuggingFace-hosted sets, ``datasets``); it is not
run in CI. Run a subset with e.g. ``python scripts/eval/fetch.py raid mage``.
"""

from __future__ import annotations

import sys
from pathlib import Path

CACHE = Path.home() / ".cache" / "slopscore"

# name -> (url-or-hf-id, license, train-eligible?). Train-eligible excludes NC licenses.
SOURCES: dict[str, tuple[str, str, bool]] = {
    "raid": ("liamdugan/raid", "MIT/permissive (verify upstream)", True),
    "mage": ("yaful/MAGE", "CC-BY-4.0", True),
    "kobak_excess": ("berenslab/llm-excess-vocab (GitHub)", "CC-BY-SA-3.0", True),
    "hc3": ("Hello-SimpleAI/HC3", "CC-BY-NC-4.0", False),  # eval-only, never trains the model
}


def fetch(name: str) -> None:
    if name not in SOURCES:
        raise SystemExit(f"unknown source '{name}'; choose from {sorted(SOURCES)}")
    src, lic, trainable = SOURCES[name]
    CACHE.mkdir(parents=True, exist_ok=True)
    note = "train+eval" if trainable else "EVAL-ONLY (NC license)"
    print(f"[{name}] {src}  license={lic}  use={note}")
    print(
        "  This is a documented stub. Implement the actual download with `datasets.load_dataset`\n"
        "  or a direct HTTP fetch, normalize each row to {text,label,bucket,subgroup}, and write\n"
        f"  JSONL to {CACHE / (name + '.jsonl')}. Keep NC sources out of training splits."
    )


def main(argv: list[str]) -> None:
    names = argv or list(SOURCES)
    for name in names:
        fetch(name)


if __name__ == "__main__":
    main(sys.argv[1:])
