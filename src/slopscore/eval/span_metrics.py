"""Span-level precision/recall helpers (exact and IoU matching).

Infrastructure for evaluating evidence spans against gold annotations. v0.3 ships these helpers
plus a tiny golden fixture for regression; a full annotated span benchmark is a later milestone.
"""

from __future__ import annotations

Span = tuple[int, int]


def iou(a: Span, b: Span) -> float:
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def matches(pred: Span, gold: Span, *, mode: str = "exact", threshold: float = 0.5) -> bool:
    if mode == "exact":
        return pred == gold
    return iou(pred, gold) >= threshold


def precision_recall(
    pred: list[Span], gold: list[Span], *, mode: str = "exact", threshold: float = 0.5
) -> tuple[float, float]:
    """Set-level precision/recall; each gold span may be matched at most once."""
    remaining = list(gold)
    tp = 0
    for p in pred:
        for i, g in enumerate(remaining):
            if matches(p, g, mode=mode, threshold=threshold):
                tp += 1
                remaining.pop(i)
                break
    precision = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    recall = tp / len(gold) if gold else 1.0
    return precision, recall
