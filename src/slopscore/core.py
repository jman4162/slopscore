"""The scan pipeline and the public ``SlopScorer`` API.

RawSource -> canonicalize (ftfy) -> clean (offset-preserving) -> segment -> language detect
-> Document -> score. Importing :mod:`slopscore.features` registers all extractors.
"""

from __future__ import annotations

from pathlib import Path

import slopscore.features  # noqa: F401  (registers feature extractors)
from slopscore.config import Settings, Strictness
from slopscore.document import Document
from slopscore.ingest import RawSource, from_path, from_string, from_url
from slopscore.models import Report
from slopscore.normalize.clean import canonicalize, clean
from slopscore.normalize.language import detect_language
from slopscore.normalize.segment import split_paragraphs, split_sentences
from slopscore.scoring.scorer import score_document


def build_document(raw: RawSource) -> Document:
    canonical = canonicalize(raw.text)
    cleaned, mapper = clean(canonical)
    language, lang_conf = detect_language(cleaned)
    return Document(
        original_text=canonical,
        cleaned_text=cleaned,
        mapper=mapper,
        sentences=split_sentences(cleaned),
        paragraphs=split_paragraphs(cleaned),
        source_type=raw.source_type,
        source=raw.source,
        language=language,
        language_confidence=lang_conf,
    )


class SlopScorer:
    """Scan text, files, or URLs for AI-slop writing patterns."""

    def __init__(
        self,
        profile: str = "blog",
        strictness: str | Strictness = Strictness.conservative,
        baseline: str | None = None,
    ) -> None:
        self.settings = Settings(profile=profile, strictness=Strictness(strictness))
        self._baseline = self._load_baseline(baseline)

    @staticmethod
    def _load_baseline(name: str | None):  # type: ignore[no-untyped-def]
        if name is None:
            return None
        from slopscore.scoring.calibrate import load_profile

        profile = load_profile(name)
        if profile is None:
            raise FileNotFoundError(
                f"No calibration baseline named '{name}'. Run `slopscore calibrate` first."
            )
        return profile

    def _score(self, raw: RawSource) -> Report:
        report = score_document(build_document(raw), self.settings)
        if self._baseline is not None:
            report.baseline = self._baseline.compare(report.dimensions)
        return report

    def scan_text(self, text: str, source: str = "<string>") -> Report:
        return self._score(from_string(text, source=source))

    def scan_file(self, path: str | Path, *, json_path: str | None = None) -> Report:
        return self._score(from_path(path, json_path=json_path))

    def scan_url(self, url: str) -> Report:
        return self._score(from_url(url))


def scan_text(
    text: str,
    *,
    profile: str = "blog",
    strictness: str | Strictness = Strictness.conservative,
    source: str = "<string>",
) -> Report:
    return SlopScorer(profile=profile, strictness=strictness).scan_text(text, source=source)


def scan_path(
    path: str | Path,
    *,
    profile: str = "blog",
    strictness: str | Strictness = Strictness.conservative,
    json_path: str | None = None,
) -> Report:
    return SlopScorer(profile=profile, strictness=strictness).scan_file(path, json_path=json_path)


def scan_url(
    url: str,
    *,
    profile: str = "blog",
    strictness: str | Strictness = Strictness.conservative,
) -> Report:
    return SlopScorer(profile=profile, strictness=strictness).scan_url(url)
