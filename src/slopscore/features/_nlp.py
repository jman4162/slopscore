"""Lazy, shared spaCy pipeline for the optional ``[nlp]`` extra.

Features always have a regex path; when spaCy and the English model are installed they call
:func:`get_nlp` to refine spans with POS/dependency precision. The model loads once per
process. Nothing here imports spaCy at module load, so the lean default install is unaffected.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from spacy.language import Language

_MODEL = "en_core_web_sm"


def is_nlp_available() -> bool:
    """True only if spaCy AND the English model can be loaded (cheap import check)."""
    try:
        import importlib.util

        if importlib.util.find_spec("spacy") is None:
            return False
        return importlib.util.find_spec(_MODEL) is not None
    except (ImportError, ValueError):
        return False


@lru_cache(maxsize=1)
def get_nlp() -> Language:
    """Load and cache the spaCy pipeline (tagger + parser only; NER kept for attribution)."""
    import spacy

    return spacy.load(_MODEL, disable=["lemmatizer"])


@lru_cache(maxsize=256)
def _cached_parse(text: str) -> Any:
    return get_nlp()(text)


def parse(text: str) -> Any:
    """Parse ``text`` with the shared pipeline, caching repeated inputs within a run."""
    return _cached_parse(text)


_EMBED_MODEL = "all-MiniLM-L6-v2"


def is_embeddings_available() -> bool:
    """True if sentence-transformers is installed (for the dense-embedding redundancy path)."""
    try:
        import importlib.util

        return importlib.util.find_spec("sentence_transformers") is not None
    except (ImportError, ValueError):
        return False


@lru_cache(maxsize=1)
def _embedder() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_EMBED_MODEL)


def embed(sentences: tuple[str, ...]) -> Any:
    """Return L2-normalized sentence embeddings (numpy array)."""
    return _embedder().encode(list(sentences), normalize_embeddings=True)
