"""Symbol helpers that do not depend on dataframe libraries."""

from __future__ import annotations

from typing import Any


MISSING_TEXT_MARKERS = {"", "nan", "none", "null", "<na>"}
SH_SZ_EXCHANGES = ("sh", "sz")
A_SHARE_EXCHANGES = ("sh", "sz", "bj")
BOARD_MAIN = "主板"
BOARD_CHINEXT = "创业板"
BOARD_STAR = "科创板"
BOARD_BSE = "北证"
BOARD_HK_MAIN = "港股主板"
BOARD_HK_GEM = "港股 GEM"
BOARD_UNKNOWN = "未知"
HK_MARKET_VALUES = {"hk", "hong kong", "hong-kong", "h-share", "港股", "香港"}


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


def normalize_hk_symbol(value: Any) -> str:
    text = str(value).strip()
    if text.lower() in MISSING_TEXT_MARKERS:
        return ""
    lower = text.lower()
    if lower.startswith("hk."):
        text = text.split(".", 1)[1]
    if lower.endswith(".hk"):
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


def stock_symbol_key(value: Any) -> str:
    symbol = str(value).strip().upper().replace("_", ".")
    if symbol.isdigit() and 1 <= len(symbol) <= 5:
        return normalized_market_symbol_key(symbol, "HK")
    if "." not in symbol:
        return symbol
    parts = [part for part in symbol.split(".") if part]
    if len(parts) < 2:
        return symbol
    market_prefixes = {"SH", "SZ", "BJ", "HK"}
    if parts[0] in market_prefixes:
        return normalized_market_symbol_key(parts[1], parts[0])
    if parts[-1] in market_prefixes:
        return normalized_market_symbol_key(parts[0], parts[-1])
    return symbol


def normalized_market_symbol_key(symbol: str, market: str) -> str:
    if market == "HK" and symbol.isdigit() and 1 <= len(symbol) <= 5:
        return symbol.zfill(5)
    return symbol


def baostock_code(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"sh.{symbol}"
    return f"sz.{symbol}"


def listing_board(symbol: Any, market: Any = "") -> str:
    if is_hk_market(market) or is_hk_symbol_text(symbol):
        return hk_listing_board(symbol)
    normalized = normalize_prefixed_symbol(
        symbol,
        allowed_exchanges=A_SHARE_EXCHANGES,
    )
    if not normalized.isdigit() or len(normalized) != 6:
        return BOARD_UNKNOWN
    if normalized.startswith("68"):
        return BOARD_STAR
    if normalized.startswith("30"):
        return BOARD_CHINEXT
    if normalized.startswith(("8", "4", "920")):
        return BOARD_BSE
    if normalized.startswith(("00", "60")):
        return BOARD_MAIN
    return BOARD_UNKNOWN


def listing_board_values(values: Any, markets: Any = None) -> list[str]:
    if markets is None:
        return [listing_board(value) for value in values]
    return [listing_board(value, market) for value, market in zip(values, markets)]


def hk_listing_board(symbol: Any) -> str:
    normalized = normalize_hk_symbol(symbol)
    if not normalized.isdigit():
        return BOARD_UNKNOWN
    code = normalized.zfill(5)
    number = int(code)
    if 8000 <= number <= 8999:
        return BOARD_HK_GEM
    if 1 <= number <= 9999:
        return BOARD_HK_MAIN
    return BOARD_UNKNOWN


def is_hk_market(value: Any) -> bool:
    return str(value).strip().lower() in HK_MARKET_VALUES


def is_hk_symbol_text(value: Any) -> bool:
    text = str(value).strip().lower()
    return text.startswith("hk.") or text.endswith(".hk")


def valid_hk_symbol_text(value: Any) -> bool:
    text = normalize_hk_symbol(value)
    return text.isdigit() and 1 <= len(text) <= 5 and int(text) > 0

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
