"""Input preparation helpers for A-share selection scoring."""

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


import pandas as pd


BASE_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]


def prepare_frame(
    frame: pd.DataFrame,
    parse_dates,
    *,
    validated: bool = False,
) -> pd.DataFrame:
    if validated:
        typed = frame.copy(deep=False)
        typed["symbol"] = frame["symbol"].astype(str).str.strip()
        if not pd.api.types.is_datetime64_any_dtype(frame["date"]):
            parsed = parse_dates(frame["date"])
            if not parsed.isna().any():
                typed["date"] = parsed
        if _has_validated_dtypes(typed):
            return typed.sort_values(["symbol", "date"]).reset_index(drop=True)
    result = frame.copy()
    result = result.dropna(subset=["symbol"])
    result["symbol"] = result["symbol"].astype(str).str.strip()
    result = result[
        ~result["symbol"].str.lower().isin(["", "nan", "none", "null", "<na>"])
    ]
    result["date"] = parse_dates(result["date"])
    for column in numeric_columns():
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=BASE_COLUMNS)
    price_mask = (result[["open", "high", "low", "close"]] > 0).all(axis=1)
    result = result[price_mask & (result["volume"] >= 0)]
    return result.sort_values(["symbol", "date"]).reset_index(drop=True)


def _has_validated_dtypes(frame: pd.DataFrame) -> bool:
    if not pd.api.types.is_datetime64_any_dtype(frame["date"]):
        return False
    if not pd.api.types.is_string_dtype(frame["symbol"]):
        return False
    return all(
        pd.api.types.is_numeric_dtype(frame[column])
        for column in BASE_COLUMNS[2:]
    )


def numeric_columns() -> list[str]:
    return [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover",
        "turn",
        "prediction",
        "prediction_score",
    ]
