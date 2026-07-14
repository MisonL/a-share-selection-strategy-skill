"""Optional local prices filtering for today's A-share runner."""

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


from datetime import datetime
from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_symbols import (
    stock_symbol_key,
    symbol_set_sha256,
)


CLAIM_BOUNDARY = "local_prices_filtered_from_existing_artifacts_not_new_history_fetch"
SPOT_SYMBOL_COLUMNS = ("symbol", "code", "code_id", "stock_code", "ticker", "Ticker")
FILTER_EMPTY_ERROR = "local prices filters removed all price symbols"


class PricesFilterError(ValueError):
    def __init__(self, message: str, metadata: dict[str, Any]) -> None:
        super().__init__(message)
        self.metadata = dict(metadata)


def filter_local_prices(
    *,
    prices: Path,
    spot: Path | None,
    output_dir: Path,
    filter_spot_universe: bool,
    min_symbol_latest_date: str,
) -> tuple[Any, dict[str, Any]]:
    price_frame = read_table(prices)
    if "symbol" not in price_frame:
        raise ValueError("prices input missing symbol column")
    price_keys, symbols_by_key = normalized_price_data(price_frame["symbol"])
    min_latest_date = normalize_filter_date(min_symbol_latest_date)
    filter_plan = build_filter_plan(
        price_frame=price_frame,
        price_keys=price_keys,
        symbols_by_key=symbols_by_key,
        spot=spot,
        filter_spot_universe=filter_spot_universe,
        min_latest_date=min_latest_date,
    )
    keep_mask = filter_plan["keep_mask"]
    kept_keys = [key for keep, key in zip(keep_mask, price_keys) if keep]
    kept = (
        price_frame
        if all(filter_plan["keep_mask"])
        else price_frame.loc[filter_plan["keep_mask"]].copy()
    )
    metadata = filter_metadata(
        prices=prices,
        spot=spot,
        output_dir=output_dir,
        filter_spot_universe=filter_spot_universe,
        min_latest_date=min_latest_date,
        price_frame=price_frame,
        kept=kept,
        price_keys=price_keys,
        kept_keys=kept_keys,
        spot_keys=filter_plan["spot_keys"],
        removed_universe_symbols=filter_plan["removed_universe_symbols"],
        removed_stale_symbols=filter_plan["removed_stale_symbols"],
    )
    if kept.empty:
        metadata["prices_filter_output_written"] = False
        metadata["prices_filter_failure_reason"] = "all_price_symbols_removed"
        metadata["prices_filter_error"] = FILTER_EMPTY_ERROR
        raise PricesFilterError(FILTER_EMPTY_ERROR, metadata)
    return kept, metadata


def build_filter_plan(
    *,
    price_frame: Any,
    price_keys: list[str],
    symbols_by_key: dict[str, str],
    spot: Path | None,
    filter_spot_universe: bool,
    min_latest_date: str,
) -> dict[str, Any]:
    keep_mask = [True] * len(price_keys)
    spot_keys: set[str] = set()
    removed_universe_symbols: list[str] = []
    removed_stale_symbols: list[str] = []
    if filter_spot_universe:
        if spot is None:
            raise ValueError("--filter-prices-to-spot-universe requires spot artifact")
        spot_keys = read_spot_keys(spot)
        keep_mask = [
            keep and key in spot_keys for keep, key in zip(keep_mask, price_keys)
        ]
        removed_universe_symbols = removed_price_symbols(symbols_by_key, spot_keys)
    if min_latest_date:
        stale_keys = stale_price_keys(
            price_frame,
            price_keys,
            symbols_by_key,
            min_latest_date,
        )
        keep_mask = [
            keep and key not in stale_keys for keep, key in zip(keep_mask, price_keys)
        ]
        removed_stale_symbols = symbols_for_keys(symbols_by_key, stale_keys)
    return {
        "keep_mask": keep_mask,
        "spot_keys": spot_keys,
        "removed_universe_symbols": removed_universe_symbols,
        "removed_stale_symbols": removed_stale_symbols,
    }


def filter_metadata(
    *,
    prices: Path,
    spot: Path | None,
    output_dir: Path,
    filter_spot_universe: bool,
    min_latest_date: str,
    price_frame: Any,
    kept: Any,
    price_keys: list[str],
    kept_keys: list[str],
    spot_keys: set[str],
    removed_universe_symbols: list[str],
    removed_stale_symbols: list[str],
) -> dict[str, Any]:
    removed_symbols = sorted(set(removed_universe_symbols + removed_stale_symbols))
    input_symbols = set(price_keys)
    kept_symbols = set(kept_keys)
    removed_symbol_keys = input_symbols.difference(kept_symbols)
    metadata_path = output_dir / "prices_filter.json"
    return {
        "source": "prices_local_filter",
        "source_claim_boundary": CLAIM_BOUNDARY,
        "prices_filter_spot_universe": bool(filter_spot_universe),
        "prices_filter_min_symbol_latest_date": min_latest_date,
        "prices_filter_source_prices": str(prices),
        "prices_filter_source_spot": str(spot) if spot else "",
        "prices_filter_input_rows": int(len(price_frame)),
        "prices_filter_output_rows": int(len(kept)),
        "prices_filter_spot_symbol_count": len(spot_keys),
        "prices_filter_input_symbol_count": len(input_symbols),
        "prices_filter_input_symbol_set_sha256": symbol_set_sha256(input_symbols),
        "prices_filter_spot_symbol_set_sha256": symbol_set_sha256(spot_keys),
        "prices_filter_kept_symbol_count": len(kept_symbols),
        "prices_filter_kept_symbol_set_sha256": symbol_set_sha256(kept_symbols),
        "prices_filter_removed_symbol_count": len(removed_symbols),
        "prices_filter_removed_symbols": removed_symbols,
        "prices_filter_removed_symbol_set_sha256": symbol_set_sha256(
            removed_symbol_keys
        ),
        "prices_filter_removed_stale_symbol_count": len(removed_stale_symbols),
        "prices_filter_removed_stale_symbols": removed_stale_symbols,
        "prices_filter_output_written": True,
        "prices_filter_failure_reason": "",
        "prices_filter_error": "",
        "prices_filter_metadata_output": str(metadata_path),
    }


def read_spot_keys(spot: Path) -> set[str]:
    spot_frame = read_table(spot)
    spot_column = first_existing_column(spot_frame, SPOT_SYMBOL_COLUMNS)
    spot_keys = normalized_keys(spot_frame[spot_column].tolist())
    if not spot_keys:
        raise ValueError("spot universe has no valid symbols")
    return spot_keys


def read_table(path: Path) -> Any:
    from lib.selection_core.a_share_selection_data import read_table as read_data_table

    return read_data_table(path)


def first_existing_column(frame: Any, columns: tuple[str, ...]) -> str:
    for column in columns:
        if column in frame:
            return column
    raise ValueError(
        "spot input requires symbol column; accepted aliases: " + ",".join(columns)
    )


def normalized_keys(values: list[Any]) -> set[str]:
    return {key for key in (stock_symbol_key(value) for value in values) if key}


def normalized_price_data(series: Any) -> tuple[list[str], dict[str, str]]:
    raw = series.astype(str).str.strip()
    mapping = {
        value: stock_symbol_key(value)
        for value in raw.drop_duplicates().tolist()
    }
    symbols_by_key: dict[str, str] = {}
    for symbol, key in mapping.items():
        symbols_by_key.setdefault(key, symbol)
    return raw.map(mapping).tolist(), symbols_by_key


def removed_price_symbols(
    symbols_by_key: dict[str, str],
    spot_keys: set[str],
) -> list[str]:
    return sorted(
        symbol for key, symbol in symbols_by_key.items() if key not in spot_keys
    )


def stale_price_keys(
    frame: Any,
    price_keys: list[str],
    symbols_by_key: dict[str, str],
    min_latest_date: str,
) -> set[str]:
    if "date" not in frame:
        raise ValueError("--min-symbol-latest-date requires date column")
    from lib.selection_core.a_share_selection_data import parse_dates

    dates = parse_dates(frame["date"])
    if dates.isna().any():
        invalid_keys = {
            price_keys[position]
            for position, is_invalid in enumerate(dates.isna().tolist())
            if is_invalid
        }
        invalid = symbols_for_keys(symbols_by_key, invalid_keys)
        raise ValueError(
            "prices input has invalid date values for symbols: " + ",".join(invalid[:20])
        )
    latest_by_key = dates.groupby(price_keys).max()
    return {
        str(key)
        for key, latest in latest_by_key.items()
        if latest.date().isoformat() < min_latest_date
    }


def symbols_for_keys(symbols_by_key: dict[str, str], keys: set[str]) -> list[str]:
    return sorted(symbol for key, symbol in symbols_by_key.items() if key in keys)


def normalize_filter_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = text.replace("-", "")
    if not compact.isdigit() or len(compact) != 8:
        raise ValueError("--min-symbol-latest-date must be YYYY-MM-DD or YYYYMMDD")
    try:
        return datetime.strptime(compact, "%Y%m%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("--min-symbol-latest-date must be a real calendar date") from exc
