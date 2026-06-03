"""Data parsing helpers for stock selection scripts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype={"symbol": str})
    if suffix in {".parquet", ".pq"}:
        return ensure_symbol_text(pd.read_parquet(path))
    raise ValueError("unsupported input format; use .csv, .parquet, or .pq")


def ensure_symbol_text(frame: pd.DataFrame) -> pd.DataFrame:
    if "symbol" not in frame.columns:
        return frame
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str).str.strip()
    return result


def parse_dates(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    numeric_yyyymmdd = text.str.fullmatch(r"\d{8}")
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if numeric_yyyymmdd.any():
        parsed.loc[numeric_yyyymmdd] = pd.to_datetime(
            text[numeric_yyyymmdd],
            format="%Y%m%d",
            errors="coerce",
        )
    other = ~numeric_yyyymmdd
    if other.any():
        parsed.loc[other] = pd.to_datetime(text[other], errors="coerce")
    return parsed
