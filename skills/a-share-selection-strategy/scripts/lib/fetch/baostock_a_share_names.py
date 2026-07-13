"""Name lookup policies for baostock A-share history fetches."""

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

from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_symbols import baostock_code


MISSING_NAME_POLICIES = ("query", "fail", "blank")


def resolve_symbol_names(
    bs: Any,
    symbols: list[str],
    names_input: str = "",
    missing_name_policy: str = "query",
) -> dict[str, Any]:
    if missing_name_policy not in MISSING_NAME_POLICIES:
        raise ValueError(f"unsupported missing-name-policy: {missing_name_policy}")
    loaded = load_names_input(names_input, symbols)
    missing = [symbol for symbol in symbols if symbol not in loaded["names"]]
    queried = empty_query_result()
    if missing and missing_name_policy == "query":
        queried = fetch_symbol_names(bs, missing)
    names = {**loaded["names"], **queried["names"]}
    unresolved = [symbol for symbol in symbols if symbol not in names]
    sources = [source for source in [loaded["source"], queried["source"]] if source]
    return {
        "source": "+".join(sources),
        "names": names,
        "failed_symbols": queried["failed_symbols"],
        "missing_symbols": unresolved,
        "input_path": loaded["input_path"],
        "input_name_count": len(loaded["names"]),
        "query_count": len(missing) if missing_name_policy == "query" else 0,
        "policy": missing_name_policy,
    }


def load_names_input(path_text: str, symbols: list[str]) -> dict[str, Any]:
    if not str(path_text or "").strip():
        return {"source": "", "names": {}, "input_path": ""}
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"names input does not exist: {path}")
    frame = read_names_frame(path)
    missing_columns = sorted({"symbol", "name"} - set(frame.columns))
    if missing_columns:
        raise ValueError(f"names input missing columns: {', '.join(missing_columns)}")
    requested = set(symbols)
    names: dict[str, str] = {}
    for raw_symbol, raw_name in frame[["symbol", "name"]].itertuples(index=False):
        symbol = str(raw_symbol).strip()
        name = str(raw_name).strip()
        if symbol not in requested or name.lower() in {"", "nan", "<na>", "none"}:
            continue
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"names input symbol must be six digits: {symbol}")
        if symbol in names and names[symbol] != name:
            raise ValueError(f"names input has conflicting names for symbol {symbol}")
        names[symbol] = name
    return {
        "source": "names_input",
        "names": names,
        "input_path": str(path),
    }


def read_names_frame(path: Path) -> Any:
    import pandas as pd

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype={"symbol": "string", "name": "string"})
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("names input must be CSV or Parquet")


def fetch_symbol_names(bs: Any, symbols: list[str]) -> dict[str, Any]:
    names = {}
    failed = []
    missing = []
    for symbol in symbols:
        result = bs.query_stock_basic(code=baostock_code(symbol))
        if result.error_code != "0":
            failed.append({"symbol": symbol, "error": result.error_msg})
            continue
        name = collect_stock_basic_name(result)
        if name:
            names[symbol] = name
        else:
            missing.append(symbol)
    return {
        "source": "baostock_query_stock_basic",
        "names": names,
        "failed_symbols": failed,
        "missing_symbols": missing,
    }


def collect_stock_basic_name(result: Any) -> str:
    while result.next():
        raw = dict(zip(result.fields, result.get_row_data()))
        return str(raw.get("code_name", "")).strip()
    return ""


def empty_query_result() -> dict[str, Any]:
    return {
        "source": "",
        "names": {},
        "failed_symbols": [],
        "missing_symbols": [],
    }
