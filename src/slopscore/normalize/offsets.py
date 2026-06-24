"""Map character offsets in cleaned text back to the original source.

Cleaning (encoding fixes, whitespace collapse, dropping Markdown code blocks) shifts and
deletes characters. Features run on the cleaned text but every evidence span must point at
the bytes the user actually wrote. :class:`OffsetMapper` records, for each character in the
cleaned text, the index it came from in the original.
"""

from __future__ import annotations

from collections.abc import Sequence


class OffsetMapper:
    """Maps cleaned-text offsets to original-text offsets.

    ``clean_to_orig[i]`` is the original index of cleaned character ``i``. The array has
    ``len(cleaned) + 1`` entries; the final sentinel is ``len(original)`` so that an
    end-exclusive cleaned offset maps to a valid end-exclusive original offset.
    """

    def __init__(self, original_len: int, clean_to_orig: Sequence[int]) -> None:
        self._orig_len = original_len
        self._map: list[int] = list(clean_to_orig)

    def to_original(self, clean_start: int, clean_end: int) -> tuple[int, int]:
        """Map an end-exclusive cleaned span to an end-exclusive original span."""
        if clean_start < 0 or clean_end < clean_start:
            raise ValueError(f"invalid span ({clean_start}, {clean_end})")
        last = len(self._map) - 1
        start = self._map[min(clean_start, last)]
        # End is exclusive: map the last included char, then extend to its end.
        if clean_end <= clean_start:
            return start, start
        end_inclusive = self._map[min(clean_end - 1, last)]
        return start, end_inclusive + 1

    @property
    def original_length(self) -> int:
        return self._orig_len


class MappingBuilder:
    """Accumulate cleaned text while tracking each char's original index.

    Cleaning code appends either kept characters (with their source index) or replacement
    characters (e.g. a collapsed run of whitespace) that point at a representative source
    index. Call :meth:`build` to finalize.
    """

    def __init__(self, original: str) -> None:
        self._original = original
        self._chars: list[str] = []
        self._map: list[int] = []

    def keep(self, char: str, orig_index: int) -> None:
        self._chars.append(char)
        self._map.append(orig_index)

    def emit(self, char: str, orig_index: int) -> None:
        """Append a substituted character mapped to a representative source index."""
        self._chars.append(char)
        self._map.append(orig_index)

    @property
    def cleaned(self) -> str:
        return "".join(self._chars)

    def build(self) -> tuple[str, OffsetMapper]:
        sentinel = self._map[-1] + 1 if self._map else 0
        sentinel = min(sentinel, len(self._original))
        return self.cleaned, OffsetMapper(len(self._original), [*self._map, sentinel])
