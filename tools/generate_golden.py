"""Deterministically generate the golden price fixture.

Pure standard library (NO pandas/numpy) so it runs in any environment and
produces byte-identical output every time. The close series is an explicit
hardcoded list — fully auditable by eye — and the other OHLCV fields are
derived from it by simple, stated rules:

    Open[i]  = Close[i-1]   (Open[0] = Close[0])
    High[i]  = max(Open[i], Close[i]) + 0.50
    Low[i]   = min(Open[i], Close[i]) - 0.50
    Volume[i] = 1_000_000 + i * 1_000

Dates are consecutive weekdays (Mon-Fri) starting 2024-01-02.

Run:  python tools/generate_golden.py
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

# 40 hand-picked daily closes: a gentle uptrend with regular pullbacks,
# enough variety to exercise trend and momentum indicators later.
CLOSES = [
    100.00, 101.50, 102.00, 101.00, 103.50, 104.00, 103.00, 105.50,
    106.00, 107.50, 106.50, 108.00, 109.50, 108.50, 110.00, 111.50,
    110.50, 112.00, 111.00, 113.50, 112.50, 114.00, 113.00, 115.50,
    114.50, 116.00, 115.00, 117.50, 116.50, 118.00, 117.00, 119.50,
    118.50, 120.00, 119.00, 121.50, 120.50, 122.00, 121.00, 123.50,
]

START = date(2024, 1, 2)


def weekdays(start: date, count: int) -> list[date]:
    """Return ``count`` consecutive weekday dates from ``start``."""
    out: list[date] = []
    day = start
    while len(out) < count:
        if day.weekday() < 5:  # Mon=0 .. Fri=4
            out.append(day)
        day += timedelta(days=1)
    return out


def build_rows() -> list[list]:
    dates = weekdays(START, len(CLOSES))
    rows: list[list] = []
    for i, close in enumerate(CLOSES):
        open_ = CLOSES[i - 1] if i > 0 else close
        high = round(max(open_, close) + 0.50, 2)
        low = round(min(open_, close) - 0.50, 2)
        volume = 1_000_000 + i * 1_000
        rows.append(
            [dates[i].isoformat(), round(open_, 2), high, low, round(close, 2), volume]
        )
    return rows


def main() -> Path:
    out = (
        Path(__file__).resolve().parent.parent
        / "tests"
        / "fixtures"
        / "golden_prices.csv"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        writer.writerows(build_rows())
    print(f"Wrote {len(CLOSES)} rows -> {out}")
    return out


if __name__ == "__main__":
    main()
