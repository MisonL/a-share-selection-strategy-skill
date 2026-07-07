"""Date comparison helpers for walk-forward artifact validation."""

from __future__ import annotations

from typing import Any


def same_date_list(left: list[str], right: list[str]) -> bool:
    if len(left) != len(right):
        return False
    return all(
        same_calendar_date(left_date, right_date)
        for left_date, right_date in zip(left, right)
    )


def date_after(left: str | None, right: str | None) -> bool:
    left_date = parsed_calendar_date(left)
    right_date = parsed_calendar_date(right)
    return left_date is not None and right_date is not None and left_date > right_date


def same_calendar_date(left: str | None, right: str | None) -> bool:
    left_text = normalized_date_text(left)
    right_text = normalized_date_text(right)
    return left_text is not None and right_text is not None and left_text == right_text


def normalized_date_text(value: str | None) -> str | None:
    parsed = parsed_calendar_date(value)
    if parsed is None:
        return None
    return str(parsed.date())


def parsed_calendar_date(value: str | None) -> Any:
    if value is None or str(value).strip() == "":
        return None
    import pandas as pd
    from lib.selection_core.a_share_selection_data import parse_dates

    parsed = parse_dates(pd.Series([str(value)])).iloc[0]
    return None if pd.isna(parsed) else parsed
