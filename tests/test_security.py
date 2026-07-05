"""Offline tests for the slopsquatting allowlist (validates security.feature)."""
from __future__ import annotations

from pathlib import Path

from techna import security

ROOT = Path(__file__).resolve().parent.parent


def _requirements_packages() -> list[str]:
    text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    return security.parse_requirements(text)


def test_requirements_parse_non_empty():
    assert _requirements_packages(), "requirements.txt parsed to no packages"


def test_every_requirement_is_approved():
    unapproved = [p for p in _requirements_packages()
                  if p not in security.APPROVED_PACKAGES]
    assert not unapproved, f"Unapproved packages present: {unapproved}"


def test_no_duplicate_requirements():
    pkgs = _requirements_packages()
    assert len(pkgs) == len(set(pkgs))


def test_canonicalization():
    assert security.canonical("Py_Test") == "py-test"
    assert security.canonical("  NumPy ") == "numpy"


def test_parser_ignores_comments_and_specifiers():
    text = "# a comment\npandas>=2.2,<3.0\n\nrich>=13.7\n-r other.txt\n"
    assert security.parse_requirements(text) == ["pandas", "rich"]
