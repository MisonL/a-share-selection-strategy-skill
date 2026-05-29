#!/usr/bin/env python3
"""Create deterministic demo OHLCV CSV files for quick-start smoke tests."""

from __future__ import annotations

import argparse
import csv
import math
from datetime import date, timedelta
from pathlib import Path


FIELDNAMES = [
    "symbol",
    "name",
    "market",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turn",
    "prediction_score",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create demo stock selection CSV data.")
    parser.add_argument(
        "--output",
        default="/tmp/stock-selection-demo",
        help="Directory for prices.csv and prices_with_prediction.csv.",
    )
    args = parser.parse_args(argv)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "prices.csv", include_prediction=False)
    write_csv(output / "prices_with_prediction.csv", include_prediction=True)
    print(f"OK: wrote demo data to {output}")
    return 0


def write_csv(path: Path, *, include_prediction: bool) -> None:
    columns = FIELDNAMES if include_prediction else FIELDNAMES[:-1]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in demo_rows(include_prediction=include_prediction):
            writer.writerow({key: row[key] for key in columns})


def demo_rows(*, include_prediction: bool) -> list[dict[str, str]]:
    rows = []
    symbols = [("000002", "Demo Shenzhen", 8.0, 0.72), ("600001", "Demo Shanghai", 10.0, 0.68)]
    for symbol, name, base, prediction in symbols:
        for index, day in enumerate(business_dates(date(2025, 1, 2), 130)):
            close = base + index * 0.018 + math.sin(index / 9) * 0.08
            row = {
                "symbol": symbol,
                "name": name,
                "market": "A-share",
                "date": day.isoformat(),
                "open": f"{close * 0.997:.4f}",
                "high": f"{close * 1.012:.4f}",
                "low": f"{close * 0.988:.4f}",
                "close": f"{close:.4f}",
                "volume": str(120000 + index * 30),
                "turn": f"{1.1 + math.cos(index / 11) * 0.03:.4f}",
            }
            if include_prediction:
                row["prediction_score"] = f"{prediction:.4f}"
            rows.append(row)
    return rows


def business_dates(start: date, count: int) -> list[date]:
    days = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


if __name__ == "__main__":
    raise SystemExit(main())
