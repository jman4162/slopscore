"""The ``Document`` passed from ingest/normalize into the feature extractors."""

from __future__ import annotations

from dataclasses import dataclass, field

from slopscore.models import STANDARD_WARNINGS, Evidence, Severity, SourceType
from slopscore.normalize.offsets import OffsetMapper
from slopscore.spans import TextSpan


@dataclass
class Document:
    """Everything a feature extractor needs about one input.

    Features operate on ``cleaned_text`` and produce offsets in cleaned coordinates,
    then call :meth:`evidence` to map those back to the original source.
    """

    original_text: str
    cleaned_text: str
    mapper: OffsetMapper
    sentences: list[TextSpan] = field(default_factory=list)
    paragraphs: list[TextSpan] = field(default_factory=list)
    source_type: SourceType = SourceType.text
    source: str = "<string>"
    language: str = "en"
    language_confidence: float = 1.0

    @property
    def word_count(self) -> int:
        return len(self.cleaned_text.split())

    def evidence(
        self,
        rule_id: str,
        severity: Severity,
        clean_start: int,
        clean_end: int,
        explanation: str,
    ) -> Evidence:
        """Build an :class:`Evidence` from a span in cleaned coordinates.

        Offsets and the quoted span are mapped back to the original source so reports
        highlight the real bytes the user wrote.
        """
        orig_start, orig_end = self.mapper.to_original(clean_start, clean_end)
        return Evidence(
            rule_id=rule_id,
            severity=severity,
            span=self.original_text[orig_start:orig_end],
            start_char=orig_start,
            end_char=orig_end,
            explanation=explanation,
        )


__all__ = ["STANDARD_WARNINGS", "Document", "TextSpan"]
