"""Slopsquatting defense — verify every dependency BEFORE installing.

Run this before `pip install`. For each package listed in requirements.txt it:

  1. confirms the name is on Techna's curated allowlist (techna/security.py), and
  2. actively queries PyPI to confirm the project genuinely exists.

Exits non-zero if any package is unapproved or missing on PyPI, so it can
gate an automated setup pipeline. Standard library only — safe to run in a
bare interpreter before anything is installed.

Usage:
    python tools/verify_deps.py [path/to/requirements.txt]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the `techna` package importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from techna import security  # noqa: E402


def main(argv: list[str]) -> int:
    req_path = Path(argv[1]) if len(argv) > 1 else ROOT / "requirements.txt"
    if not req_path.exists():
        print(f"ERROR: requirements file not found: {req_path}")
        return 2

    packages = security.parse_requirements(req_path.read_text(encoding="utf-8"))
    if not packages:
        print(f"ERROR: no packages parsed from {req_path}")
        return 2

    print(f"Verifying {len(packages)} package(s) from {req_path.name}\n")
    print(f"  {'package':<16} {'approved':<10} {'on PyPI':<10} latest")
    print(f"  {'-'*16} {'-'*10} {'-'*10} {'-'*10}")

    problems = 0
    for name in packages:
        approved = name in security.APPROVED_PACKAGES
        try:
            exists, version = security.check_pypi_exists(name)
        except Exception as exc:  # network trouble — report, don't crash
            print(f"  {name:<16} {'yes' if approved else 'NO':<10} "
                  f"{'? ('+type(exc).__name__+')':<10}")
            problems += 1
            continue

        approved_s = "yes" if approved else "NO"
        exists_s = "yes" if exists else "MISSING"
        print(f"  {name:<16} {approved_s:<10} {exists_s:<10} {version or '-'}")
        if not approved or not exists:
            problems += 1

    print()
    if problems:
        print(f"FAILED: {problems} package(s) unapproved or missing on PyPI. "
              f"Aborting before install.")
        return 1

    print("OK: all dependencies are approved and exist on PyPI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
