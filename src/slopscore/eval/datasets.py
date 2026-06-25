"""Load labeled evaluation rows from JSONL.

The committed seed set lives at ``eval/datasets/seed.jsonl`` (repo root). Large public corpora
fetched by ``scripts/eval/fetch_*`` land in the cache directory and are loaded the same way.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LabeledRow:
    text: str
    label: int  # 1 = slop, 0 = clean
    bucket: str
    subgroup: str


def _repo_root() -> Path:
    # src/slopscore/eval/datasets.py -> repo root is three parents up from this file's package.
    return Path(__file__).resolve().parents[3]


def dataset_path(name: str) -> Path:
    """Locate a committed eval dataset.

    Installed wheels ship the datasets under the package (``slopscore/data/eval/``, via the wheel
    force-include); a source checkout reads the repo-root ``eval/datasets/``. Prefer the packaged
    copy so CLI commands (``eval``, ``fairness``) work after ``pip install``.
    """
    from slopscore.config import data_path

    packaged = Path(str(data_path("eval", name)))
    if packaged.is_file():
        return packaged
    return _repo_root() / "eval" / "datasets" / name


def seed_path() -> Path:
    return dataset_path("seed.jsonl")


def benchmark_path() -> Path:
    return dataset_path("benchmark.jsonl")


def load_jsonl(path: str | Path) -> list[LabeledRow]:
    rows: list[LabeledRow] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rows.append(
                LabeledRow(
                    text=d["text"],
                    label=int(d["label"]),
                    bucket=d.get("bucket", "unknown"),
                    subgroup=d.get("subgroup", "general"),
                )
            )
    return rows


def load_seed() -> list[LabeledRow]:
    return load_jsonl(seed_path())
