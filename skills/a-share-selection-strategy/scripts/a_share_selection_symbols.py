"""Symbol helpers that do not depend on dataframe libraries."""

from __future__ import annotations

from typing import Any


MISSING_TEXT_MARKERS = {"", "nan", "none", "null", "<na>"}


def parse_six_digit_symbols(text: str) -> list[str]:
    symbols = [
        normalize_prefixed_symbol(item.strip())
        for item in text.split(",")
        if item.strip()
    ]
    if not symbols:
        raise ValueError("symbols must not be empty")
    invalid = [symbol for symbol in symbols if not symbol.isdigit() or len(symbol) != 6]
    if invalid:
        raise ValueError(f"symbols must be six digits: {','.join(invalid)}")
    return symbols


def normalize_prefixed_symbol(value: Any) -> str:
    text = str(value).strip()
    if text.lower() in MISSING_TEXT_MARKERS:
        return ""
    if text.lower().startswith(("sh.", "sz.")):
        text = text.split(".", 1)[1]
    if text.lower().endswith((".sh", ".sz")):
        text = text.rsplit(".", 1)[0]
    return text


def normalize_symbol_values(values: Any) -> list[str]:
    return [normalize_prefixed_symbol(value) for value in values]


def baostock_code(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh.{symbol}"
    return f"sz.{symbol}"
