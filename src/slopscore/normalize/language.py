"""Language detection, used to lower confidence on non-English text.

Detection requires the optional ``[lang]`` extra (lingua). Without it, we assume English
with neutral confidence rather than failing — the confidence model simply can't down-weight
non-English text it can't detect.
"""

from __future__ import annotations


def detect_language(text: str) -> tuple[str, float]:
    """Return an ISO 639-1 code and a [0, 1] confidence.

    Falls back to ``("en", 1.0)`` when the ``[lang]`` extra is not installed or the text is
    too short to judge.
    """
    if len(text.split()) < 20:
        return "en", 0.5
    try:
        from lingua import LanguageDetectorBuilder
    except ImportError:
        return "en", 1.0

    detector = LanguageDetectorBuilder.from_all_languages().build()
    value = detector.compute_language_confidence_values(text)
    if not value:
        return "en", 1.0
    top = value[0]
    code = top.language.iso_code_639_1.name.lower()
    return code, float(top.value)
