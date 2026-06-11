"""Data parsing helpers for A-share selection scripts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


COMPACT_DATE_FORMAT = "%Y%m%d"
ISO_DATE_FORMAT = "%Y-%m-%d"
ACCEPTED_DATE_FORMATS = (COMPACT_DATE_FORMAT, ISO_DATE_FORMAT)


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype={"symbol": str, "name": str})
    if suffix in {".parquet", ".pq"}:
        return ensure_text_columns(pd.read_parquet(path))
    raise ValueError("unsupported input format; use .csv, .parquet, or .pq")


def ensure_text_columns(frame: pd.DataFrame) -> pd.DataFrame:
    text_columns = [column for column in ("symbol", "name") if column in frame.columns]
    if not text_columns:
        return frame
    result = frame.copy()
    if "symbol" in text_columns:
        result["symbol"] = result["symbol"].astype(str).str.strip()
    if "name" in text_columns:
        result["name"] = result["name"].map(text_value)
    return result


def text_value(value: object) -> object:
    if pd.isna(value):
        return value
    return str(value)


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse dates in ACCEPTED_DATE_FORMATS; unsupported formats become NaT."""

    text = series.astype(str).str.strip()
    numeric_yyyymmdd = text.str.fullmatch(r"\d{8}")
    iso_yyyy_mm_dd = text.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if numeric_yyyymmdd.any():
        parsed.loc[numeric_yyyymmdd] = pd.to_datetime(
            text[numeric_yyyymmdd],
            format=COMPACT_DATE_FORMAT,
            errors="coerce",
        )
    if iso_yyyy_mm_dd.any():
        parsed.loc[iso_yyyy_mm_dd] = pd.to_datetime(
            text[iso_yyyy_mm_dd],
            format=ISO_DATE_FORMAT,
            errors="coerce",
        )
    return parsed

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
