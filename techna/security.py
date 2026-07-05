"""Dependency provenance — defense against slopsquatting.

LLMs can hallucinate plausible-but-nonexistent package names; attackers
register those names on PyPI ("slopsquatting"). Techna guards against this
in two layers:

1. APPROVED_PACKAGES — a curated allowlist of packages we have deliberately
   chosen and verified as the genuine, intended PyPI projects. This is an
   OFFLINE guard enforced by the test suite: nothing outside this set may
   appear in requirements.

2. check_pypi_exists() — an ACTIVE network check (run by tools/verify_deps.py
   during setup) confirming each required name actually resolves on PyPI.

This module is standard-library only so it can run before anything is
installed.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import List, Optional, Tuple

# Canonical (PEP 503) names of every package Techna is allowed to install.
APPROVED_PACKAGES = {
    "yfinance",
    "pandas",
    "numpy",
    "matplotlib",
    "rich",
    "pytest",
    "statsmodels",
    "scipy",
    # Dev / quality tooling (not runtime; see requirements-dev.txt).
    "ruff",
    "mypy",
    "vulture",
    "pytest-cov",
    "pip-audit",
    # Notebook-authoring tooling (not runtime; see requirements-notebook.txt).
    # Used only to build/re-execute notebooks/proof_of_correctness.ipynb.
    "ta",
    "nbformat",
    "nbconvert",
    "ipykernel",
}

_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def canonical(name: str) -> str:
    """Normalize a distribution name per PEP 503 (lowercase, runs of
    -, _, . collapsed to a single hyphen)."""
    return re.sub(r"[-_.]+", "-", name.strip()).lower()


def parse_requirements(text: str) -> List[str]:
    """Extract canonical package names from a requirements file's text,
    ignoring blank lines, comments, and version specifiers."""
    names: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _NAME_RE.match(line)
        if match:
            names.append(canonical(match.group(1)))
    return names


def check_pypi_exists(name: str, timeout: int = 15) -> Tuple[bool, Optional[str]]:
    """Return (exists, latest_version) by querying the PyPI JSON API.

    A 404 means the project does not exist (the slopsquatting red flag).
    """
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
        return True, data.get("info", {}).get("version")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, None
        raise
