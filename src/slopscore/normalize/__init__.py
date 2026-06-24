"""Text normalization: encoding repair, offset-preserving cleaning, segmentation."""

from slopscore.normalize.clean import canonicalize, clean
from slopscore.normalize.language import detect_language
from slopscore.normalize.offsets import MappingBuilder, OffsetMapper
from slopscore.normalize.segment import split_paragraphs, split_sentences

__all__ = [
    "MappingBuilder",
    "OffsetMapper",
    "canonicalize",
    "clean",
    "detect_language",
    "split_paragraphs",
    "split_sentences",
]
