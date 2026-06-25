"""Code ingestion: extract the PROSE inside source files (docstrings, comments, JSDoc).

slopscore lints writing, not control flow. This adapter pulls the natural-language prose out of
code so `scan file.py` flags slop in docstrings and comments while ignoring the code itself.

Like the Markdown adapter, offsets in the resulting report index the EXTRACTED prose, not the
original source bytes (so report line numbers are relative to the extracted prose). Python uses the
stdlib `ast` (docstrings) + `tokenize` (comments); JS/TS use a best-effort comment regex.
"""

from __future__ import annotations

import ast
import io
import tokenize

import regex as re

from slopscore.ingest import RawSource
from slopscore.models import SourceType

_PY_SUFFIXES = {".py", ".pyi"}
_JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
CODE_SUFFIXES = _PY_SUFFIXES | _JS_SUFFIXES


def _py_docstrings(src: str) -> list[str]:
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            doc = ast.get_docstring(node, clean=True)
            if doc and doc.strip():
                out.append(doc.strip())
    return out


def _py_comments(src: str) -> list[str]:
    out: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                text = tok.string.lstrip("#").strip()
                if text:
                    out.append(text)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return out


def _python_prose(src: str) -> list[str]:
    return _py_docstrings(src) + _py_comments(src)


# Best-effort: /* ... */ and /** ... */ block comments, and // line comments. Strips markers and
# leading "*" gutters. Does not parse strings, so it will not catch comment-like text in strings.
_BLOCK = re.compile(r"/\*+(.*?)\*+/", re.DOTALL)
_LINE = re.compile(r"(?<![:/])//[ \t]?(.*)")  # avoid http:// ; not perfect


def _js_prose(src: str) -> list[str]:
    out: list[str] = []
    for m in _BLOCK.finditer(src):
        lines = [ln.strip().lstrip("*").strip() for ln in m.group(1).splitlines()]
        text = " ".join(ln for ln in lines if ln)
        if text:
            out.append(text)
    src_no_block = _BLOCK.sub("", src)
    for m in _LINE.finditer(src_no_block):
        text = m.group(1).strip()
        if text:
            out.append(text)
    return out


def code_to_prose(src: str, suffix: str) -> str:
    suffix = suffix.lower()
    if suffix in _PY_SUFFIXES:
        blocks = _python_prose(src)
    elif suffix in _JS_SUFFIXES:
        blocks = _js_prose(src)
    else:
        blocks = _python_prose(src)  # default to the Python extractor
    return "\n\n".join(blocks)


def is_code_suffix(suffix: str) -> bool:
    return suffix.lower() in _PY_SUFFIXES | _JS_SUFFIXES


def ingest_code(src: str, suffix: str = ".py", source: str = "<string>") -> RawSource:
    return RawSource(
        text=code_to_prose(src, suffix),
        source_type=SourceType.code,
        source=source,
    )
