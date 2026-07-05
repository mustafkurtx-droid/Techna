"""Deterministically generate the golden_long price fixture.

Pure standard library (NO pandas/numpy) so it runs in any environment.
The close series is synthetically generated using a V-shape profile to guarantee
exactly one Golden Cross of SMA50 crossing above SMA200:

    - Days 0 to 179 (falling): Close[i] = 150.0 - i * 0.5
    - Days 180 to 269 (rising): Close[i] = Close[179] + (i - 179) * 2.0

Other OHLCV fields are derived using standard rules:
    Open[i] = Close[i-1] (Open[0] = Close[0])
    High[i] = max(Open[i], Close[i]) + 0.50
    Low[i] = min(Open[i], Close[i]) - 0.50
    Volume[i] = 1_000_000 + i * 1_000

Dates are consecutive weekdays starting 2024-01-02.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

START = date(2024, 1, 2)
LENGTH = 270


def weekdays(start: date, count: int) -> list[date]:
    """Return ``count`` consecutive weekday dates from ``start``."""
    out: list[date] = []
    day = start
    while len(out) < count:
        if day.weekday() < 5:  # Mon=0 .. Fri=4
            out.append(day)
        day += timedelta(days=1)
    return out


def generate_closes() -> list[float]:
    closes: list[float] = []
    for i in range(LENGTH):
        if i < 180:
            val = 150.0 - i * 0.5
        else:
            val = closes[179] + (i - 179) * 2.0
        closes.append(round(val, 2))
    return closes


def build_rows() -> list[list]:
    closes = generate_closes()
    dates = weekdays(START, LENGTH)
    rows: list[list] = []
    for i, close in enumerate(closes):
        open_ = closes[i - 1] if i > 0 else close
        high = round(max(open_, close) + 0.50, 2)
        low = round(min(open_, close) - 0.50, 2)
        volume = 1_000_000 + i * 1_000
        rows.append(
            [dates[i].isoformat(), round(open_, 2), high, low, round(close, 2), volume]
        )
    return rows


def find_cross_and_print_anchors():
    closes = generate_closes()
    sma50 = [None] * LENGTH
    sma200 = [None] * LENGTH
    
    for i in range(LENGTH):
        if i >= 49:
            sma50[i] = sum(closes[i-49:i+1]) / 50.0
        if i >= 199:
            sma200[i] = sum(closes[i-199:i+1]) / 200.0

    cross_index = None
    for i in range(200, LENGTH):
        prev_50 = sma50[i-1]
        prev_200 = sma200[i-1]
        curr_50 = sma50[i]
        curr_200 = sma200[i]
        if prev_50 <= prev_200 and curr_50 > curr_200:
            cross_index = i
            break

    print(f"SMA50 at index 199: {sma50[199]:.4f}")
    print(f"SMA200 at index 199: {sma200[199]:.4f}")
    if cross_index:
        print(f"Golden cross found at index {cross_index} (Day {cross_index + 1})")
        print(f"SMA50 at cross: {sma50[cross_index]:.4f}, SMA200 at cross: {sma200[cross_index]:.4f}")
    else:
        print("No Golden cross found!")


def main() -> Path:
    out = (
        Path(__file__).resolve().parent.parent
        / "tests"
        / "fixtures"
        / "golden_long.csv"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Date", "Open", "High", "Low", "Close", "Volume"])
        writer.writerows(build_rows())
    print(f"Wrote {LENGTH} rows -> {out}")
    find_cross_and_print_anchors()
    return out


if __name__ == "__main__":
    main()
