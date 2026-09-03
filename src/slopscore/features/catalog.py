"""Every rule id the registered features can emit.

Used to validate the names in inline suppression comments. Before this existed the known-name
set was built from the rules that fired in the current document, so a shared header such as
``<!-- slopscore-disable-file WEASEL_STUDIES_SHOW -->`` warned "Unknown name" in every file
where that rule happened not to fire.
"""

from __future__ import annotations

from functools import lru_cache

from slopscore.features.base import Cataloged, registry
from slopscore.models import Dimension


@lru_cache(maxsize=1)
def all_rule_ids() -> frozenset[str]:
    from slopscore.features.suggestions import suggestion_rule_ids

    ids: set[str] = set()
    for feature in registry():
        if isinstance(feature, Cataloged):
            ids |= feature.rule_ids()
    return frozenset(ids | suggestion_rule_ids())


def known_suppression_names() -> frozenset[str]:
    """Rule ids plus dimension names, the two things a suppression comment may name."""
    return all_rule_ids() | frozenset(d.value for d in Dimension)
