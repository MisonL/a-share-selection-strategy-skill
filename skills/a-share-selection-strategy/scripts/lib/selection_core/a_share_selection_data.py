"""Data parsing helpers for A-share selection scripts."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)


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
    text_columns = sorted(
        {
            *(
                column
                for column in frame.columns
                if isinstance(frame[column].dtype, pd.StringDtype)
            ),
            *(column for column in ("symbol", "name") if column in frame.columns),
        }
    )
    if not text_columns:
        return frame
    result = frame.copy()
    for column in text_columns:
        values = result[column].astype(object)
        if column == "symbol":
            values = result[column].astype(str).str.strip().astype(object)
        elif column == "name":
            values = values.map(text_value)
        result[column] = values
    return result


def text_value(value: object) -> object:
    if pd.isna(value):
        return value
    return str(value)


def parse_dates(series: pd.Series) -> pd.Series:
    """Parse dates in ACCEPTED_DATE_FORMATS; unsupported formats become NaT."""

    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    if len(series) and pd.api.types.is_string_dtype(series):
        iso = pd.to_datetime(series, format=ISO_DATE_FORMAT, errors="coerce")
        if not iso.isna().any():
            return iso
        compact = pd.to_datetime(series, format=COMPACT_DATE_FORMAT, errors="coerce")
        if not compact.isna().any():
            return compact
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
