"""Shared fixtures: representative clean / slop / markdown samples."""

from __future__ import annotations

import pytest

SLOP_TEXT = (
    "In today's fast-paced digital landscape, it is crucial to leverage robust, "
    "cutting-edge tools. Whether you're a beginner or an expert, this comprehensive "
    "guide will delve into the intricate tapestry of solutions. Ultimately, technology "
    "has revolutionized industries. Moreover, it is a game-changer. Let's delve into the "
    "details. At its core, innovation underscores transformative potential. Furthermore, "
    "it empowers everyone. This offering is more than just software. The platform stands "
    "as a testament to modern engineering and plays a pivotal role in shaping the future. "
    "Experts argue that it reflects a broader movement toward seamless, holistic design. "
    "It is not just a tool, it is a revolution, fostering a vibrant, dynamic, and "
    "transformative ecosystem. Marking a significant shift, the solution serves as a "
    "cornerstone, highlighting its enduring significance and contributing to the broader "
    "landscape of innovation across the industry."
)

CLEAN_TEXT = (
    "The Golden Gate Bridge opened in 1937 after four years of construction. Workers "
    "poured 389,000 cubic yards of concrete into its towers. Joseph Strauss, the chief "
    "engineer, fought the Navy for two years over the design. On a clear day you can see "
    "Point Reyes, 30 miles to the north. The original toll was 50 cents each way. "
    "Construction began in January 1933. The two towers rise 746 feet above the water. "
    "The bridge used about 83,000 tons of steel, most of it shipped from mills in "
    "Pennsylvania. Eleven workers died during the build, ten of them on a single day in "
    "February 1937 when a scaffold fell through the safety net. The lead engineer, "
    "Charles Ellis, did much of the math but received no credit until decades later. "
    "Today roughly 110,000 vehicles cross it each day."
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
