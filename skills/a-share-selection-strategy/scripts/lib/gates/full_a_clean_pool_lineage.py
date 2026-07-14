"""Validate full-A history freshness and clean-pool row lineage."""

from __future__ import annotations

from typing import Any


def symbols_before_as_of_date(frame: Any, as_of_date: str) -> list[str]:
    dates = frame["date"].astype(str).str.strip().str.replace("-", "", regex=False)
    normalized = frame.assign(
        _date=dates,
        _symbol=frame["symbol"].astype(str).str.strip(),
    )
    latest = normalized.groupby("_symbol", sort=False)["_date"].max()
    expected = as_of_date.replace("-", "")
    return sorted(str(symbol) for symbol, value in latest.items() if value != expected)


def validate_clean_history_lineage(
    history: Any,
    clean: Any,
    removed_symbols: set[str],
) -> None:
    if list(history.columns) != list(clean.columns):
        raise ValueError("clean prices columns do not match history prices")
    retained = history.loc[
        ~history["symbol"].astype(str).isin(removed_symbols),
        list(history.columns),
    ].reset_index(drop=True)
    actual = clean.reset_index(drop=True)
    if len(retained) != len(actual):
        raise ValueError("clean prices rows do not match history minus removals")
    for column in clean.columns:
        left = comparable_series(retained[column], column)
        right = comparable_series(actual[column], column)
        equal = left.eq(right) | (left.isna() & right.isna())
        if not bool(equal.fillna(False).all()):
            raise ValueError(
                f"clean prices content does not match history minus removals: {column}"
            )


def comparable_series(series: Any, column: str) -> Any:
    if column == "symbol":
        return series.astype(str).str.strip()
    if column == "date":
        return series.astype(str).str.strip().str.replace("-", "", regex=False)
    return series
