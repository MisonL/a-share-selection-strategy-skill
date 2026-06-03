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
    "amount",
    "turn",
    "tradestatus",
    "isST",
    "prediction_score",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create demo stock selection CSV data. prices.csv is for generic and "
            "low-price gates. prices_with_prediction.csv includes synthetic "
            "prediction_score and may trigger prediction-derived auto mode; it does not prove "
            "that LightGBM ran."
        )
    )
    parser.add_argument(
        "--output",
        default="/tmp/stock-selection-demo",
        help="Directory for prices.csv and prices_with_prediction.csv.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=130,
        help="Business-day rows to generate per symbol. Default: 130.",
    )
    parser.add_argument(
        "--scenario",
        choices=["basic", "low-price-ultra-short"],
        default="basic",
        help="Demo scenario to generate. Default: basic.",
    )
    args = parser.parse_args(argv)
    if args.days < 1:
        raise ValueError("days must be >= 1")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(
        output / "prices.csv",
        include_prediction=False,
        days=args.days,
        scenario=args.scenario,
    )
    write_csv(
        output / "prices_with_prediction.csv",
        include_prediction=True,
        days=args.days,
        scenario=args.scenario,
    )
    print(f"OK: wrote demo data to {output}")
    return 0


def write_csv(
    path: Path, *, include_prediction: bool, days: int, scenario: str
) -> None:
    columns = FIELDNAMES if include_prediction else FIELDNAMES[:-1]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in demo_rows(
            include_prediction=include_prediction,
            days=days,
            scenario=scenario,
        ):
            writer.writerow({key: row[key] for key in columns})


def demo_rows(
    *, include_prediction: bool, days: int, scenario: str
) -> list[dict[str, str]]:
    if scenario == "low-price-ultra-short":
        return low_price_ultra_short_rows(
            include_prediction=include_prediction,
            days=days,
        )
    return basic_rows(include_prediction=include_prediction, days=days)


def basic_rows(*, include_prediction: bool, days: int) -> list[dict[str, str]]:
    rows = []
    symbols = [("000002", "Demo Shenzhen", 6.0, 0.72), ("600001", "Demo Shanghai", 8.0, 0.68)]
    for symbol, name, base, prediction in symbols:
        for index, day in enumerate(business_dates(date(2025, 1, 2), days)):
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
                "amount": f"{150000000 + index * 100000:.2f}",
                "turn": f"{1.1 + math.cos(index / 11) * 0.03:.4f}",
                "tradestatus": "1",
                "isST": "0",
            }
            if include_prediction:
                row["prediction_score"] = f"{prediction:.4f}"
            rows.append(row)
    return rows


def low_price_ultra_short_rows(
    *, include_prediction: bool, days: int
) -> list[dict[str, str]]:
    rows = []
    for spec in low_price_specs():
        for index, day in enumerate(business_dates(date(2025, 1, 2), days)):
            rows.append(
                low_price_row(
                    spec=spec,
                    index=index,
                    days=days,
                    day=day,
                    include_prediction=include_prediction,
                )
            )
    return rows


def low_price_specs() -> list[dict[str, object]]:
    return [
        symbol_spec("000002", "Low Price Pass", 5.2, 150000000.0, 1.25, "1", "0"),
        symbol_spec("000003", "High Price Reject", 10.8, 150000000.0, 1.25, "1", "0"),
        symbol_spec("000004", "Amount Reject", 5.4, 50000000.0, 1.25, "1", "0"),
        symbol_spec("000005", "Turn Reject", 5.6, 150000000.0, 0.35, "1", "0"),
        symbol_spec("000006", "ST Reject", 5.8, 150000000.0, 1.25, "1", "1"),
        symbol_spec("000007", "Suspended Reject", 6.0, 150000000.0, 1.25, "0", "0"),
        symbol_spec(
            "000008",
            "One Word Bar Reject",
            6.2,
            150000000.0,
            1.25,
            "1",
            "0",
            one_word_bar=True,
        ),
    ]


def symbol_spec(
    symbol: str,
    name: str,
    base: float,
    amount: float,
    turn: float,
    tradestatus: str,
    is_st: str,
    *,
    one_word_bar: bool = False,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": name,
        "base": base,
        "amount": amount,
        "turn": turn,
        "tradestatus": tradestatus,
        "isST": is_st,
        "one_word_bar": one_word_bar,
    }


def low_price_row(
    *,
    spec: dict[str, object],
    index: int,
    days: int,
    day: date,
    include_prediction: bool,
) -> dict[str, str]:
    base = float(spec["base"])
    close = base + index * 0.01 + math.sin(index / 8) * 0.06
    open_price = close * 0.997
    high = close * 1.012
    low = close * 0.988
    if bool(spec.get("one_word_bar")) and index == days - 1:
        open_price = high = low = close
    row = {
        "symbol": str(spec["symbol"]),
        "name": str(spec["name"]),
        "market": "A-share",
        "date": day.isoformat(),
        "open": f"{open_price:.4f}",
        "high": f"{high:.4f}",
        "low": f"{low:.4f}",
        "close": f"{close:.4f}",
        "volume": str(150000 + index * 40),
        "amount": f"{float(spec['amount']) + index * 1000:.2f}",
        "turn": f"{float(spec['turn']):.4f}",
        "tradestatus": str(spec["tradestatus"]),
        "isST": str(spec["isST"]),
    }
    if include_prediction:
        row["prediction_score"] = "0.7000"
    return row


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
