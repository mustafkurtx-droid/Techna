"""Live smoke test for the data layer (requires network + installed deps).

Fetches a real ticker through techna.data_layer.get_prices, prints a small
summary with rich, and demonstrates that the second call is served from the
on-disk cache rather than the network.

Usage:
    python tools/smoke_fetch.py [TICKER]      # default: AAPL
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from techna import data_layer as dl  # noqa: E402


def main(argv: list[str]) -> int:
    ticker = argv[1] if len(argv) > 1 else "AAPL"
    console = Console()

    try:
        first = dl.get_prices(ticker, min_rows=5)
        second = dl.get_prices(ticker, min_rows=5)
    except dl.DataLayerError as exc:
        console.print(f"[red]Data layer error:[/red] {exc}")
        return 1

    table = Table(title=f"Techna data-layer smoke test: {first.ticker}")
    table.add_column("field")
    table.add_column("value", justify="right")
    table.add_row("rows", str(len(first)))
    table.add_row("first call source", first.source)
    table.add_row("second call source", second.source)
    table.add_row("date range",
                  f"{first.df.index.min().date()} -> {first.df.index.max().date()}")
    table.add_row("last close", f"{first.df['Close'].iloc[-1]:.2f}")
    console.print(table)

    if first.warnings:
        console.print("[yellow]Warnings:[/yellow] " + "; ".join(first.warnings))

    if second.source != "cache":
        console.print("[red]Expected second call to be served from cache.[/red]")
        return 1
    console.print("[green]OK[/green] — second call served from cache.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
