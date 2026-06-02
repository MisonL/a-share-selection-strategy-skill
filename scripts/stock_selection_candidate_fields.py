"""Candidate gate fields derived from the latest input row."""

from __future__ import annotations

from typing import Any

import pandas as pd


GATE_COLUMNS = ["amount", "tradestatus", "isST", "one_word_bar"]


def merge_latest_gate_fields(scored: pd.DataFrame, input_frame: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return scored
    latest = latest_gate_view(input_frame)
    return scored.merge(latest, on="symbol", how="left")


def latest_gate_view(input_frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in input_frame.groupby("symbol", sort=False):
        latest = group.iloc[-1]
        rows.append(
            {
                "symbol": str(latest["symbol"]),
                "amount": numeric_value(latest, "amount"),
                "tradestatus": text_value(latest, "tradestatus"),
                "isST": text_value(latest, "isST"),
                "one_word_bar": one_word_bar(latest),
            }
        )
    return pd.DataFrame(rows, columns=["symbol", *GATE_COLUMNS])


def numeric_value(row: pd.Series, column: str) -> float:
    if column not in row:
        return float("nan")
    value = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
    return float(value) if pd.notna(value) else float("nan")


def text_value(row: pd.Series, column: str) -> str:
    if column not in row or pd.isna(row[column]):
        return ""
    return str(row[column]).strip()


def one_word_bar(row: pd.Series) -> bool:
    values = [numeric_value(row, column) for column in ["open", "high", "low", "close"]]
    if any(pd.isna(value) for value in values):
        return False
    return max(values) == min(values)
