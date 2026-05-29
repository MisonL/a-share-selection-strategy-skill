"""Data parsing helpers for stock selection scripts."""

from __future__ import annotations

import pandas as pd


def parse_dates(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    numeric_yyyymmdd = text.str.fullmatch(r"\d{8}")
    parsed = pd.to_datetime(text, errors="coerce")
    if numeric_yyyymmdd.any():
        parsed.loc[numeric_yyyymmdd] = pd.to_datetime(
            text[numeric_yyyymmdd],
            format="%Y%m%d",
            errors="coerce",
        )
    return parsed
