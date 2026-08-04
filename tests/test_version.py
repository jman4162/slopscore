"""Guards against the package version drifting from the distribution metadata.

0.9.0 shipped with ``__version__ = "0.8.1"`` hand-written in ``slopscore/__init__.py``. That
value is not cosmetic: ``report/sarif.py`` publishes it as ``tool.driver.version``, so every
SARIF upload from that release told code scanning it came from 0.8.1.
"""

from __future__ import annotations

import json
from importlib.metadata import version as distribution_version

import slopscore
from slopscore.core import scan_text
from slopscore.report.sarif import to_sarif


def test_version_matches_distribution_metadata() -> None:
    # Holds by construction while __init__ reads the metadata. The point is that it stops
    # holding the moment someone puts a literal back, which is how the drift happened.
    assert slopscore.__version__ == distribution_version("slopscore-lint")


def test_version_is_not_the_uninstalled_placeholder() -> None:
    # The test suite always runs against an installed package, so the PackageNotFoundError
    # fallback in __init__ must never be what we ship.
    assert slopscore.__version__ != "0.0.0.dev0"


def test_sarif_reports_the_installed_version() -> None:
    report = scan_text("The clerk fixed the form on 3 March and the queue cleared by noon.")
    sarif = json.loads(json.dumps(to_sarif(report)))
    driver = sarif["runs"][0]["tool"]["driver"]
    assert driver["version"] == distribution_version("slopscore-lint")
