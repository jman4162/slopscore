"""Fetch public evaluation corpora into the local cache (not committed).

Sources and their use:
- ``mage``        : MAGE authorship corpus (CC-BY-4.0). Authorship, not slop; an authorship-null
                    panel. Needs the ``[eval]`` extra (the ``datasets`` library).
- ``fineweb_edu`` : FineWeb-Edu (ODC-BY). Educational-quality web docs; high score -> clean(0),
                    low -> slop-proxy(1). Long-form real prose. HTTP via the HF datasets-server.
- ``finerweb``    : FinerWeb-10BT (Apache-2.0). Line-quality web text; high mean line-quality ->
                    clean(0), low -> slop-proxy(1). HTTP via the HF datasets-server.
- ``wiki_aicleanup`` : Wikipedia WikiProject AI Cleanup (CC-BY-SA-4.0). Articles editors flagged as
                    suspected AI-generated -> slop(1); random clean articles -> clean(0).
                    Subjective labels: **EVAL-ONLY**, never trains the shipped model.
- ``slop_cshaib`` : "Measuring AI Slop" (arXiv:2509.19163) span annotations. Not released yet (stub).

The SHIPPED model is trained only on permissive / CC-BY / CC-BY-SA train-eligible sources; eval-only
sources (Wikipedia AI Cleanup, HC3) are never used for training. Output JSONL lands in
``~/.cache/slopscore/``. The ``fineweb_edu``/``finerweb``/``wiki_aicleanup`` fetchers use plain HTTP
(no heavy dependency); only ``mage`` needs the ``datasets`` library.

Run: ``python scripts/eval/fetch.py wiki_aicleanup fineweb_edu --per-class 40``
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CACHE = Path.home() / ".cache" / "slopscore"
_UA = "slopscore-eval/0.5 (https://github.com/jman4162/slopscore)"
_MIN_WORDS = 40
_MAX_CHARS = 2000


@dataclass(frozen=True)
class Source:
    hf_or_url: str
    license: str
    train_eligible: bool


SOURCES: dict[str, Source] = {
    "mage": Source("yaful/MAGE", "CC-BY-4.0", True),
    "fineweb_edu": Source("HuggingFaceFW/fineweb-edu", "ODC-BY", True),
    "finerweb": Source("TurkuNLP/finerweb-10bt", "Apache-2.0", True),
    "wiki_aicleanup": Source("Wikipedia AI Cleanup category", "CC-BY-SA-4.0", False),  # eval-only
    "hc3": Source("Hello-SimpleAI/HC3", "CC-BY-NC-4.0", False),  # eval-only
    "slop_cshaib": Source("cshaib/slop (arXiv:2509.19163)", "MIT", False),  # not released
}


def _get_json(url: str, retries: int = 4) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # back off on rate limits / transient 5xx
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    return {}


def _write(name: str, rows: list[dict], counts: dict) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"{name}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[{name}] wrote {len(rows)} rows ({counts}) to {out}")
    return out


def _ok(text: str) -> bool:
    return _MIN_WORDS <= len(text.split()) and len(text) >= 80


# --- HF datasets-server (no datasets library needed) -----------------------------------------

_ROWS = "https://datasets-server.huggingface.co/rows"


def _hf_rows(dataset: str, length: int, offset: int) -> list[dict]:
    q = urllib.parse.urlencode(
        {
            "dataset": dataset,
            "config": "default",
            "split": "train",
            "offset": offset,
            "length": length,
        }
    )
    return [r["row"] for r in _get_json(f"{_ROWS}?{q}").get("rows", [])]


def fetch_fineweb_edu(per_class: int) -> Path:
    """High educational score -> clean(0); low -> slop-proxy(1). Long-form real web prose."""
    rows: list[dict] = []
    counts = {0: 0, 1: 0}
    offset = 0
    while min(counts.values()) < per_class and offset < 8000:
        for row in _hf_rows("HuggingFaceFW/fineweb-edu", 100, offset):
            text = (row.get("text") or "").strip()[:_MAX_CHARS]
            score = float(row.get("score", row.get("int_score", 3)) or 3)
            label = 0 if score >= 3.5 else (1 if score <= 2.0 else None)
            if label is None or not _ok(text) or counts[label] >= per_class:
                continue
            counts[label] += 1
            rows.append({"text": text, "label": label, "bucket": "web_edu", "subgroup": "web"})
        offset += 100
        time.sleep(0.2)
    return _write("fineweb_edu", rows, counts)


def fetch_finerweb(per_class: int) -> Path:
    """High mean line-quality -> clean(0); low -> slop-proxy(1)."""
    rows: list[dict] = []
    counts = {0: 0, 1: 0}
    offset = 0
    while min(counts.values()) < per_class and offset < 8000:
        for row in _hf_rows("TurkuNLP/finerweb-10bt", 100, offset):
            text = (row.get("text") or "").strip()[:_MAX_CHARS]
            lq = row.get("line_quality")
            if isinstance(lq, str):
                lq = json.loads(lq)
            if not lq:
                continue
            mean = sum(float(x) for x in lq) / len(lq)
            label = 0 if mean >= 0.85 else (1 if mean <= 0.55 else None)
            if label is None or not _ok(text) or counts[label] >= per_class:
                continue
            counts[label] += 1
            rows.append({"text": text, "label": label, "bucket": "web_quality", "subgroup": "web"})
        offset += 100
        time.sleep(0.2)
    return _write("finerweb", rows, counts)


# --- Wikipedia AI Cleanup (eval-only) --------------------------------------------------------

_WIKI = "https://en.wikipedia.org/w/api.php"
_AI_CAT = "Category:Articles containing suspected AI-generated texts"


def _wiki_extract(title: str) -> str:
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "redirects": 1,
            "titles": title,
            "format": "json",
        }
    )
    pages = _get_json(f"{_WIKI}?{q}").get("query", {}).get("pages", {})
    for page in pages.values():
        return (page.get("extract") or "").strip()[:_MAX_CHARS]
    return ""


def _category_members(category: str, cmtype: str, limit: int) -> list[str]:
    titles: list[str] = []
    cont = ""
    while len(titles) < limit:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": cmtype,
            "cmlimit": 50,
            "format": "json",
        }
        if cont:
            params["cmcontinue"] = cont
        data = _get_json(f"{_WIKI}?{urllib.parse.urlencode(params)}")
        titles += [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        cont = data.get("continue", {}).get("cmcontinue", "")
        if not cont:
            break
        time.sleep(0.2)
    return titles[:limit]


def _wiki_category_titles(category: str, limit: int) -> list[str]:
    """Pages in the category, recursing one level into its (monthly) subcategories."""
    titles = _category_members(category, "page", limit)
    if len(titles) < limit:
        for subcat in _category_members(category, "subcat", 24):
            if len(titles) >= limit:
                break
            titles += _category_members(subcat, "page", limit - len(titles))
            time.sleep(0.2)
    # de-dup preserving order
    return list(dict.fromkeys(titles))[:limit]


def _wiki_random_titles(limit: int) -> list[str]:
    q = urllib.parse.urlencode(
        {"action": "query", "list": "random", "rnnamespace": 0, "rnlimit": limit, "format": "json"}
    )
    return [r["title"] for r in _get_json(f"{_WIKI}?{q}").get("query", {}).get("random", [])]


def fetch_wiki_aicleanup(per_class: int) -> Path:
    """Flagged 'suspected AI-generated' article leads -> slop(1); random articles -> clean(0).

    EVAL-ONLY: labels are subjective editor judgments; never train the shipped model on these.
    """
    rows: list[dict] = []
    counts = {0: 0, 1: 0}
    for title in _wiki_category_titles(_AI_CAT, per_class * 3):
        if counts[1] >= per_class:
            break
        text = _wiki_extract(title)
        if _ok(text):
            counts[1] += 1
            rows.append({"text": text, "label": 1, "bucket": "wild_slop", "subgroup": "wiki"})
        time.sleep(0.15)
    while counts[0] < per_class:
        for title in _wiki_random_titles(min(20, per_class)):
            if counts[0] >= per_class:
                break
            text = _wiki_extract(title)
            if _ok(text):
                counts[0] += 1
                rows.append({"text": text, "label": 0, "bucket": "wiki_clean", "subgroup": "wiki"})
            time.sleep(0.15)
    return _write("wiki_aicleanup", rows, counts)


def fetch_mage(per_class: int) -> Path:
    from datasets import load_dataset

    ds = load_dataset("yaful/MAGE", split="train", streaming=True)
    rows: list[dict] = []
    counts = {0: 0, 1: 0}
    for ex in ds:
        text = (ex.get("text") or "").strip()[:_MAX_CHARS]
        if len(text.split()) < _MIN_WORDS:
            continue
        our_label = 0 if int(ex["label"]) == 1 else 1  # MAGE: 1=human->0, 0=machine->1
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
    return _write("mage", rows, counts)


_FETCHERS = {
    "mage": fetch_mage,
    "fineweb_edu": fetch_fineweb_edu,
    "finerweb": fetch_finerweb,
    "wiki_aicleanup": fetch_wiki_aicleanup,
}


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*", default=["wiki_aicleanup"])
    parser.add_argument("--per-class", type=int, default=40)
    args = parser.parse_args(argv)
    for name in args.names or ["wiki_aicleanup"]:
        if name not in SOURCES:
            raise SystemExit(f"unknown source '{name}'; choose from {sorted(SOURCES)}")
        src = SOURCES[name]
        if name in _FETCHERS:
            _FETCHERS[name](args.per_class)
        else:
            use = "train+eval" if src.train_eligible else "EVAL-ONLY"
            print(
                f"[{name}] {src.hf_or_url}  license={src.license}  use={use}  (not yet implemented)"
            )


if __name__ == "__main__":
    main(sys.argv[1:])
