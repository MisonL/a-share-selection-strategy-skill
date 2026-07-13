"""Shared OHLCV validation helpers."""

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


from typing import Iterable

from lib.selection_core.a_share_selection_symbols import (
    is_hk_market,
    is_hk_symbol_text,
)


REQUIRED_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
PRICE_COLUMNS = ["open", "high", "low", "close"]
MAX_ERROR_EXAMPLES = 5
VOLUME_UNIT_VERIFICATION = "not_verified_by_cli"


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    global pd, parse_dates, profile_column_errors, prediction_value_errors
    import pandas as pandas_module
    from lib.selection_core.a_share_selection_data import parse_dates as parse_dates_fn
    from lib.selection_core.a_share_selection_profile import (
        profile_column_errors as profile_column_errors_fn,
    )
    from lib.selection_core.a_share_selection_profile import (
        prediction_value_errors as prediction_value_errors_fn,
    )

    pd = pandas_module
    parse_dates = parse_dates_fn
    profile_column_errors = profile_column_errors_fn
    prediction_value_errors = prediction_value_errors_fn


def validate_frame(frame: pd.DataFrame, min_history_rows: int) -> list[str]:
    ensure_runtime_dependencies()
    errors: list[str] = []
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        errors.append(f"missing required columns: {', '.join(missing)}")
        errors.extend(validate_available_columns(frame, min_history_rows))
        return errors
    if frame.empty:
        return ["input data is empty"]

    errors.extend(validate_required_values(frame))
    errors.extend(validate_symbols(frame))
    errors.extend(validate_numeric_values(frame))
    errors.extend(validate_dates(frame))
    errors.extend(validate_duplicates(frame))
    errors.extend(validate_history(frame, min_history_rows=min_history_rows))
    return errors


def validate_available_columns(
    frame: pd.DataFrame,
    min_history_rows: int,
) -> Iterable[str]:
    if "symbol" in frame:
        yield from validate_symbols(frame)
    if "date" in frame:
        yield from validate_dates(frame)
    for column in [*PRICE_COLUMNS, "volume"]:
        if column in frame:
            yield from validate_numeric_column(frame, column)
    if {"symbol", "date"}.issubset(frame.columns):
        yield from validate_duplicates(frame)
    if "symbol" in frame:
        yield from validate_history(frame, min_history_rows=min_history_rows)


def validate_required_values(frame: pd.DataFrame) -> Iterable[str]:
    for column in REQUIRED_COLUMNS:
        mask = frame[column].isna()
        missing_count = int(mask.sum())
        if missing_count:
            yield (
                f"column {column} has {missing_count} missing values"
                f"{error_examples(frame, mask, field=column)}"
            )


def validate_symbols(frame: pd.DataFrame) -> Iterable[str]:
    symbols = frame["symbol"].astype(str).str.strip()
    empty_count = int((symbols == "").sum())
    if empty_count:
        yield (
            f"column symbol has {empty_count} empty values"
            f"{error_examples(frame, symbols == '')}"
        )
    hk_context = hk_symbol_context(frame, symbols)
    damaged = symbols.str.fullmatch(r"(?:\d{1,5}|\d+\.0+)", na=False) & ~hk_context
    damaged_count = int(damaged.sum())
    if damaged_count:
        yield (
            f"column symbol has {damaged_count} values that look numeric-damaged; "
            "preserve leading zeros as text"
            f"{error_examples(frame, damaged)}"
        )


def hk_symbol_context(frame: pd.DataFrame, symbols: pd.Series) -> pd.Series:
    symbol_markers = symbols.map(is_hk_symbol_text)
    if "market" not in frame.columns:
        return symbol_markers
    markets = frame["market"].map(is_hk_market)
    return symbol_markers | markets


def validate_numeric_values(frame: pd.DataFrame) -> Iterable[str]:
    for column in [*PRICE_COLUMNS, "volume"]:
        yield from validate_numeric_column(frame, column)


def validate_numeric_column(frame: pd.DataFrame, column: str) -> Iterable[str]:
    values = pd.to_numeric(frame[column], errors="coerce")
    invalid_count = int(values.isna().sum())
    if invalid_count:
        yield (
            f"column {column} has {invalid_count} non-numeric values"
            f"{error_examples(frame, values.isna(), field=column)}"
        )
    if column in PRICE_COLUMNS:
        mask = values <= 0
        non_positive = int(mask.sum())
        if non_positive:
            yield (
                f"column {column} has {non_positive} non-positive values"
                f"{error_examples(frame, mask, field=column)}"
            )
    else:
        mask = values < 0
        negative = int(mask.sum())
        if negative:
            yield (
                f"column {column} has {negative} negative values"
                f"{error_examples(frame, mask, field=column)}"
            )


def validate_dates(frame: pd.DataFrame) -> Iterable[str]:
    dates = parse_dates(frame["date"])
    invalid_count = int(dates.isna().sum())
    if invalid_count:
        yield (
            f"column date has {invalid_count} invalid values"
            f"{error_examples(frame, dates.isna(), field='date')}"
        )


def validate_duplicates(frame: pd.DataFrame) -> Iterable[str]:
    checked = frame[["symbol"]].copy()
    checked["symbol"] = checked["symbol"].astype(str).str.strip()
    checked["date"] = parse_dates(frame["date"])
    checked = checked.dropna(subset=["date"])
    duplicated = checked.duplicated(subset=["symbol", "date"], keep=False)
    duplicate_count = int(checked.duplicated(subset=["symbol", "date"]).sum())
    if duplicate_count:
        yield (
            f"found {duplicate_count} duplicate symbol/date rows"
            f"{duplicate_examples(frame, checked[duplicated])}"
        )


def error_examples(
    frame: pd.DataFrame,
    mask: pd.Series,
    *,
    field: str | None = None,
) -> str:
    rows = []
    selected = frame.loc[mask.fillna(False)].head(MAX_ERROR_EXAMPLES)
    for index, row in selected.iterrows():
        item = example_base(index, row)
        if field:
            item.append(f"{field}={display_value(row.get(field, ''))}")
        rows.append(",".join(item))
    return format_examples(rows)


def duplicate_examples(frame: pd.DataFrame, duplicates: pd.DataFrame) -> str:
    rows = []
    for index, row in duplicates.head(MAX_ERROR_EXAMPLES).iterrows():
        source = frame.loc[index]
        item = example_base(index, source)
        item.append(f"normalized_date={row['date'].date().isoformat()}")
        rows.append(",".join(item))
    return format_examples(rows)


def example_base(index: object, row: pd.Series) -> list[str]:
    return [
        f"row={csv_line(index)}",
        f"symbol={display_value(row.get('symbol', ''))}",
        f"date={display_value(row.get('date', ''))}",
    ]


def csv_line(index: object) -> int:
    try:
        return int(index) + 2
    except (TypeError, ValueError):
        return 0


def display_value(value: object) -> str:
    text = str(value)
    return text.replace(",", "\\,").replace("\n", "\\n")


def format_examples(rows: list[str]) -> str:
    if not rows:
        return ""
    return " examples=" + " | ".join(rows)


def validate_history(frame: pd.DataFrame, min_history_rows: int) -> Iterable[str]:
    counts = frame.groupby("symbol", dropna=False).size()
    short = counts[counts < min_history_rows]
    if not short.empty:
        examples = ", ".join(
            f"{symbol}:{count}" for symbol, count in short.head(10).items()
        )
        yield (
            f"{len(short)} symbols have fewer than {min_history_rows} rows ({examples})"
        )


def validate_profile_columns(frame: pd.DataFrame, config: dict) -> Iterable[str]:
    ensure_runtime_dependencies()
    errors = profile_column_errors(frame, config)
    errors.extend(prediction_value_errors(frame, config))
    return errors
