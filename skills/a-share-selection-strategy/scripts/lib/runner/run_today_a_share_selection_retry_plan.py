"""Pure retry-plan contracts shared by the recovery CLI and today's runner."""

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


from typing import Any


RETRY_METADATA_KEYS = [
    "failed_symbols",
    "empty_symbols",
    "possibly_truncated_symbols",
    "unprocessed_symbols",
]
DEFAULT_EXCLUDE_KEYS = [
    "invalid_symbols",
    "non_trading_symbols",
    "st_symbols",
]


def build_retry_plan(
    *,
    selected_data: dict[str, Any],
    metadata: dict[str, Any],
    include_clean_selected: bool,
) -> dict[str, Any]:
    selected = unique_symbols(selected_symbols(selected_data))
    selected_set = set(selected)
    retry_by_reason = retry_symbols_by_reason(metadata)
    blocked = symbols_for_keys(metadata, DEFAULT_EXCLUDE_KEYS)
    retry_candidates = unique_symbols(
        symbol
        for symbols in retry_by_reason.values()
        for symbol in symbols
    )
    unexpected = sorted(symbol for symbol in retry_candidates if symbol not in selected_set)
    retry = unique_symbols(
        symbol for symbol in retry_candidates if symbol in selected_set and symbol not in blocked
    )
    clean = [
        symbol
        for symbol in selected
        if symbol not in set(retry)
        and symbol not in blocked
        and not symbol_in_any_reason(symbol, retry_by_reason)
    ]
    if include_clean_selected:
        retry = unique_symbols([*retry, *clean])
    return {
        "source": "history_retry_plan",
        "selected_symbol_count": len(selected),
        "retry_symbols": retry,
        "retry_symbol_count": len(retry),
        "retry_symbols_csv": ",".join(retry),
        "retry_reasons": retry_by_reason,
        "retry_reason_counts": {
            key: len(value) for key, value in retry_by_reason.items()
        },
        "excluded_symbols": sorted(blocked),
        "excluded_symbol_count": len(blocked),
        "unexpected_metadata_symbols": unexpected,
        "unexpected_metadata_symbol_count": len(unexpected),
        "clean_selected_symbols": clean,
        "clean_selected_symbol_count": len(clean),
        "include_clean_selected": include_clean_selected,
        "claim_boundary": (
            "retry_plan_only_not_full_market_completion_or_history_fetch_success"
        ),
        "next_action": (
            "rerun_history_fetch_with_retry_symbols_then_revalidate_metadata"
        ),
    }


def selected_symbols(data: dict[str, Any]) -> list[str]:
    for key in ("selected_symbols", "symbols"):
        value = data.get(key)
        if isinstance(value, list):
            return normalize_symbol_items(value)
    return []


def normalize_symbol_items(items: list[Any]) -> list[str]:
    result = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("symbol", "")
        else:
            value = item
        text = str(value).strip()
        if text:
            result.append(text)
    return result


def retry_symbols_by_reason(metadata: dict[str, Any]) -> dict[str, list[str]]:
    return {
        key: sorted(symbols_for_keys(metadata, [key]))
        for key in RETRY_METADATA_KEYS
    }


def symbols_for_keys(metadata: dict[str, Any], keys: list[str]) -> set[str]:
    symbols: set[str] = set()
    for key in keys:
        symbols.update(metadata_symbols(metadata.get(key, [])))
    return symbols


def metadata_symbols(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    result = set()
    for item in value:
        if isinstance(item, dict):
            item = item.get("symbol", "")
        text = str(item).strip()
        if text:
            result.add(text)
    return result


def symbol_in_any_reason(symbol: str, retry_by_reason: dict[str, list[str]]) -> bool:
    return any(symbol in symbols for symbols in retry_by_reason.values())


def unique_symbols(symbols: Any) -> list[str]:
    seen = set()
    result = []
    for value in symbols:
        symbol = str(value).strip()
        if not symbol or symbol in seen:
            continue
        result.append(symbol)
        seen.add(symbol)
    return result
