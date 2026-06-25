"""Dense-embedding redundancy catches rephrased repetition (skipped without the [nlp] extra)."""

from __future__ import annotations

import pytest

from slopscore.core import build_document
from slopscore.features._nlp import is_embeddings_available
from slopscore.features.redundancy import Redundancy
from slopscore.ingest import from_string

_REPHRASED = (
    "Our software saves you many hours every single day. The application cuts the time you "
    "spend each day. This tool reduces your daily workload by a lot."
)
_DISTINCT = (
    "The factory opened in 1962 near Cleveland. Copper prices fell four percent in March. "
    "The trail climbs 900 meters in four kilometers."
)


def _redundancy(text: str) -> float:
    return Redundancy().extract(build_document(from_string(text)), "blog").score


@pytest.mark.skipif(not is_embeddings_available(), reason="requires the [nlp] embeddings extra")
def test_embedding_redundancy_catches_rephrase() -> None:
    assert _redundancy(_REPHRASED) > _redundancy(_DISTINCT)
    assert _redundancy(_DISTINCT) == 0.0
