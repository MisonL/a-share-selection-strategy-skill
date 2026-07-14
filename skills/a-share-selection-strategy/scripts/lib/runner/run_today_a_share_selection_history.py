"""History fetch and spot-derived symbol helpers for today's A-share runner."""

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


import importlib.util
import json
import re
from pathlib import Path
from typing import Any

from lib.runner.run_today_a_share_selection_helpers import option_configured
from lib.selection_core.a_share_selection_symbols import (
    A_SHARE_EXCHANGES,
    is_hk_market,
    normalize_hk_symbol,
    SH_SZ_EXCHANGES,
    normalize_prefixed_symbol,
    normalize_symbol_values,
    parse_a_share_symbols,
    parse_six_digit_symbols,
    valid_hk_symbol_text,
)


DEFAULT_HISTORY_SYMBOL_LIMIT = 50
AKSHARE_HK_DAILY_SOURCE = "akshare_hk_daily"
SYMBOL_COLUMN_ALIASES = ["symbol", "code", "code_id", "stock_code", "ticker", "Ticker"]
ZZSHARE_ONLY_HISTORY_OPTIONS = [
    "history_http_url",
    "history_timeout_seconds",
    "history_request_interval_seconds",
    "history_max_concurrent_symbol_requests",
    "history_max_rate_limit_sleep_seconds",
    "history_max_429_events",
    "history_max_runtime_seconds",
    "history_limit",
    "history_max_pages",
    "history_non_trading_policy",
    "history_checkpoint_batch_size",
    "history_resume_from_checkpoint",
    "history_progress_interval",
]
YFINANCE_UNSUPPORTED_HISTORY_OPTIONS = [
    "history_adjust",
    "drop_invalid_history_rows",
]
PYTDX_UNSUPPORTED_HISTORY_OPTIONS = [
    "history_adjust",
]
HISTORY_OUTPUT_FORMATS = {"csv", "parquet", "pq"}


def validate_history_inputs(args: Any, spot: Path | None) -> None:
    if args.spot_input and args.fetch_spot:
        raise ValueError("use either --spot-input or --fetch-spot, not both")
    if args.fetch_spot_fallback and not args.fetch_spot:
        raise ValueError("--fetch-spot-fallback requires --fetch-spot")
    if args.fetch_spot_fallback and args.fetch_spot_fallback == args.fetch_spot:
        raise ValueError("--fetch-spot-fallback must differ from --fetch-spot")
    if args.prices_input:
        reject_ignored_history_options(args)
        return
    validate_history_required_inputs(args, spot)


def validate_history_required_inputs(args: Any, spot: Path | None) -> None:
    if args.prices_input:
        return
    missing = [
        name
        for name in ["history_source", "start_date", "end_date"]
        if not getattr(args, name)
    ]
    if missing:
        raise ValueError(
            "prices-input omitted; missing required history options: "
            + ",".join(missing)
        )
    if args.symbols and getattr(args, "symbols_file", None):
        raise ValueError("use either --symbols or --symbols-file, not both")
    if explicit_symbol_input_configured(args) and args.derive_symbols_from_spot:
        raise ValueError(
            "use explicit symbol input or --derive-symbols-from-spot, not both"
        )
    if not explicit_symbol_input_configured(args) and not args.derive_symbols_from_spot:
        raise ValueError(
            "prices-input omitted; provide --symbols, --symbols-file, or "
            "--derive-symbols-from-spot"
        )
    if args.derive_symbols_from_spot and spot is None:
        raise ValueError(
            "--derive-symbols-from-spot requires --spot-input or --fetch-spot"
        )
    if args.derive_all_spot_symbols and not args.derive_symbols_from_spot:
        raise ValueError(
            "--derive-all-spot-symbols requires --derive-symbols-from-spot"
        )
    if args.history_source == "yfinance":
        reject_yfinance_unsupported_history_options(args)
    if args.history_source == "pytdx":
        reject_pytdx_unsupported_history_options(args)
    if (
        args.history_output_format
        and args.history_output_format not in HISTORY_OUTPUT_FORMATS
    ):
        raise ValueError("history-output-format must be csv, parquet, or pq")
    if args.history_output_format and args.history_source != "baostock":
        raise ValueError(
            "--history-output-format requires --history-source baostock"
        )
    if (
        args.history_output_format in {"parquet", "pq"}
        and not parquet_engine_available()
    ):
        raise RuntimeError(
            "Parquet history output requires pyarrow or fastparquet"
        )
    if args.history_source != "zzshare":
        reject_zzshare_only_history_options(args)


def reject_ignored_history_options(args: Any) -> None:
    ignored = []
    for name in [
        "history_source",
        "symbols",
        "symbols_file",
        "start_date",
        "end_date",
        "history_adjust",
        "history_output_format",
        *ZZSHARE_ONLY_HISTORY_OPTIONS,
    ]:
        if option_configured(getattr(args, name, None)):
            ignored.append("--" + name.replace("_", "-"))
    for name in [
        "derive_symbols_from_spot",
        "derive_all_spot_symbols",
        "allow_partial_history",
        "drop_invalid_history_rows",
        "history_resume_from_checkpoint",
    ]:
        if getattr(args, name):
            ignored.append("--" + name.replace("_", "-"))
    if ignored:
        raise ValueError(
            "--prices-input was provided; history fetch options would be ignored: "
            + ",".join(ignored)
        )


def reject_zzshare_only_history_options(args: Any) -> None:
    names = [
        name
        for name in ZZSHARE_ONLY_HISTORY_OPTIONS
        if not (
            name == "history_timeout_seconds"
            and args.history_source in {"pytdx", "yfinance"}
        )
    ]
    ignored = option_flags(args, names)
    if ignored:
        raise ValueError(
            "zzshare-specific history options require --history-source zzshare: "
            + ",".join(ignored)
        )


def reject_yfinance_unsupported_history_options(args: Any) -> None:
    ignored = option_flags(args, YFINANCE_UNSUPPORTED_HISTORY_OPTIONS)
    if ignored:
        raise ValueError(
            "unsupported yfinance history options would be ignored: "
            + ",".join(ignored)
        )


def reject_pytdx_unsupported_history_options(args: Any) -> None:
    ignored = option_flags(args, PYTDX_UNSUPPORTED_HISTORY_OPTIONS)
    if ignored:
        raise ValueError(
            "unsupported pytdx history options would be ignored: "
            + ",".join(ignored)
        )


def option_flags(args: Any, names: list[str]) -> list[str]:
    return [
        "--" + name.replace("_", "-")
        for name in names
        if option_configured(getattr(args, name, None))
    ]


def parquet_engine_available() -> bool:
    return any(
        importlib.util.find_spec(module) is not None
        for module in ("pyarrow", "fastparquet")
    )


def history_symbols(
    args: Any,
    spot: Path | None,
    output: Path,
    config: Path,
) -> list[str]:
    if explicit_symbol_input_configured(args):
        symbols = unique_symbols(parse_history_symbols(args))
        write_json(
            explicit_symbol_metadata(args, symbols), output / "selected_symbols.json"
        )
        return symbols
    if spot is None:
        raise ValueError("--derive-symbols-from-spot requires a spot snapshot")
    return derive_symbols_from_spot(args, spot, output, config)


def parse_history_symbols(args: Any) -> list[str]:
    text = explicit_symbols_text(args)
    if args.history_source == "zzshare":
        return parse_a_share_symbols(text)
    if args.history_source == "pytdx":
        return parse_six_digit_symbols(text)
    if args.history_source == AKSHARE_HK_DAILY_SOURCE:
        return parse_akshare_hk_symbols(text)
    if args.history_source == "yfinance":
        return parse_yfinance_symbols(text, getattr(args, "history_market", ""))
    return parse_six_digit_symbols(text)


def explicit_symbol_input_configured(args: Any) -> bool:
    return option_configured(getattr(args, "symbols", None)) or option_configured(
        getattr(args, "symbols_file", None)
    )


def explicit_symbols_text(args: Any) -> str:
    symbols_file = getattr(args, "symbols_file", None)
    if option_configured(symbols_file):
        return read_symbols_file(Path(symbols_file))
    return str(getattr(args, "symbols", "") or "")


def read_symbols_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"symbols file not found: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"symbols file is a directory: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"symbols file is not valid UTF-8 or UTF-8-BOM: {path}"
        ) from exc
    text = re.sub(r"[\r\n]+", ",", raw_text).rstrip(",")
    if not any(value.strip() for value in text.split(",")):
        raise ValueError(f"symbols file is empty or contains no symbols: {path}")
    return text


def explicit_symbol_metadata(args: Any, symbols: list[str]) -> dict[str, Any]:
    source = explicit_symbol_metadata_source(args)
    metadata = {
        "source": source,
        "symbols": symbols,
        "selected_symbol_count": len(symbols),
        "history_symbol_limit_source": "explicit_symbols_no_spot_limit",
    }
    if getattr(args, "symbols_file", None):
        metadata["symbols_file"] = str(Path(args.symbols_file))
    if getattr(args, "resume_from", None):
        metadata["resume_from"] = str(Path(args.resume_from))
        metadata["resume_symbol_source"] = getattr(args, "resume_symbol_source", "")
    return metadata


def explicit_symbol_metadata_source(args: Any) -> str:
    if getattr(args, "resume_from", None):
        return "resume_retry_symbols"
    if getattr(args, "symbols_file", None):
        return "explicit_symbols_file"
    return "explicit_symbols"


def parse_akshare_hk_symbols(text: str) -> list[str]:
    raw_symbols = [item.strip() for item in text.split(",") if item.strip()]
    if not raw_symbols:
        raise ValueError("symbols must not be empty")
    result = []
    for symbol in raw_symbols:
        normalized = normalize_hk_symbol(symbol)
        if not valid_hk_symbol_text(normalized):
            raise ValueError(
                f"HK symbols must be 1 to 5 digits or HK-prefixed/suffixed: {symbol}"
            )
        result.append(normalized.zfill(5))
    return result


def parse_yfinance_symbols(text: str, market: str = "") -> list[str]:
    raw_symbols = [item.strip() for item in text.split(",") if item.strip()]
    if not raw_symbols:
        raise ValueError("symbols must not be empty")
    if not is_hk_market(market):
        return [symbol.upper() for symbol in raw_symbols]
    return [normalize_yfinance_hk_symbol(symbol) for symbol in raw_symbols]


def normalize_yfinance_hk_symbol(symbol: str) -> str:
    text = symbol.strip()
    if text.lower().endswith(".hk"):
        normalized = normalize_hk_symbol(text)
    elif text.lower().startswith("hk."):
        normalized = normalize_hk_symbol(text)
    elif text.isdigit() and 1 <= len(text) <= 5:
        normalized = text
    else:
        return text.upper()
    if not valid_hk_symbol_text(normalized):
        raise ValueError(
            f"HK yfinance symbols must be 1 to 5 digits or HK-prefixed/suffixed: {symbol}"
        )
    return f"{int(normalized):04d}.HK"


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
    derive_all = bool(getattr(args, "derive_all_spot_symbols", False))
    filtered = filter_spot_universe(
        frame,
        config,
        history_source=args.history_source,
        apply_thresholds=not derive_all,
    )
    limit = int(args.max_history_symbols)
    max_history_symbols_is_default = not bool(
        getattr(args, "max_history_symbols_supplied", False)
    )
    ranked = rank_spot_candidates(filtered, symbol_only=derive_all).head(limit)
    symbols = ranked["symbol"].astype(str).tolist()
    if not symbols:
        write_json(
            spot_symbol_metadata(
                frame,
                filtered,
                ranked,
                config,
                limit,
                max_history_symbols_is_default=max_history_symbols_is_default,
                derive_all_spot_symbols=derive_all,
                failed=True,
            ),
            output / "selected_symbols.json",
        )
        raise ValueError(
            "spot snapshot produced zero history symbols after configured filters; "
            "preflight_stage=derive_symbols filtered_spot_rows="
            f"{int(len(filtered))} raw_spot_rows={int(len(frame))} "
            f"selected_symbols_count={int(len(ranked))} max_history_symbols={int(limit)} "
            "next_action=expand_spot_universe_or_relax_filters"
        )
    write_json(
        spot_symbol_metadata(
            frame,
            filtered,
            ranked,
            config,
            limit,
            max_history_symbols_is_default=max_history_symbols_is_default,
            derive_all_spot_symbols=derive_all,
        ),
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


def filter_spot_universe(
    frame,
    config: dict[str, Any],
    history_source: str = "",
    *,
    apply_thresholds: bool = True,
):
    result = (
        normalize_spot_filter_frame(frame, history_source)
        if apply_thresholds
        else normalize_spot_symbol_frame(frame, history_source)
    )
    thresholds = config.get("thresholds", {})
    if history_source == AKSHARE_HK_DAILY_SOURCE:
        result = result[result["symbol"].map(valid_hk_symbol_text)]
    else:
        result = result[result["symbol"].str.fullmatch(r"\d{6}", na=False)]
    result = apply_symbol_universe(result, config.get("universe", {}))
    if not apply_thresholds:
        return result.copy()
    if "min_close" in thresholds:
        result = result[result["spot_price"] >= float(thresholds["min_close"])]
    if "max_close" in thresholds:
        result = result[result["spot_price"] <= float(thresholds["max_close"])]
    if "min_amount" in thresholds:
        result = result[result["spot_amount"] >= float(thresholds["min_amount"])]
    if thresholds.get("exclude_st") and "name" in result:
        result = result[
            ~result["name"]
            .astype(str)
            .str.upper()
            .str.match(r"^(?:\*?ST|SST)", na=False)
        ]
    return result.copy()


def normalize_spot_symbol_frame(frame, history_source: str = ""):
    result = frame.copy()
    result["symbol"] = normalize_history_spot_symbols(
        first_existing_required(result, SYMBOL_COLUMN_ALIASES, "symbol"),
        history_source,
    )
    if "name" not in result:
        result["name"] = ""
    return result


def normalize_spot_filter_frame(frame, history_source: str = ""):
    import pandas as pd

    result = frame.copy()
    result["symbol"] = normalize_history_spot_symbols(
        first_existing_required(result, SYMBOL_COLUMN_ALIASES, "symbol"),
        history_source,
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


def normalize_history_spot_symbols(values: Any, history_source: str) -> list[str]:
    if history_source == AKSHARE_HK_DAILY_SOURCE:
        return [normalize_akshare_hk_spot_symbol(value) for value in values]
    return normalize_symbol_values(
        values,
        allowed_exchanges=history_symbol_exchanges(history_source),
    )


def normalize_akshare_hk_spot_symbol(value: Any) -> str:
    normalized = normalize_hk_symbol(value)
    if valid_hk_symbol_text(normalized):
        return normalized.zfill(5)
    return normalized


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
    raise ValueError(
        f"spot input requires {label} column; accepted aliases: {','.join(columns)}"
    )


def apply_symbol_universe(frame, universe: dict[str, Any]):
    result = frame
    allow = universe.get("symbol_prefix_allow_regex")
    if allow:
        result = result[result["symbol"].str.match(str(allow), na=False)]
    excluded = tuple(str(item) for item in universe.get("symbol_prefix_exclude", []))
    if excluded:
        result = result[~result["symbol"].str.startswith(excluded)]
    return result


def rank_spot_candidates(frame, *, symbol_only: bool = False):
    if symbol_only:
        return frame.sort_values(["symbol"], ascending=[True])
    return frame.sort_values(["spot_amount", "spot_pct_chg"], ascending=[False, False])


def spot_symbol_metadata(
    frame,
    filtered,
    ranked,
    config: dict[str, Any],
    limit: int,
    *,
    max_history_symbols_is_default: bool,
    derive_all_spot_symbols: bool,
    failed: bool = False,
) -> dict[str, Any]:
    thresholds = config.get("thresholds", {})
    metadata = {
        "source": "spot_snapshot",
        "filter_profile": config.get("profile_name", ""),
        "preflight_stage": "derive_symbols",
        "spot_symbol_filter_mode": (
            "all_valid_spot_symbols"
            if derive_all_spot_symbols
            else "configured_spot_thresholds"
        ),
        "spot_thresholds_applied": not derive_all_spot_symbols,
        "raw_spot_rows": int(len(frame)),
        "filtered_spot_rows": int(len(filtered)),
        "selected_symbols": ranked["symbol"].astype(str).tolist(),
        "selected_symbol_count": int(len(ranked)),
        "max_history_symbols": int(limit),
        "history_symbol_limit_source": (
            "small_sample_default_cap"
            if max_history_symbols_is_default
            else "explicit_user_input"
        ),
        "filters": {
            "universe": config.get("universe", {}),
            "thresholds": {
                key: thresholds.get(key)
                for key in ["min_close", "max_close", "min_amount", "exclude_st"]
                if key in thresholds
            },
            "thresholds_applied": not derive_all_spot_symbols,
        },
    }
    if failed:
        metadata.update(
            {
                "selection_failed": True,
                "selection_failed_reason": "spot_snapshot_filtered_to_zero_history_symbols",
                "selection_failed_next_action": "expand_spot_universe_or_relax_filters",
                "next_action": "expand_spot_universe_or_relax_filters",
            }
        )
    return metadata


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
