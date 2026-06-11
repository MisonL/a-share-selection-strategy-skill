"""Symbol helpers that do not depend on dataframe libraries."""

from __future__ import annotations

from typing import Any


MISSING_TEXT_MARKERS = {"", "nan", "none", "null", "<na>"}
SH_SZ_EXCHANGES = ("sh", "sz")
A_SHARE_EXCHANGES = ("sh", "sz", "bj")


def parse_six_digit_symbols(
    text: str,
    *,
    allowed_exchanges: tuple[str, ...] = SH_SZ_EXCHANGES,
) -> list[str]:
    symbols = [
        normalize_prefixed_symbol(item.strip(), allowed_exchanges=allowed_exchanges)
        for item in text.split(",")
        if item.strip()
    ]
    if not symbols:
        raise ValueError("symbols must not be empty")
    invalid = [symbol for symbol in symbols if not symbol.isdigit() or len(symbol) != 6]
    if invalid:
        raise ValueError(f"symbols must be six digits: {','.join(invalid)}")
    return symbols


def parse_a_share_symbols(text: str) -> list[str]:
    return parse_six_digit_symbols(text, allowed_exchanges=A_SHARE_EXCHANGES)


def normalize_prefixed_symbol(
    value: Any,
    *,
    allowed_exchanges: tuple[str, ...] = SH_SZ_EXCHANGES,
) -> str:
    text = str(value).strip()
    if text.lower() in MISSING_TEXT_MARKERS:
        return ""
    prefixes = tuple(f"{exchange}." for exchange in allowed_exchanges)
    suffixes = tuple(f".{exchange}" for exchange in allowed_exchanges)
    if text.lower().startswith(prefixes):
        text = text.split(".", 1)[1]
    if text.lower().endswith(suffixes):
        text = text.rsplit(".", 1)[0]
    return text


def normalize_symbol_values(
    values: Any,
    *,
    allowed_exchanges: tuple[str, ...] = SH_SZ_EXCHANGES,
) -> list[str]:
    return [
        normalize_prefixed_symbol(value, allowed_exchanges=allowed_exchanges)
        for value in values
    ]


def baostock_code(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh.{symbol}"
    return f"sz.{symbol}"

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
