"""Symbol helpers that do not depend on dataframe libraries."""

from __future__ import annotations


def parse_six_digit_symbols(text: str) -> list[str]:
    symbols = [item.strip() for item in text.split(",") if item.strip()]
    invalid = [symbol for symbol in symbols if not symbol.isdigit() or len(symbol) != 6]
    if invalid:
        raise ValueError(f"symbols must be six digits: {','.join(invalid)}")
    return symbols


def baostock_code(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh.{symbol}"
    return f"sz.{symbol}"
