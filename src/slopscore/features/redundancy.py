"""Redundancy: adjacent-sentence semantic overlap.

Default path: TF-IDF cosine similarity between consecutive sentences (interpretable, scikit-learn is
a core dep). When the ``[nlp]`` extra brings sentence-transformers, a dense-embedding path catches
*rephrased* redundancy (the same idea in different words) that TF-IDF misses; TF-IDF stays the
fallback. Score is the fraction of adjacent sentence pairs above a similarity threshold.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from slopscore.document import Document
from slopscore.features._nlp import embed, is_embeddings_available
from slopscore.features.base import register
from slopscore.models import Dimension, FeatureResult

_SIMILARITY_THRESHOLD = 0.6
# Dense embeddings (MiniLM) score paraphrases higher than TF-IDF; a higher bar avoids flagging
# merely on-topic adjacent sentences. Measured: rephrased redundancy ~0.53-0.56, while clean
# non-native and simple-English adjacent pairs stay <=0.30, so 0.50 separates them with headroom
# and keeps the fairness gate green.
_EMBED_THRESHOLD = 0.5


def _embedding_redundancy(sentences: list[str]) -> float | None:
    try:
        emb = embed(tuple(sentences))
        sims = [float(emb[i] @ emb[i + 1]) for i in range(len(sentences) - 1)]
    except Exception:
        return None
    return float(np.mean([s >= _EMBED_THRESHOLD for s in sims])) if sims else 0.0


class Redundancy:
    dimension = Dimension.redundancy

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        sentences = [s.text for s in doc.sentences if s.text.strip()]
        if len(sentences) < 2:
            return FeatureResult(dimension=self.dimension, score=0.0, spans=[])

        if is_embeddings_available():
            score = _embedding_redundancy(sentences)
            if score is not None:
                return FeatureResult(dimension=self.dimension, score=score, spans=[])

        try:
            matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(sentences)
        except ValueError:
            # Empty vocabulary (e.g. all stopwords/punctuation).
            return FeatureResult(dimension=self.dimension, score=0.0, spans=[])

        sims = [
            float(cosine_similarity(matrix[i], matrix[i + 1])[0, 0])
            for i in range(len(sentences) - 1)
        ]
        redundant = np.mean([s >= _SIMILARITY_THRESHOLD for s in sims]) if sims else 0.0
        return FeatureResult(dimension=self.dimension, score=float(redundant), spans=[])


register(Redundancy())
