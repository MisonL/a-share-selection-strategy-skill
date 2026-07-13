"""Clean history pool helpers."""

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


import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLAIM_BOUNDARY = "clean_history_pool_from_existing_artifacts_not_full_market_proof"


def build_clean_plan(
    metadata: dict[str, Any],
    short_data: dict[str, Any],
    ttl_days: int,
) -> dict[str, Any]:
    reasons = {
        "empty_history": sorted(metadata_symbols(metadata.get("empty_symbols", []))),
        "short_history": sorted(metadata_symbols(short_data.get("symbols", []))),
        "failed_fetch": sorted(metadata_symbols(metadata.get("failed_symbols", []))),
        "possibly_truncated": sorted(
            metadata_symbols(metadata.get("possibly_truncated_symbols", []))
        ),
        "unprocessed_fetch": sorted(
            metadata_symbols(metadata.get("unprocessed_symbols", []))
        ),
    }
    remove = unique_symbols(symbol for symbols in reasons.values() for symbol in symbols)
    return {
        "remove_symbols": remove,
        "reason_symbols": reasons,
        "reason_counts": {reason: len(symbols) for reason, symbols in reasons.items()},
        "skip_records": skip_records(reasons, ttl_days, metadata),
        "ttl_days": ttl_days,
    }


def apply_clean_plan(frame: Any, plan: dict[str, Any]) -> Any:
    if "symbol" not in frame:
        raise ValueError("prices input missing symbol column")
    if frame.empty:
        return frame.copy()
    remove = set(plan["remove_symbols"])
    if not remove:
        return frame
    return frame.loc[~frame["symbol"].astype(str).isin(remove)].reset_index(drop=True)


def build_clean_metadata(
    metadata: dict[str, Any],
    plan: dict[str, Any],
    clean: Any,
    prices_input: Path,
) -> dict[str, Any]:
    updated = dict(metadata)
    updated.update(clean_metadata_fields(metadata, plan, clean, prices_input))
    updated["empty_symbols"] = []
    updated["failed_symbols"] = []
    updated["possibly_truncated_symbols"] = []
    updated["unprocessed_symbols"] = []
    updated["symbols"] = clean_symbol_summaries(clean, metadata)
    updated["requested_symbols"] = [
        item["symbol"] for item in updated["symbols"] if item.get("symbol")
    ]
    return updated


def clean_metadata_fields(
    metadata: dict[str, Any],
    plan: dict[str, Any],
    clean: Any,
    prices_input: Path,
) -> dict[str, Any]:
    return {
        "source": str(metadata.get("source", "history_clean_pool")),
        "source_type": str(metadata.get("source_type", "external_fetch")),
        "source_scope": "clean_history_pool",
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": (
            "Cleaned from existing history artifacts; removed empty, failed, "
            "truncated, unprocessed, or short-history symbols without refetching."
        ),
        "clean_pool_generated_at": now_iso(),
        "clean_pool_source_prices": str(prices_input),
        "clean_pool_removed_symbols": plan["remove_symbols"],
        "clean_pool_removed_symbol_count": len(plan["remove_symbols"]),
        "clean_pool_reason_counts": plan["reason_counts"],
        "clean_pool_skip_records": plan["skip_records"],
        "rows": int(len(clean)),
        "symbol_count": int(clean["symbol"].nunique()) if not clean.empty else 0,
        "partial_result": bool(plan["remove_symbols"]),
        "output_written": True,
        "metadata_output_written": True,
    }


def clean_symbol_summaries(
    clean: Any, metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    by_symbol = metadata_symbol_map(metadata)
    if clean.empty or "symbol" not in clean:
        return []
    grouped = clean.assign(_symbol=clean["symbol"].astype(str)).groupby("_symbol")["date"]
    result = []
    for symbol, series in grouped:
        prior = dict(by_symbol.get(str(symbol), {}))
        prior.update(
            {
                "symbol": str(symbol),
                "rows": int(series.size),
                "date_min": str(series.min()),
                "date_max": str(series.max()),
            }
        )
        result.append(prior)
    return sorted(result, key=lambda item: str(item.get("symbol", "")))


def metadata_symbol_map(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for item in metadata.get("symbols", []):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol", "")).strip()
        if symbol:
            result[symbol] = item
    return result


def build_report(
    plan: dict[str, Any],
    raw: Any,
    clean: Any,
    metadata_input: Path,
    short_input: Path | None,
    incremental_merge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": "clean_history_pool_report",
        "claim_boundary": CLAIM_BOUNDARY,
        "history_metadata": str(metadata_input),
        "short_history": str(short_input) if short_input else "",
        "raw_rows": int(len(raw)),
        "raw_symbol_count": int(raw["symbol"].nunique()) if not raw.empty else 0,
        "clean_rows": int(len(clean)),
        "clean_symbol_count": int(clean["symbol"].nunique()) if not clean.empty else 0,
        "removed_symbols": plan["remove_symbols"],
        "removed_symbol_count": len(plan["remove_symbols"]),
        "reason_symbols": plan["reason_symbols"],
        "reason_counts": plan["reason_counts"],
        "skip_records": plan["skip_records"],
        "incremental_merge": incremental_merge or {},
    }


def skip_records(
    reasons: dict[str, list[str]],
    ttl_days: int,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    generated_at = now_iso()
    source = str(metadata.get("source", "unknown") or "unknown")
    return sorted(
        [
            {
                "symbol": symbol,
                "source": source,
                "reason": reason,
                "observed_at": generated_at,
                "ttl_days": ttl_days,
            }
            for reason, symbols in reasons.items()
            for symbol in symbols
        ],
        key=lambda item: (item["symbol"], item["reason"]),
    )


def metadata_symbols(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        raw = item.get("symbol", "") if isinstance(item, dict) else item
        text = str(raw).strip()
        if text:
            result.append(text)
    return sorted(set(result))


def unique_symbols(values: Any) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def read_frame(path: Path) -> Any:
    pd = pandas_module()
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype={"symbol": str, "name": str})
    if suffix in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
        if "symbol" in frame:
            frame["symbol"] = frame["symbol"].astype(str)
        return frame
    raise ValueError("unsupported prices format; use .csv, .parquet, or .pq")


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def validate_paths(*, inputs: list[Path | None], outputs: list[Path]) -> None:
    input_paths = {resolved_path(path) for path in inputs if path is not None}
    seen_outputs = set()
    for output in outputs:
        output_path = resolved_path(output)
        if output_path in input_paths:
            raise ValueError(f"output path must not overwrite input: {output}")
        if output_path in seen_outputs:
            raise ValueError(f"duplicate output path: {output}")
        seen_outputs.add(output_path)


def resolved_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def pandas_module() -> Any:
    import pandas as pandas  # noqa: PLC0415

    return pandas
