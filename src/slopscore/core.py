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
    ) -> None:
        self.settings = Settings(profile=profile, strictness=Strictness(strictness))

    def _score(self, raw: RawSource) -> Report:
        return score_document(build_document(raw), self.settings)

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
