"""Generate a stable i.i.d. return series for econometrics tests with a fixed seed."""
from __future__ import annotations

import csv
import datetime
import random
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "tests" / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "golden_returns.csv"
    
    rng = random.Random(42)
    start_date = datetime.date(2024, 1, 2)
    
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Return"])
        for i in range(250):
            # Generate i.i.d. normal-like returns
            r = rng.normalvariate(0.0005, 0.015)
            date_str = (start_date + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            writer.writerow([date_str, f"{r:.8f}"])
            
    print(f"Generated {out_file}")


if __name__ == "__main__":
    main()
