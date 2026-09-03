"""Redundancy: adjacent-sentence overlap, lexical or structural.

Default path (numpy only): TF-IDF cosine similarity between consecutive sentences over stopword-
filtered unigrams and bigrams, plus a token-alignment check that catches TEMPLATED neighbours:
sentences that reuse the same frame with the slots swapped ("The get_user function returns a user
object. The get_group function returns a group object."). TF-IDF alone misses those, because the
swapped slot words dominate the vector and IDF down-weights the shared frame.

When the ``[nlp]`` extra brings sentence-transformers, a dense-embedding path catches *rephrased*
redundancy (the same idea in different words) that neither lexical measure sees; the numpy path
stays the fallback. Score is the fraction of adjacent sentence pairs above a threshold.

scikit-learn used to provide the TF-IDF and was therefore a required dependency of a package whose
scan path is meant to be numpy-only; it is now an ``[eval]`` extra.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import pairwise

import numpy as np
import regex as re

from slopscore.document import Document
from slopscore.features._nlp import embed, is_embeddings_available
from slopscore.features.base import register
from slopscore.models import Dimension, FeatureResult

_SIMILARITY_THRESHOLD = 0.6
# Fraction of aligned tokens (longest common subsequence over the longer sentence) at or above
# which two neighbours share a frame. Ordinary adjacent prose sits around 0.2-0.35 because only
# function words align; templated pairs sit above 0.7.
_FRAME_THRESHOLD = 0.6
# Frame alignment needs enough tokens to mean anything; very short sentences ("I like it. I
# like them.") are ordinary in plain and non-native English and must not count.
_FRAME_MIN_TOKENS = 6
# Dense embeddings (MiniLM) score paraphrases higher than TF-IDF; a higher bar avoids flagging
# merely on-topic adjacent sentences. Measured: rephrased redundancy ~0.53-0.56, while clean
# non-native and simple-English adjacent pairs stay <=0.30, so 0.50 separates them with headroom
# and keeps the fairness gate green.
_EMBED_THRESHOLD = 0.5

_TOKEN = re.compile(r"[a-z0-9][a-z0-9'_-]*")
_STOPWORDS = frozenset(
    """a an the and or but if so of to in on at by for from with as is are was were be been
    being it its this that these those there here he she they we you i me him her them us my
    your his their our not no nor do does did done have has had can could will would shall
    should may might must than then when where which who whom whose what why how all any each
    every some such only own same too very just also into onto over under up down out about
    after before between through during while because until again further once""".split()
)


def _tokens(sentence: str) -> list[str]:
    return list(_TOKEN.findall(sentence.lower()))


def _content_features(tokens: list[str]) -> Counter[str]:
    content = [t for t in tokens if t not in _STOPWORDS]
    feats: Counter[str] = Counter(content)
    feats.update(f"{a} {b}" for a, b in pairwise(content))
    return feats


def _tfidf_cosines(sentences: list[str]) -> list[float]:
    docs = [_content_features(_tokens(s)) for s in sentences]
    vocab: dict[str, int] = {}
    df: Counter[str] = Counter()
    for d in docs:
        for term in d:
            vocab.setdefault(term, len(vocab))
            df[term] += 1
    if not vocab:
        return [0.0] * (len(sentences) - 1)
    n = len(docs)
    idf = np.array([math.log((1 + n) / (1 + df[t])) + 1.0 for t in vocab], dtype=float)
    matrix = np.zeros((n, len(vocab)), dtype=float)
    for i, d in enumerate(docs):
        for term, count in d.items():
            matrix[i, vocab[term]] = count
    matrix *= idf
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    matrix /= norms[:, None]
    return [float(matrix[i] @ matrix[i + 1]) for i in range(n - 1)]


def _lcs_length(a: list[str], b: list[str]) -> int:
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, start=1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


def _frame_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if min(len(ta), len(tb)) < _FRAME_MIN_TOKENS:
        return 0.0
    return _lcs_length(ta, tb) / max(len(ta), len(tb))


def _embedding_redundancy(sentences: list[str]) -> float | None:
    try:
        emb = embed(tuple(sentences))
        sims = [float(emb[i] @ emb[i + 1]) for i in range(len(sentences) - 1)]
    except Exception:
        return None
    return float(np.mean([s >= _EMBED_THRESHOLD for s in sims])) if sims else 0.0


def lexical_redundancy(sentences: list[str]) -> float:
    """Fraction of adjacent pairs that are lexically or structurally redundant (numpy path)."""
    if len(sentences) < 2:
        return 0.0
    cosines = _tfidf_cosines(sentences)
    frames = [_frame_similarity(a, b) for a, b in pairwise(sentences)]
    flags = [
        c >= _SIMILARITY_THRESHOLD or f >= _FRAME_THRESHOLD
        for c, f in zip(cosines, frames, strict=True)
    ]
    return float(np.mean(flags)) if flags else 0.0


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

        return FeatureResult(
            dimension=self.dimension, score=lexical_redundancy(sentences), spans=[]
        )


register(Redundancy())
