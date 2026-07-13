"""Verified incremental history merge helpers."""

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


from datetime import datetime, timezone
import time
from typing import Any

from lib.gates.clean_history_pool import clean_symbol_summaries, metadata_symbol_map


INCREMENTAL_MERGE_BOUNDARY = (
    "incremental_history_merge_from_verified_artifacts_not_full_market_proof"
)
FETCH_FAILURE_LISTS = (
    "failed_symbols",
    "empty_symbols",
    "possibly_truncated_symbols",
    "unprocessed_symbols",
)


def merge_incremental_history(
    base: Any,
    base_metadata: dict[str, Any],
    plan: dict[str, Any],
    incremental: Any,
    incremental_metadata: dict[str, Any],
    *,
    compute_symbol_summaries: bool = True,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    target = plan_target_date(plan)
    planned = unique_symbols(plan.get("fetch_symbols", []))
    if not planned:
        raise ValueError("incremental plan has no fetch_symbols")
    validate_incremental_metadata(incremental_metadata, planned)
    validate_provider_merge_contract(incremental_metadata)
    base_normalized = normalize_history_frame(base, "base prices")
    delta_normalized = normalize_history_frame(incremental, "incremental prices")
    validate_matching_columns(base_normalized, delta_normalized)
    delta_symbols = unique_symbols(delta_normalized["symbol"].tolist())
    validate_planned_symbol_coverage(planned, delta_symbols)
    validate_incremental_dates(delta_normalized, planned, target)
    merged, overlap_rows = merge_frames(base_normalized, delta_normalized)
    duration = round(max(time.monotonic() - started, 0.0), 6)
    report = incremental_merge_report(
        base_normalized,
        delta_normalized,
        merged,
        planned,
        target,
        overlap_rows,
        duration,
    )
    metadata = merged_history_metadata(
        base_metadata,
        incremental_metadata,
        merged,
        planned,
        report,
        compute_symbol_summaries=compute_symbol_summaries,
    )
    report["symbol_summaries_deferred"] = not compute_symbol_summaries
    return merged, metadata, report


def normalize_history_frame(frame: Any, label: str) -> Any:
    missing = sorted({"symbol", "date"} - set(frame.columns))
    if missing:
        raise ValueError(f"{label} missing columns: {','.join(missing)}")
    raw_symbols = frame["symbol"]
    if raw_symbols.isna().any():
        raise ValueError(f"{label} has missing symbol values")
    if not raw_symbols.map(lambda value: isinstance(value, str)).all():
        raise ValueError(f"{label} symbol values must be text")
    symbols = raw_symbols.astype(str).str.strip()
    invalid_symbols = ~symbols.str.fullmatch(r"\d{6}")
    if invalid_symbols.any():
        examples = symbols.loc[invalid_symbols].drop_duplicates().head(20).tolist()
        raise ValueError(f"{label} has invalid symbol values: {examples}")
    dates = normalize_date_series(frame["date"], label)
    symbol_unchanged = frame["symbol"].equals(symbols)
    date_unchanged = frame["date"].equals(dates)
    normalized = frame if symbol_unchanged and date_unchanged else frame.copy()
    if not symbol_unchanged:
        normalized["symbol"] = symbols
    if not date_unchanged:
        normalized["date"] = dates
    duplicates = normalized.duplicated(["symbol", "date"], keep=False)
    if duplicates.any():
        examples = (
            normalized.loc[duplicates, ["symbol", "date"]]
            .drop_duplicates()
            .head(20)
            .to_dict("records")
        )
        raise ValueError(f"{label} has duplicate symbol/date rows: {examples}")
    return normalized


def normalize_date_series(series: Any, label: str) -> Any:
    pd = pandas_module()
    text = series.astype(str).str.strip()
    compact = text.str.fullmatch(r"\d{8}")
    iso = text.str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    if iso.all():
        parsed_iso = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
        if parsed_iso.notna().all():
            return text
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    parsed.loc[compact] = pd.to_datetime(text.loc[compact], format="%Y%m%d")
    parsed.loc[iso] = pd.to_datetime(text.loc[iso], format="%Y-%m-%d")
    if parsed.isna().any():
        examples = text.loc[parsed.isna()].drop_duplicates().head(20).tolist()
        raise ValueError(f"{label} has invalid date values: {examples}")
    return parsed.dt.strftime("%Y-%m-%d")


def validate_incremental_metadata(metadata: dict[str, Any], planned: list[str]) -> None:
    for key in ("output_written", "metadata_output_written"):
        if metadata.get(key) is not True:
            raise ValueError(f"incremental history metadata requires {key}=true")
    for key in FETCH_FAILURE_LISTS:
        values = metadata_symbols(metadata.get(key, []))
        if values:
            raise ValueError(f"incremental history metadata has {key}: {values[:20]}")
    if metadata.get("rate_limit_budget_exhausted") is True:
        raise ValueError("incremental history metadata exhausted its rate-limit budget")
    if int(metadata.get("invalid_rows", 0) or 0) != 0:
        raise ValueError("incremental history metadata has invalid_rows")
    requested = unique_symbols(metadata.get("requested_symbols", []))
    if requested and requested != planned:
        raise ValueError("incremental metadata requested_symbols do not match plan")


def validate_provider_merge_contract(metadata: dict[str, Any]) -> None:
    provider = str(metadata.get("provider") or metadata.get("source") or "").lower()
    if "pytdx" not in provider:
        return
    raise ValueError(
        "pytdx incremental history is supplemental only; exact symbol/date strict "
        "companion fields are required before verified selection merge"
    )


def validate_planned_symbol_coverage(planned: list[str], delta_symbols: list[str]) -> None:
    planned_set = set(planned)
    delta_set = set(delta_symbols)
    missing = sorted(planned_set - delta_set)
    unexpected = sorted(delta_set - planned_set)
    if missing:
        raise ValueError(f"incremental prices missing planned symbols: {missing[:20]}")
    if unexpected:
        raise ValueError(f"incremental prices has unplanned symbols: {unexpected[:20]}")


def validate_incremental_dates(frame: Any, planned: list[str], target: str) -> None:
    date_max = frame.groupby("symbol")["date"].max()
    stale = [symbol for symbol in planned if str(date_max.get(symbol, "")) < target]
    if stale:
        raise ValueError(
            f"incremental prices do not reach target_end_date for symbols: {stale[:20]}"
        )
    future = sorted(frame.loc[frame["date"] > target, "symbol"].unique().tolist())
    if future:
        raise ValueError(
            f"incremental prices exceed target_end_date for symbols: {future[:20]}"
        )


def validate_matching_columns(base: Any, incremental: Any) -> None:
    if set(base.columns) == set(incremental.columns):
        return
    missing = sorted(set(base.columns) - set(incremental.columns))
    extra = sorted(set(incremental.columns) - set(base.columns))
    raise ValueError(f"incremental prices columns differ; missing={missing} extra={extra}")


def merge_frames(base: Any, incremental: Any) -> tuple[Any, int]:
    pd = pandas_module()
    delta = incremental.loc[:, list(base.columns)]
    overlap_rows = int(
        delta[["symbol", "date"]]
        .merge(base[["symbol", "date"]], on=["symbol", "date"], how="inner")
        .shape[0]
    )
    merged = pd.concat([base, delta], ignore_index=True)
    if overlap_rows:
        merged = merged.drop_duplicates(["symbol", "date"], keep="last")
    merged = merged.sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    return merged, overlap_rows


def incremental_merge_report(
    base: Any,
    incremental: Any,
    merged: Any,
    planned: list[str],
    target: str,
    overlap_rows: int,
    duration: float,
) -> dict[str, Any]:
    input_rows = int(len(base) + len(incremental))
    return {
        "source": "incremental_history_merge",
        "claim_boundary": INCREMENTAL_MERGE_BOUNDARY,
        "target_end_date": target,
        "planned_symbol_count": len(planned),
        "planned_symbols": planned,
        "base_rows": int(len(base)),
        "incremental_rows": int(len(incremental)),
        "merged_rows": int(len(merged)),
        "overlap_rows_replaced": int(overlap_rows),
        "merged_symbol_count": int(merged["symbol"].nunique()),
        "merge_duration_seconds": duration,
        "merge_input_rows": input_rows,
        "merge_input_rows_per_second": (
            round(input_rows / duration, 6) if duration else None
        ),
    }


def merged_history_metadata(
    base: dict[str, Any],
    incremental: dict[str, Any],
    merged: Any,
    planned: list[str],
    report: dict[str, Any],
    *,
    compute_symbol_summaries: bool,
) -> dict[str, Any]:
    combined = dict(base)
    prior_symbols = metadata_symbol_map(base)
    prior_symbols.update(metadata_symbol_map(incremental))
    symbol_metadata = {"symbols": list(prior_symbols.values())}
    combined.update(metadata_fields(merged, planned, report))
    combined["symbols"] = (
        clean_symbol_summaries(merged, symbol_metadata)
        if compute_symbol_summaries
        else sorted(
            prior_symbols.values(),
            key=lambda item: str(item.get("symbol", "")),
        )
    )
    combined["requested_symbols"] = [
        item["symbol"] for item in combined["symbols"] if item.get("symbol")
    ]
    for key in FETCH_FAILURE_LISTS:
        combined[key] = remove_symbols(combined.get(key, []), set(planned))
    return combined


def metadata_fields(merged: Any, planned: list[str], report: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_scope": "incremental_history_merged_pool",
        "source_claim_boundary": INCREMENTAL_MERGE_BOUNDARY,
        "incremental_merge_generated_at": now_iso(),
        "incremental_merge_target_end_date": report["target_end_date"],
        "incremental_merge_planned_symbols": planned,
        "incremental_merge_planned_symbol_count": len(planned),
        "incremental_merge_rows": report["incremental_rows"],
        "incremental_merge_overlap_rows_replaced": report["overlap_rows_replaced"],
        "incremental_merge_duration_seconds": report["merge_duration_seconds"],
        "incremental_merge_input_rows_per_second": report[
            "merge_input_rows_per_second"
        ],
        "incremental_merge_claim_boundary": INCREMENTAL_MERGE_BOUNDARY,
        "rows": int(len(merged)),
        "symbol_count": int(merged["symbol"].nunique()),
        "output_written": True,
        "metadata_output_written": True,
    }


def plan_target_date(plan: dict[str, Any]) -> str:
    if str(plan.get("source", "")) != "incremental_history_plan":
        raise ValueError("incremental plan source is invalid")
    boundary = str(plan.get("claim_boundary", ""))
    if boundary != "incremental_history_plan_only_not_history_fetch_success":
        raise ValueError("incremental plan claim_boundary is invalid")
    return normalize_date(plan.get("target_end_date", ""))


def normalize_date(value: Any) -> str:
    text = str(value or "").strip().replace("-", "")
    if not text.isdigit() or len(text) != 8:
        raise ValueError(f"invalid target_end_date: {value}")
    try:
        return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"invalid target_end_date: {value}") from exc


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


def remove_symbols(value: Any, removed: set[str]) -> list[str]:
    return [symbol for symbol in metadata_symbols(value) if symbol not in removed]


def unique_symbols(values: Any) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def pandas_module() -> Any:
    import pandas as pandas  # noqa: PLC0415

    return pandas
