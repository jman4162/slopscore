"""Redundancy: adjacent-sentence semantic overlap (thin v0.1 implementation).

Uses TF-IDF cosine similarity between consecutive sentences — interpretable and dependency-light
(scikit-learn is a core dep). Dense sentence-transformer embeddings are deferred to the ``[nlp]``
extra in v0.2. Score is the fraction of adjacent pairs above a similarity threshold.
"""

from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from slopscore.document import Document
from slopscore.features.base import register
from slopscore.models import Dimension, FeatureResult

_SIMILARITY_THRESHOLD = 0.6


class Redundancy:
    dimension = Dimension.redundancy

    def extract(self, doc: Document, profile: str) -> FeatureResult:
        sentences = [s.text for s in doc.sentences if s.text.strip()]
        if len(sentences) < 2:
            return FeatureResult(dimension=self.dimension, score=0.0, spans=[])
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
