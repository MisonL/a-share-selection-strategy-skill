"""Validate and fingerprint a full-A universe to clean-history artifact chain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.gates.clean_history_pool import metadata_symbols, read_frame, read_json
from lib.gates.full_a_clean_pool_artifacts import (
    artifact_fingerprint,
    artifact_fingerprints,
    artifact_identity_matches,
    artifact_path_from,
    same_content_identity,
)
from lib.gates.full_a_clean_pool_lineage import (
    symbols_before_as_of_date,
    validate_clean_history_lineage,
)
from lib.selection_core.a_share_selection_symbols import symbol_set_sha256


SCHEMA_VERSION = 2
SOURCE = "full_a_clean_pool_provenance"
VALIDATION_STATUS = "valid"
CLAIM_BOUNDARY = "artifact_chain_validation_not_realtime_prediction_broker_or_return_proof"
ELIGIBLE_BOUNDARY = "clean_pool_matches_full_a_universe_history_no_exclusions"
EXCLUSION_BOUNDARY = "clean_pool_removed_symbols_not_full_market"
UNIVERSE_BREADTH_BOUNDARY = "universe_breadth_below_full_a_minimum"
HISTORY_FRESHNESS_BOUNDARY = "history_symbols_before_as_of_date_not_full_market"
MIN_FULL_A_UNIVERSE_SYMBOLS = 4_000
QUALITY_COUNTER_SEMANTICS = "raw_dimension_counts_not_additive"
FAILURE_LIST_KEYS = (
    "failed_symbols",
    "empty_symbols",
    "possibly_truncated_symbols",
    "unprocessed_symbols",
)
A_SHARE_PREFIXES = (
    "000",
    "001",
    "002",
    "003",
    "300",
    "301",
    "600",
    "601",
    "603",
    "605",
    "688",
    "689",
)


@dataclass(frozen=True)
class ValidatedProvenanceInputs:
    universe: Any
    history: Any
    clean: Any
    universe_meta: dict[str, Any]
    history_meta: dict[str, Any]
    clean_meta: dict[str, Any]
    universe_symbols: set[str]
    history_symbols: set[str]
    clean_symbols: set[str]
    universe_breadth_eligible: bool
    history_date_min: str
    history_as_of_date: str
    history_stale_symbols: list[str]
    removed_symbols: list[str]


def build_clean_pool_provenance(
    *,
    universe_input: Path,
    universe_metadata: Path,
    history_prices: Path,
    history_metadata: Path,
    clean_prices: Path,
    clean_metadata: Path,
    clean_metadata_alias: Path | None = None,
    clean_report: Path,
    short_history: Path | None = None,
    display_paths: dict[str, Path] | None = None,
    history_frame: Any | None = None,
    clean_frame: Any | None = None,
) -> dict[str, Any]:
    """Build a proof for persisted artifacts without claiming a final selection run."""

    state = validate_provenance_inputs(
        universe_input,
        universe_metadata,
        history_prices=history_prices,
        history_metadata=history_metadata,
        clean_prices=clean_prices,
        clean_metadata=clean_metadata,
        clean_report=clean_report,
        short_history=short_history,
        history_frame=history_frame,
        clean_frame=clean_frame,
    )
    artifacts = build_artifact_bindings(
        universe_input=universe_input,
        universe_metadata=universe_metadata,
        history_prices=history_prices,
        history_metadata=history_metadata,
        clean_prices=clean_prices,
        clean_metadata=clean_metadata,
        clean_metadata_alias=clean_metadata_alias,
        clean_report=clean_report,
        short_history=short_history,
        display_paths=display_paths or {},
    )
    return provenance_document(
        universe_meta=state.universe_meta,
        universe_symbols=state.universe_symbols,
        universe_rows=len(state.universe),
        universe_breadth_eligible=state.universe_breadth_eligible,
        history_meta=state.history_meta,
        history_symbols=state.history_symbols,
        history_rows=len(state.history),
        history_date_min=state.history_date_min,
        history_as_of_date=state.history_as_of_date,
        history_stale_symbols=state.history_stale_symbols,
        clean_meta=state.clean_meta,
        clean_symbols=state.clean_symbols,
        clean_rows=len(state.clean),
        removed_symbols=state.removed_symbols,
        artifacts=artifacts,
    )


def validate_provenance_inputs(
    universe_input: Path,
    universe_metadata: Path,
    *,
    history_prices: Path,
    history_metadata: Path,
    clean_prices: Path,
    clean_metadata: Path,
    clean_report: Path,
    short_history: Path | None,
    history_frame: Any | None,
    clean_frame: Any | None,
) -> ValidatedProvenanceInputs:
    universe = read_frame(universe_input)
    history = read_frame(history_prices) if history_frame is None else history_frame
    clean = read_frame(clean_prices) if clean_frame is None else clean_frame
    universe_meta = read_json(universe_metadata)
    history_meta = read_json(history_metadata)
    clean_meta = read_json(clean_metadata)
    report = read_json(clean_report)
    short_data = read_json(short_history) if short_history is not None else {}
    universe_symbols = validated_symbol_set(universe, "universe input", require_a_share=True)
    history_symbols = validated_symbol_set(history, "history prices")
    clean_symbols = validated_symbol_set(clean, "clean prices")
    validate_price_keys(history, "history prices")
    validate_price_keys(clean, "clean prices")
    history_date_min, history_as_of_date = validated_date_range(history, "history prices")
    validated_date_range(clean, "clean prices")
    history_stale_symbols = symbols_before_as_of_date(history, history_as_of_date)
    breadth_eligible = validate_universe_metadata(
        universe_meta,
        universe_symbols,
        universe_input,
        universe_metadata,
        history_as_of_date,
    )
    validate_history_metadata(
        history_meta, history, universe_symbols, history_symbols, history_as_of_date
    )
    removed_symbols = validate_clean_pool(
        clean_meta=clean_meta,
        report=report,
        history_prices=history_prices,
        history_metadata=history_metadata,
        history_meta=history_meta,
        short_history=short_history,
        short_data=short_data,
        history_symbols=history_symbols,
        history=history,
        clean=clean,
        clean_symbols=clean_symbols,
    )
    return ValidatedProvenanceInputs(
        universe=universe,
        history=history,
        clean=clean,
        universe_meta=universe_meta,
        history_meta=history_meta,
        clean_meta=clean_meta,
        universe_symbols=universe_symbols,
        history_symbols=history_symbols,
        clean_symbols=clean_symbols,
        universe_breadth_eligible=breadth_eligible,
        history_date_min=history_date_min,
        history_as_of_date=history_as_of_date,
        history_stale_symbols=history_stale_symbols,
        removed_symbols=removed_symbols,
    )


def validate_clean_pool_provenance(path: Path) -> dict[str, Any]:
    """Verify a previously written proof still binds to the same on-disk files."""

    data = read_json(path)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("full-A provenance schema_version is invalid")
    if data.get("source") != SOURCE:
        raise ValueError("full-A provenance source is invalid")
    if data.get("validation_status") != VALIDATION_STATUS:
        raise ValueError("full-A provenance validation_status is invalid")
    if data.get("claim_boundary") != CLAIM_BOUNDARY:
        raise ValueError("full-A provenance claim_boundary is invalid")
    if not isinstance(data.get("full_market_closure_eligible"), bool):
        raise ValueError("full-A provenance eligibility must be boolean")
    clean_pool = data.get("clean_pool")
    if not isinstance(clean_pool, dict):
        raise ValueError("full-A provenance clean_pool is missing")
    removed_count = non_negative_count(clean_pool, "removed_symbol_count", "clean_pool")
    universe = data.get("universe")
    history = data.get("history")
    if not isinstance(universe, dict) or not isinstance(history, dict):
        raise ValueError("full-A provenance universe or history is missing")
    breadth_eligible = universe.get("full_a_breadth_eligible") is True
    stale_symbols = metadata_symbol_set(history.get("symbols_before_as_of_date", []))
    stale_count = non_negative_count(history, "symbols_before_as_of_date_count", "history")
    if stale_count != len(stale_symbols):
        raise ValueError("full-A provenance history stale symbol count is invalid")
    expected_boundary = ELIGIBLE_BOUNDARY
    if not data["full_market_closure_eligible"]:
        if removed_count:
            expected_boundary = EXCLUSION_BOUNDARY
        elif not breadth_eligible:
            expected_boundary = UNIVERSE_BREADTH_BOUNDARY
        else:
            expected_boundary = HISTORY_FRESHNESS_BOUNDARY
    if data.get("full_market_closure_boundary") != expected_boundary:
        raise ValueError("full-A provenance boundary does not match eligibility")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("full-A provenance artifacts are missing")
    required = {
        "universe_input",
        "universe_metadata",
        "history_prices",
        "history_metadata",
        "clean_prices",
        "clean_metadata",
        "clean_report",
    }
    if set(artifacts).intersection(required) != required:
        raise ValueError("full-A provenance required artifacts are missing")
    actual_artifacts = {}
    for name, expected in artifacts.items():
        if not isinstance(expected, dict):
            raise ValueError(f"full-A provenance artifact is invalid: {name}")
        artifact_path = Path(str(expected.get("path", "")))
        actual = artifact_fingerprint(artifact_path)
        if not artifact_identity_matches(expected, actual):
            raise ValueError(f"full-A provenance artifact fingerprint mismatch: {name}")
        actual_artifacts[name] = actual
    recomputed = recompute_provenance(artifacts, actual_artifacts)
    final_artifacts = {
        name: artifact_fingerprint(Path(str(expected["path"])))
        for name, expected in artifacts.items()
    }
    for name, actual in final_artifacts.items():
        if not artifact_identity_matches(actual_artifacts[name], actual):
            raise ValueError(f"full-A provenance artifact changed during validation: {name}")
    if comparable_provenance(data) != comparable_provenance(recomputed):
        raise ValueError("full-A provenance contents do not match artifacts")
    return data


def recompute_provenance(
    artifacts: dict[str, Any],
    actual_artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    universe_input = artifact_path_from(artifacts, "universe_input")
    universe_metadata = artifact_path_from(artifacts, "universe_metadata")
    history_prices = artifact_path_from(artifacts, "history_prices")
    history_metadata = artifact_path_from(artifacts, "history_metadata")
    clean_prices = artifact_path_from(artifacts, "clean_prices")
    clean_metadata = artifact_path_from(artifacts, "clean_metadata")
    clean_report = artifact_path_from(artifacts, "clean_report")
    short_history = (
        artifact_path_from(artifacts, "short_history")
        if "short_history" in artifacts
        else None
    )
    state = validate_provenance_inputs(
        universe_input,
        universe_metadata,
        history_prices=history_prices,
        history_metadata=history_metadata,
        clean_prices=clean_prices,
        clean_metadata=clean_metadata,
        clean_report=clean_report,
        short_history=short_history,
        history_frame=None,
        clean_frame=None,
    )
    if "clean_metadata_alias" in actual_artifacts and not same_content_identity(
        actual_artifacts["clean_metadata"],
        actual_artifacts["clean_metadata_alias"],
    ):
        raise ValueError("clean metadata alias does not match primary metadata")
    return provenance_document(
        universe_meta=state.universe_meta,
        universe_symbols=state.universe_symbols,
        universe_rows=len(state.universe),
        universe_breadth_eligible=state.universe_breadth_eligible,
        history_meta=state.history_meta,
        history_symbols=state.history_symbols,
        history_rows=len(state.history),
        history_date_min=state.history_date_min,
        history_as_of_date=state.history_as_of_date,
        history_stale_symbols=state.history_stale_symbols,
        clean_meta=state.clean_meta,
        clean_symbols=state.clean_symbols,
        clean_rows=len(state.clean),
        removed_symbols=state.removed_symbols,
        artifacts=actual_artifacts,
    )


def validate_universe_metadata(
    metadata: dict[str, Any],
    symbols: set[str],
    universe_input: Path,
    universe_metadata: Path,
    history_as_of_date: str,
) -> bool:
    validate_artifact_flags(metadata, "universe metadata")
    if metadata.get("source") != "baostock":
        raise ValueError("universe metadata source must be baostock")
    if metadata.get("source_type") != "external_fetch":
        raise ValueError("universe metadata source_type must be external_fetch")
    if metadata.get("source_scope") != "baostock_universe_snapshot":
        raise ValueError("universe metadata source_scope must be baostock_universe_snapshot")
    if metadata.get("real_market_data") is not True:
        raise ValueError("universe metadata requires real_market_data=true")
    require_count(metadata, "symbol_count", len(symbols), "universe metadata")
    require_count(metadata, "raw_items", len(symbols), "universe metadata")
    require_count(metadata, "filtered_items", len(symbols), "universe metadata")
    excluded_count = non_negative_count(metadata, "excluded_count", "universe metadata")
    require_count(
        metadata,
        "raw_row_count",
        len(symbols) + excluded_count,
        "universe metadata",
    )
    if metadata.get("error") not in ("", None):
        raise ValueError("universe metadata has fetch error")
    if metadata.get("fetch_errors") != []:
        raise ValueError("universe metadata fetch_errors must be empty")
    require_count(metadata, "fetch_error_count", 0, "universe metadata")
    if metadata.get("allowed_failure_actions") != []:
        raise ValueError("universe metadata allowed_failure_actions must be empty")
    if metadata.get("coverage_claim") != "symbol_universe_snapshot_not_realtime_spot_proof":
        raise ValueError("universe metadata coverage_claim is invalid")
    if metadata.get("source_claim_boundary") != (
        "baostock_universe_snapshot_not_realtime_spot_or_full_market_proof"
    ):
        raise ValueError("universe metadata source_claim_boundary is invalid")
    require_same_path(metadata.get("output"), universe_input, "universe metadata output")
    require_same_path(
        metadata.get("metadata_output"),
        universe_metadata,
        "universe metadata metadata_output",
    )
    validate_universe_attempt(
        metadata,
        len(symbols),
        len(symbols) + excluded_count,
        history_as_of_date,
    )
    return len(symbols) >= MIN_FULL_A_UNIVERSE_SYMBOLS


def validate_universe_attempt(
    metadata: dict[str, Any],
    symbol_count: int,
    raw_row_count: int,
    history_as_of_date: str,
) -> None:
    resolved_date = normalized_date(
        metadata.get("resolved_snapshot_date"),
        "universe metadata resolved_snapshot_date",
    )
    if resolved_date != history_as_of_date:
        raise ValueError("universe resolved_snapshot_date does not match history as_of_date")
    attempts = metadata.get("attempted_dates")
    if not resolved_date or not isinstance(attempts, list):
        raise ValueError("universe metadata date resolution is missing")
    matches = [
        item
        for item in attempts
        if isinstance(item, dict) and str(item.get("date", "")) == resolved_date
    ]
    if len(matches) != 1:
        raise ValueError("universe metadata resolved attempt is invalid")
    attempt = matches[0]
    if str(attempt.get("error", "")):
        raise ValueError("universe metadata resolved attempt has error")
    require_count(attempt, "symbol_count", symbol_count, "universe resolved attempt")
    require_count(attempt, "raw_rows", raw_row_count, "universe resolved attempt")


def validate_history_metadata(
    metadata: dict[str, Any],
    history: Any,
    universe_symbols: set[str],
    history_symbols: set[str],
    history_as_of_date: str,
) -> None:
    validate_artifact_flags(metadata, "history metadata")
    for key in FAILURE_LIST_KEYS:
        if metadata_symbols(metadata.get(key, [])):
            raise ValueError(f"history metadata has {key}")
    require_count(metadata, "symbol_count", len(history_symbols), "history metadata")
    require_count(metadata, "rows", len(history), "history metadata")
    if metadata_symbol_set(metadata.get("requested_symbols")) != universe_symbols:
        raise ValueError("history requested_symbols do not match universe")
    if metadata_symbol_record_set(metadata.get("symbols")) != history_symbols:
        raise ValueError("history metadata symbols do not match prices")
    if history_symbols != universe_symbols:
        raise ValueError("history prices symbols do not match universe")
    if normalized_date(metadata.get("end_date"), "history metadata end_date") != history_as_of_date:
        raise ValueError("history metadata end_date does not match history as_of_date")
    validate_history_quality_counts(metadata, len(history))


def validate_clean_pool(
    *,
    clean_meta: dict[str, Any],
    report: dict[str, Any],
    history_prices: Path,
    history_metadata: Path,
    history_meta: dict[str, Any],
    short_history: Path | None,
    short_data: dict[str, Any],
    history_symbols: set[str],
    history: Any,
    clean: Any,
    clean_symbols: set[str],
) -> list[str]:
    validate_artifact_flags(clean_meta, "clean metadata")
    if clean_meta.get("source_scope") != "clean_history_pool":
        raise ValueError("clean metadata source_scope must be clean_history_pool")
    require_count(clean_meta, "symbol_count", len(clean_symbols), "clean metadata")
    require_count(clean_meta, "rows", len(clean), "clean metadata")
    if metadata_symbol_record_set(clean_meta.get("symbols")) != clean_symbols:
        raise ValueError("clean metadata symbols do not match clean prices")
    if metadata_symbol_set(clean_meta.get("requested_symbols")) != clean_symbols:
        raise ValueError("clean requested_symbols do not match clean prices")
    require_same_path(clean_meta.get("clean_pool_source_prices"), history_prices, "clean metadata source prices")
    require_same_path(report.get("history_metadata"), history_metadata, "clean report history metadata")
    recorded_short_history = str(report.get("short_history", "") or "").strip()
    if short_history is not None:
        require_same_path(report.get("short_history"), short_history, "clean report short history")
    elif recorded_short_history:
        raise ValueError("clean report short history is not bound by provenance")
    removed = metadata_symbols(clean_meta.get("clean_pool_removed_symbols", []))
    report_removed = metadata_symbols(report.get("removed_symbols", []))
    if removed != report_removed:
        raise ValueError("clean metadata and report removed symbols do not match")
    if set(removed).difference(history_symbols):
        raise ValueError("clean pool removes symbols outside history prices")
    if clean_symbols != history_symbols.difference(removed):
        raise ValueError("clean prices symbols do not match history minus removals")
    validate_clean_history_lineage(history, clean, set(removed))
    require_count(clean_meta, "clean_pool_removed_symbol_count", len(removed), "clean metadata")
    require_count(report, "removed_symbol_count", len(removed), "clean report")
    if bool(clean_meta.get("partial_result")) != bool(removed):
        raise ValueError("clean metadata partial_result does not match removals")
    if report.get("reason_counts") != clean_meta.get("clean_pool_reason_counts"):
        raise ValueError("clean report reason_counts do not match clean metadata")
    validate_reason_breakdown(
        report,
        removed,
        expected_reason_symbols(history_meta, short_data, short_history),
    )
    return removed


def validate_artifact_flags(metadata: dict[str, Any], label: str) -> None:
    if metadata.get("output_written") is not True:
        raise ValueError(f"{label} requires output_written=true")
    if metadata.get("metadata_output_written") is not True:
        raise ValueError(f"{label} requires metadata_output_written=true")
    partial_result = metadata.get("partial_result")
    if not isinstance(partial_result, bool):
        raise ValueError(f"{label} partial_result must be boolean")
    if partial_result is not False and label != "clean metadata":
        raise ValueError(f"{label} requires partial_result=false")


def validate_history_quality_counts(metadata: dict[str, Any], output_rows: int) -> None:
    invalid_rows = non_negative_count(metadata, "invalid_rows", "history metadata")
    dropped_rows = non_negative_count(
        metadata, "dropped_invalid_rows", "history metadata"
    )
    raw_rows = non_negative_count(metadata, "raw_rows", "history metadata")
    dropped_non_trading = non_negative_count(
        metadata, "dropped_non_trading_rows", "history metadata"
    )
    if invalid_rows != dropped_rows:
        raise ValueError("history invalid_rows must equal dropped_invalid_rows")
    if raw_rows != output_rows + dropped_rows + dropped_non_trading:
        raise ValueError("history raw_rows do not reconcile with dropped rows and output")
    if metadata.get("raw_quality_counter_semantics") != QUALITY_COUNTER_SEMANTICS:
        raise ValueError("history raw quality counter semantics are invalid")
    non_trading = non_negative_count(
        metadata, "raw_non_trading_rows", "history metadata"
    )
    overlap = non_negative_count(
        metadata, "raw_invalid_non_trading_overlap_rows", "history metadata"
    )
    if overlap > min(invalid_rows, non_trading):
        raise ValueError("history raw invalid/non-trading overlap is invalid")
    if dropped_non_trading > non_trading - overlap:
        raise ValueError("history dropped non-trading rows are invalid")


def artifact_summary(metadata: dict[str, Any], symbols: set[str], rows: int) -> dict[str, Any]:
    return {
        "source": str(metadata.get("source", "")),
        "source_scope": str(metadata.get("source_scope", "")),
        "symbol_count": len(symbols),
        "row_count": int(rows),
        "symbol_set_sha256": symbol_set_sha256(symbols),
    }


def build_artifact_bindings(
    *,
    universe_input: Path,
    universe_metadata: Path,
    history_prices: Path,
    history_metadata: Path,
    clean_prices: Path,
    clean_metadata: Path,
    clean_metadata_alias: Path | None,
    clean_report: Path,
    short_history: Path | None,
    display_paths: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    paths = {
        "universe_input": universe_input,
        "universe_metadata": universe_metadata,
        "history_prices": history_prices,
        "history_metadata": history_metadata,
        "clean_prices": clean_prices,
        "clean_metadata": clean_metadata,
        **({"clean_metadata_alias": clean_metadata_alias} if clean_metadata_alias else {}),
        "clean_report": clean_report,
        **({"short_history": short_history} if short_history else {}),
    }
    artifacts = artifact_fingerprints(paths, display_paths)
    if clean_metadata_alias and not same_content_identity(
        artifacts["clean_metadata"], artifacts["clean_metadata_alias"]
    ):
        raise ValueError("clean metadata alias does not match primary metadata")
    return artifacts


def provenance_document(
    *,
    universe_meta: dict[str, Any],
    universe_symbols: set[str],
    universe_rows: int,
    universe_breadth_eligible: bool,
    history_meta: dict[str, Any],
    history_symbols: set[str],
    history_rows: int,
    history_date_min: str,
    history_as_of_date: str,
    history_stale_symbols: list[str],
    clean_meta: dict[str, Any],
    clean_symbols: set[str],
    clean_rows: int,
    removed_symbols: list[str],
    artifacts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    eligible = (
        universe_breadth_eligible
        and not removed_symbols
        and not history_stale_symbols
    )
    boundary = (
        EXCLUSION_BOUNDARY
        if removed_symbols
        else UNIVERSE_BREADTH_BOUNDARY
        if not universe_breadth_eligible
        else HISTORY_FRESHNESS_BOUNDARY
        if history_stale_symbols
        else ELIGIBLE_BOUNDARY
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "validation_status": VALIDATION_STATUS,
        "claim_boundary": CLAIM_BOUNDARY,
        "full_market_closure_eligible": eligible,
        "full_market_closure_boundary": boundary,
        "generated_at": now_iso(),
        "universe": {
            **artifact_summary(universe_meta, universe_symbols, universe_rows),
            "minimum_full_a_symbol_count": MIN_FULL_A_UNIVERSE_SYMBOLS,
            "full_a_breadth_eligible": universe_breadth_eligible,
        },
        "history": {
            **artifact_summary(history_meta, history_symbols, history_rows),
            "date_min": history_date_min,
            "as_of_date": history_as_of_date,
            "symbols_before_as_of_date_count": len(history_stale_symbols),
            "symbols_before_as_of_date": history_stale_symbols,
        },
        "clean_pool": {
            **artifact_summary(clean_meta, clean_symbols, clean_rows),
            "removed_symbol_count": len(removed_symbols),
            "removed_symbols": removed_symbols,
            "partial_result": bool(clean_meta["partial_result"]),
        },
        "artifacts": artifacts,
    }


def comparable_provenance(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key != "generated_at"}


def validated_symbol_set(frame: Any, label: str, *, require_a_share: bool = False) -> set[str]:
    if "symbol" not in frame:
        raise ValueError(f"{label} is missing symbol column")
    symbols = {str(value).strip() for value in frame["symbol"]}
    if "" in symbols or any(not symbol.isdigit() or len(symbol) != 6 for symbol in symbols):
        raise ValueError(f"{label} has invalid symbol")
    if require_a_share and any(not symbol.startswith(A_SHARE_PREFIXES) for symbol in symbols):
        raise ValueError(f"{label} has symbol outside Shanghai/Shenzhen A shares")
    if require_a_share and len(frame) != len(symbols):
        raise ValueError(f"{label} has duplicate symbols")
    if not symbols:
        raise ValueError(f"{label} has no symbols")
    return symbols


def validate_price_keys(frame: Any, label: str) -> None:
    if "date" not in frame:
        raise ValueError(f"{label} is missing date column")
    if frame[["symbol", "date"]].isna().any().any():
        raise ValueError(f"{label} has missing symbol/date values")
    if frame.duplicated(subset=["symbol", "date"]).any():
        raise ValueError(f"{label} has duplicate symbol/date rows")


def validated_date_range(frame: Any, label: str) -> tuple[str, str]:
    values = frame["date"].astype(str).str.strip().str.replace("-", "", regex=False)
    if values.empty or not values.str.fullmatch(r"\d{8}").all():
        raise ValueError(f"{label} has invalid date values")
    date_min = normalized_date(values.min(), f"{label} date_min")
    date_max = normalized_date(values.max(), f"{label} date_max")
    return date_min, date_max


def normalized_date(value: Any, label: str) -> str:
    text = str(value or "").strip().replace("-", "")
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"{label} is invalid")
    try:
        parsed = datetime.strptime(text, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{label} is invalid") from exc
    return parsed.date().isoformat()


def expected_reason_symbols(
    history_meta: dict[str, Any],
    short_data: dict[str, Any],
    short_history: Path | None,
) -> dict[str, set[str]]:
    return {
        "empty_history": metadata_symbol_set(history_meta.get("empty_symbols")),
        "short_history": (
            metadata_symbol_set(short_data.get("symbols"))
            if short_history is not None
            else set()
        ),
        "failed_fetch": metadata_symbol_set(history_meta.get("failed_symbols")),
        "possibly_truncated": metadata_symbol_set(
            history_meta.get("possibly_truncated_symbols", [])
        ),
        "unprocessed_fetch": metadata_symbol_set(
            history_meta.get("unprocessed_symbols", [])
        ),
    }


def validate_reason_breakdown(
    report: dict[str, Any],
    removed: list[str],
    expected: dict[str, set[str]],
) -> None:
    reason_symbols = report.get("reason_symbols")
    reason_counts = report.get("reason_counts")
    if not isinstance(reason_symbols, dict) or not isinstance(reason_counts, dict):
        raise ValueError("clean report reason breakdown is missing")
    if set(reason_symbols) != set(reason_counts) or set(reason_symbols) != set(expected):
        raise ValueError("clean report reason keys do not match")
    covered: set[str] = set()
    for reason, values in reason_symbols.items():
        symbols = metadata_symbol_set(values)
        require_count(reason_counts, reason, len(symbols), "clean report reason_counts")
        if symbols != expected[reason]:
            raise ValueError(f"clean report {reason} symbols do not match source artifact")
        covered.update(symbols)
    if covered != set(removed):
        raise ValueError("clean report reason symbols do not match removals")


def metadata_symbol_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        raise ValueError("metadata symbol list is missing")
    symbols = metadata_symbols(value)
    if len(symbols) != len(value):
        raise ValueError("metadata symbol list has duplicates or invalid entries")
    return set(symbols)


def metadata_symbol_record_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        raise ValueError("metadata symbol records are missing")
    records = [item for item in value if isinstance(item, dict)]
    if len(records) != len(value):
        raise ValueError("metadata symbol records are invalid")
    return metadata_symbol_set(records)


def require_count(metadata: dict[str, Any], key: str, expected: int, label: str) -> None:
    actual = non_negative_count(metadata, key, label)
    if actual != expected:
        raise ValueError(f"{label} {key} does not match artifact")


def non_negative_count(metadata: dict[str, Any], key: str, label: str) -> int:
    try:
        value = int(metadata.get(key, -1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} {key} is invalid") from exc
    if value < 0:
        raise ValueError(f"{label} {key} is invalid")
    return value


def require_same_path(value: Any, expected: Path, label: str) -> None:
    if Path(str(value or "")).resolve() != expected.resolve():
        raise ValueError(f"{label} does not match expected artifact")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
