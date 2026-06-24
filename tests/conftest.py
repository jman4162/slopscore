"""Shared fixtures: representative clean / slop / markdown samples."""

from __future__ import annotations

import pytest

SLOP_TEXT = (
    "In today's fast-paced digital landscape, it is crucial to leverage robust, "
    "cutting-edge tools. Whether you're a beginner or an expert, this comprehensive "
    "guide will delve into the intricate tapestry of solutions. Ultimately, technology "
    "has revolutionized industries. Moreover, it is a game-changer. Let's delve into the "
    "details. At its core, innovation underscores transformative potential. Furthermore, "
    "it empowers everyone. This offering is more than just software."
)

CLEAN_TEXT = (
    "The Golden Gate Bridge opened in 1937 after four years of construction. Workers "
    "poured 389,000 cubic yards of concrete into its towers. Joseph Strauss, the chief "
    "engineer, fought the Navy for two years over the design. On a clear day you can see "
    "Point Reyes, 30 miles to the north. The original toll was 50 cents each way."
)

RESIDUE_TEXT = (
    "Certainly! Here is a revised version of your essay. As an AI language model, I have "
    "improved the flow. Let me know if you would like any changes. I hope this helps."
)

MARKDOWN_TEXT = """\
# Heading

This is a real paragraph with the word delve in it.

```python
# this code mentions crucial robust delve but must be ignored
x = "delve delve delve"
```

> A blockquote that mentions tapestry should be skipped.

Another paragraph here.
"""


@pytest.fixture
def slop_text() -> str:
    return SLOP_TEXT


@pytest.fixture
def clean_text() -> str:
    return CLEAN_TEXT


@pytest.fixture
def residue_text() -> str:
    return RESIDUE_TEXT


@pytest.fixture
def markdown_text() -> str:
    return MARKDOWN_TEXT
