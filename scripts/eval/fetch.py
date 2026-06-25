"""Fetch public evaluation corpora into the local cache (not committed).

Implements a real balanced fetch for MAGE (CC-BY, train-eligible) via streaming, mapping its
authorship label to slopscore's pattern label (machine-generated -> 1, human -> 0) and keeping
the source domain for leakage-aware splits. Other large corpora remain documented stubs.

The SHIPPED model is trained only on permissive / CC-BY / CC-BY-SA sources; CC-BY-NC corpora
(HC3) are eval-only and never used for training. Output JSONL lands in ``~/.cache/slopscore/``.

Run: ``python scripts/eval/fetch.py mage --per-class 800``  (needs network + the [eval] extra).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CACHE = Path.home() / ".cache" / "slopscore"

SOURCES: dict[str, tuple[str, str, bool]] = {
    "mage": ("yaful/MAGE", "CC-BY-4.0", True),
    "raid": ("liamdugan/raid", "permissive (verify upstream)", True),
    "kobak_excess": ("berenslab/llm-excess-vocab (GitHub)", "CC-BY-SA-3.0", True),
    "hc3": ("Hello-SimpleAI/HC3", "CC-BY-NC-4.0", False),  # eval-only, never trains
}

# MAGE: label 1 = human, 0 = machine. slopscore positive (slop) = machine-generated.
_MIN_WORDS = 40
_MAX_CHARS = 2000


def fetch_mage(per_class: int) -> Path:
    from datasets import load_dataset

    ds = load_dataset("yaful/MAGE", split="train", streaming=True)
    rows: list[dict[str, object]] = []
    counts = {0: 0, 1: 0}  # our labels: 1=slop(machine), 0=clean(human)
    for ex in ds:
        text = (ex.get("text") or "").strip()[:_MAX_CHARS]
        if len(text.split()) < _MIN_WORDS:
            continue
        mage_label = int(ex["label"])
        our_label = 0 if mage_label == 1 else 1  # human->0, machine->1
        if counts[our_label] >= per_class:
            if counts[0] >= per_class and counts[1] >= per_class:
                break
            continue
        counts[our_label] += 1
        rows.append(
            {
                "text": text,
                "label": our_label,
                "bucket": "raw_llm" if our_label == 1 else "human_good",
                "subgroup": str(ex.get("src", "mage")),
            }
        )
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / "mage.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[mage] wrote {len(rows)} rows ({counts}) to {out}")
    return out


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", default=["mage"])
    parser.add_argument("--per-class", type=int, default=800)
    args = parser.parse_args(argv)
    for name in args.names or ["mage"]:
        if name == "mage":
            fetch_mage(args.per_class)
        elif name in SOURCES:
            src, lic, trainable = SOURCES[name]
            use = "train+eval" if trainable else "EVAL-ONLY (NC license)"
            print(f"[{name}] {src}  license={lic}  use={use}  (stub — implement like fetch_mage)")
        else:
            raise SystemExit(f"unknown source '{name}'; choose from {sorted(SOURCES)}")


if __name__ == "__main__":
    main(sys.argv[1:])
