"""Website ingestion via trafilatura (requires the ``[web]`` extra)."""

from __future__ import annotations

from slopscore.ingest import RawSource
from slopscore.models import SourceType

_WEB_HINT = (
    "Website scanning requires the optional web extra. "
    'Install it with: pip install "slopscore-lint[web]"'
)


class WebExtraNotInstalled(RuntimeError):
    """Raised when a URL is scanned but the ``[web]`` extra is missing."""


def ingest_url(url: str) -> RawSource:
    try:
        import trafilatura
    except ImportError as exc:  # pragma: no cover - exercised via guarded path
        raise WebExtraNotInstalled(_WEB_HINT) from exc

    downloaded = trafilatura.fetch_url(url)
    if downloaded is None:
        raise RuntimeError(f"Could not fetch URL: {url}")
    extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
    if not extracted:
        raise RuntimeError(f"Could not extract article text from: {url}")
    return RawSource(text=extracted, source_type=SourceType.website, source=url)
