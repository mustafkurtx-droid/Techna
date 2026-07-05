"""The shared I/O contract every Techna module returns.

Each indicator/analysis module accepts a ticker, reads from the shared
data layer, and returns BOTH a markdown report (on disk) and a structured
result dict in exactly this shape::

    {
        "module":      str,          # e.g. "rsi"
        "ticker":      str,          # normalized symbol
        "status":      str,          # "ok" | "warning" | "error"
        "metrics":     dict,         # numeric results computed by Python only
        "report_path": str | None,   # path to the markdown report, if written
        "warnings":    list[str],    # human-readable caveats
    }

Keeping this in one helper guarantees the contract stays consistent across
every module that will be added in later phases.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VALID_STATUSES = ("ok", "warning", "error")

# Status precedence for rolling several module results into one overall status.
_STATUS_RANK = {"ok": 0, "warning": 1, "error": 2}


def make_result(
    module: str,
    ticker: str,
    *,
    status: str = "ok",
    metrics: Optional[Dict[str, Any]] = None,
    report_path: Optional[str] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a result dict that conforms to the Techna I/O contract."""
    if status not in VALID_STATUSES:
        raise ValueError(
            f"status must be one of {VALID_STATUSES}, got {status!r}."
        )
    return {
        "module": module,
        "ticker": ticker,
        "status": status,
        "metrics": dict(metrics or {}),
        "report_path": report_path,
        "warnings": list(warnings or []),
    }


def _json_safe(obj: Any) -> Any:
    """Recursively coerce a value into something json.dumps can emit cleanly.

    NaN/inf become null, tuples become lists, numpy scalars become Python
    scalars, and anything else unknown falls back to its string form.
    """
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        try:
            return _json_safe(obj.item())
        except Exception:
            return str(obj)
    return str(obj)


def overall_status(module_results: List[Dict[str, Any]]) -> str:
    """Return the worst status across the given module results."""
    worst = "ok"
    for res in module_results:
        if _STATUS_RANK.get(res.get("status", "ok"), 0) > _STATUS_RANK[worst]:
            worst = res["status"]
    return worst


def write_results_json(
    out_dir: Path | str,
    ticker: str,
    report_path: Optional[str],
    module_results: List[Dict[str, Any]],
    warnings: Optional[List[str]] = None,
    data_provenance: Optional[Dict[str, Any]] = None,
) -> str:
    """Write the structured half of the I/O contract: one JSON file aggregating
    every module's result dict. Returns the path written.

    This is the machine-readable companion to the markdown report — fulfilling
    the contract's promise that every run yields BOTH a report and structured
    results (consumable by scanners, CI, downstream tooling).

    ``data_provenance`` (source/date-range/benchmark/etc.) is written once at
    the top level rather than duplicated per module — every number in every
    module's metrics was computed from this same input, so it belongs here,
    not repeated 19 times.
    """
    out_path = Path(out_dir) / f"{ticker.upper()}_result.json"
    payload = {
        "ticker": ticker,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "report_path": str(report_path) if report_path else None,
        "status": overall_status(module_results),
        "warnings": list(warnings or []),
        "data_provenance": _json_safe(data_provenance) if data_provenance else None,
        "modules": [_json_safe(r) for r in module_results],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(out_path)
