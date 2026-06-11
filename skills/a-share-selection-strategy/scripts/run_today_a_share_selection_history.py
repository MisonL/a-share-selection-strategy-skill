"""History fetch and spot-derived symbol helpers for today's A-share runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from a_share_selection_symbols import (
    A_SHARE_EXCHANGES,
    SH_SZ_EXCHANGES,
    normalize_prefixed_symbol,
    normalize_symbol_values,
    parse_a_share_symbols,
    parse_six_digit_symbols,
)


DEFAULT_HISTORY_SYMBOL_LIMIT = 50
SYMBOL_COLUMN_ALIASES = ["symbol", "code", "code_id", "stock_code", "ticker", "Ticker"]
ZZSHARE_ONLY_HISTORY_OPTIONS = [
    "history_http_url",
    "history_timeout_seconds",
    "history_request_interval_seconds",
    "history_limit",
    "history_max_pages",
]


def validate_history_inputs(args: Any, spot: Path | None) -> None:
    if args.spot_input and args.fetch_spot:
        raise ValueError("use either --spot-input or --fetch-spot, not both")
    if args.prices_input:
        reject_ignored_history_options(args)
        return
    validate_history_required_inputs(args, spot)


def validate_history_required_inputs(args: Any, spot: Path | None) -> None:
    if args.prices_input:
        return
    missing = [
        name for name in ["history_source", "start_date", "end_date"] if not getattr(args, name)
    ]
    if missing:
        raise ValueError(
            "prices-input omitted; missing required history options: " + ",".join(missing)
        )
    if args.symbols and args.derive_symbols_from_spot:
        raise ValueError("use either --symbols or --derive-symbols-from-spot, not both")
    if not args.symbols and not args.derive_symbols_from_spot:
        raise ValueError("prices-input omitted; provide --symbols or --derive-symbols-from-spot")
    if args.derive_symbols_from_spot and spot is None:
        raise ValueError("--derive-symbols-from-spot requires --spot-input or --fetch-spot")
    if args.history_source != "zzshare":
        reject_zzshare_only_history_options(args)


def reject_ignored_history_options(args: Any) -> None:
    ignored = []
    for name in [
        "history_source",
        "symbols",
        "start_date",
        "end_date",
        "history_adjust",
        *ZZSHARE_ONLY_HISTORY_OPTIONS,
    ]:
        if option_configured(getattr(args, name)):
            ignored.append("--" + name.replace("_", "-"))
    for name in ["derive_symbols_from_spot", "allow_partial_history", "drop_invalid_history_rows"]:
        if getattr(args, name):
            ignored.append("--" + name.replace("_", "-"))
    if ignored:
        raise ValueError(
            "--prices-input was provided; history fetch options would be ignored: "
            + ",".join(ignored)
        )


def reject_zzshare_only_history_options(args: Any) -> None:
    ignored = option_flags(args, ZZSHARE_ONLY_HISTORY_OPTIONS)
    if ignored:
        raise ValueError(
            "zzshare-specific history options require --history-source zzshare: "
            + ",".join(ignored)
        )


def option_flags(args: Any, names: list[str]) -> list[str]:
    return [
        "--" + name.replace("_", "-")
        for name in names
        if option_configured(getattr(args, name))
    ]


def option_configured(value: Any) -> bool:
    return value is not None and value != ""


def history_symbols(
    args: Any,
    spot: Path | None,
    output: Path,
    config: Path,
) -> list[str]:
    if args.symbols:
        symbols = unique_symbols(parse_history_symbols(args))
        write_json(
            {"source": "explicit_symbols", "symbols": symbols},
            output / "selected_symbols.json",
        )
        return symbols
    if spot is None:
        raise ValueError("--derive-symbols-from-spot requires a spot snapshot")
    return derive_symbols_from_spot(args, spot, output, config)


def parse_history_symbols(args: Any) -> list[str]:
    if args.history_source == "zzshare":
        return parse_a_share_symbols(args.symbols)
    return parse_six_digit_symbols(args.symbols)


def unique_symbols(symbols: list[str]) -> list[str]:
    seen = set()
    result = []
    for symbol in symbols:
        if symbol in seen:
            continue
        result.append(symbol)
        seen.add(symbol)
    return result


def derive_symbols_from_spot(
    args: Any,
    spot: Path,
    output: Path,
    config_path: Path,
) -> list[str]:
    frame = read_spot_frame(spot)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    filtered = filter_spot_universe(frame, config, history_source=args.history_source)
    limit = int(args.max_history_symbols)
    ranked = rank_spot_candidates(filtered).head(limit)
    symbols = ranked["symbol"].astype(str).tolist()
    if not symbols:
        raise ValueError("spot snapshot produced zero history symbols after configured filters")
    write_json(
        spot_symbol_metadata(frame, filtered, ranked, config, limit),
        output / "selected_symbols.json",
    )
    return symbols


def read_spot_frame(path: Path):
    import pandas as pd

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str)
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
        if "symbol" in frame.columns:
            frame = frame.copy()
            frame["symbol"] = frame["symbol"].astype(str).str.strip()
        return frame
    raise ValueError("unsupported spot input format; use .csv, .parquet, or .pq")


def filter_spot_universe(frame, config: dict[str, Any], history_source: str = ""):
    result = normalize_spot_filter_frame(frame, history_source)
    thresholds = config.get("thresholds", {})
    result = result[result["symbol"].str.fullmatch(r"\d{6}", na=False)]
    result = apply_symbol_universe(result, config.get("universe", {}))
    if "min_close" in thresholds:
        result = result[result["spot_price"] >= float(thresholds["min_close"])]
    if "max_close" in thresholds:
        result = result[result["spot_price"] <= float(thresholds["max_close"])]
    if "min_amount" in thresholds:
        result = result[result["spot_amount"] >= float(thresholds["min_amount"])]
    if thresholds.get("exclude_st") and "name" in result:
        result = result[
            ~result["name"].astype(str).str.upper().str.match(r"^(?:\*?ST|SST)", na=False)
        ]
    return result.copy()


def normalize_spot_filter_frame(frame, history_source: str = ""):
    import pandas as pd

    result = frame.copy()
    result["symbol"] = normalize_symbol_values(
        first_existing_required(result, SYMBOL_COLUMN_ALIASES, "symbol"),
        allowed_exchanges=history_symbol_exchanges(history_source),
    )
    if "name" not in result:
        result["name"] = ""
    result["spot_price"] = pd.to_numeric(
        first_existing_required(result, ["spot_price", "price", "close"], "price"),
        errors="coerce",
    )
    result["spot_amount"] = pd.to_numeric(
        first_existing_required(result, ["spot_amount", "amount"], "amount"),
        errors="coerce",
    )
    result["spot_pct_chg"] = pd.to_numeric(
        first_existing(result, ["spot_pct_chg", "pct_chg", "pctChg", "change_pct"]),
        errors="coerce",
    )
    return result.dropna(subset=["spot_price", "spot_amount"])


def history_symbol_exchanges(history_source: str) -> tuple[str, ...]:
    return A_SHARE_EXCHANGES if history_source == "zzshare" else SH_SZ_EXCHANGES


def first_existing(frame, columns: list[str]):
    for column in columns:
        if column in frame:
            return frame[column]
    return [None] * len(frame)


def first_existing_required(frame, columns: list[str], label: str):
    for column in columns:
        if column in frame:
            return frame[column]
    raise ValueError(f"spot input requires {label} column; accepted aliases: {','.join(columns)}")


def apply_symbol_universe(frame, universe: dict[str, Any]):
    result = frame
    allow = universe.get("symbol_prefix_allow_regex")
    if allow:
        result = result[result["symbol"].str.match(str(allow), na=False)]
    excluded = tuple(str(item) for item in universe.get("symbol_prefix_exclude", []))
    if excluded:
        result = result[~result["symbol"].str.startswith(excluded)]
    return result


def rank_spot_candidates(frame):
    return frame.sort_values(["spot_amount", "spot_pct_chg"], ascending=[False, False])


def spot_symbol_metadata(frame, filtered, ranked, config: dict[str, Any], limit: int) -> dict[str, Any]:
    thresholds = config.get("thresholds", {})
    return {
        "source": "spot_snapshot",
        "filter_profile": config.get("profile_name", ""),
        "raw_spot_rows": int(len(frame)),
        "filtered_spot_rows": int(len(filtered)),
        "selected_symbols": ranked["symbol"].astype(str).tolist(),
        "selected_symbol_count": int(len(ranked)),
        "max_history_symbols": int(limit),
        "filters": {
            "universe": config.get("universe", {}),
            "thresholds": {
                key: thresholds.get(key)
                for key in ["min_close", "max_close", "min_amount", "exclude_st"]
                if key in thresholds
            },
        },
    }


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
