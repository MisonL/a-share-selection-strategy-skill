"""Validate explicit full-A provenance around final runner scoring."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from lib.gates.full_a_clean_pool_provenance import (
    artifact_fingerprint,
    symbol_set_sha256,
    validate_clean_pool_provenance,
    validated_symbol_set,
)
from lib.gates.clean_history_pool import read_frame
from lib.selection_core.a_share_selection_command_safety import sanitize_text


PENDING_BOUNDARY = "full_a_provenance_pending_final_scoring_validation"
FILTER_EXCLUSION_BOUNDARY = "final_prices_filter_removed_symbols_not_full_market"
VERIFIED_BOUNDARY = (
    "verified_full_a_artifact_chain_and_final_scoring_breadth_"
    "not_realtime_broker_or_return_proof"
)
OUTPUT_FAILURE_BOUNDARY = "full_a_final_scoring_output_validation_failed"
ARTIFACT_FAILURE_BOUNDARY = "full_a_provenance_artifact_validation_failed"


def apply_full_a_provenance_pre_score(
    *,
    args: Any,
    manifest: dict[str, Any],
    prices: Path,
    spot: Path | None,
) -> None:
    if not args.full_a_provenance:
        return
    if spot is None:
        raise ValueError("--full-a-provenance requires a spot input artifact")
    try:
        evidence = validate_full_a_pre_score(
            provenance_path=Path(args.full_a_provenance),
            prices_input=Path(args.prices_input),
            spot_input=Path(args.spot_input),
            final_prices=prices,
            manifest=manifest,
        )
    except Exception as exc:
        record_full_a_provenance_failure(manifest, exc, ARTIFACT_FAILURE_BOUNDARY)
        raise
    manifest.update(evidence)


def complete_full_a_provenance(
    *,
    args: Any,
    manifest: dict[str, Any],
    prices: Path,
    candidates: Path,
    diagnostics: Path,
) -> None:
    if not args.full_a_provenance:
        return
    try:
        evidence = validate_full_a_scoring_outputs(
            final_prices=prices,
            candidates=candidates,
            diagnostics=diagnostics,
        )
    except Exception as exc:
        record_full_a_provenance_failure(manifest, exc, OUTPUT_FAILURE_BOUNDARY)
        remove_unverified_scoring_outputs(manifest, candidates, diagnostics)
        raise
    manifest.update(evidence)
    manifest.update(full_market_decision(manifest))


def record_full_a_provenance_failure(
    manifest: dict[str, Any],
    exc: Exception,
    boundary: str,
) -> None:
    manifest.update(
        {
            "full_a_provenance_validation_status": "failed",
            "full_a_provenance_validation_error": sanitize_text(str(exc)),
            "full_a_provenance_final_scoring_validated": False,
            "coverage_class": "full_a_provenance_failed",
            "full_market_claim_allowed": False,
            "full_market_claim_boundary": boundary,
        }
    )


def remove_unverified_scoring_outputs(
    manifest: dict[str, Any], candidates: Path, diagnostics: Path
) -> None:
    errors = []
    for path in (candidates, diagnostics):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            errors.append(f"{path.name}:{sanitize_text(str(exc))}")
    manifest["full_a_provenance_output_cleanup_errors"] = errors


def validate_full_a_pre_score(
    *,
    provenance_path: Path,
    prices_input: Path,
    spot_input: Path,
    final_prices: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    proof = validate_clean_pool_provenance(provenance_path)
    artifacts = proof["artifacts"]
    require_exact_artifact_path(
        prices_input,
        artifact_path(artifacts, "clean_prices"),
        "--prices-input",
    )
    require_exact_artifact_path(
        spot_input,
        artifact_path(artifacts, "universe_input"),
        "--spot-input",
    )
    clean_symbols = validated_symbol_set(read_frame(prices_input), "prices input")
    final_symbols = validated_symbol_set(read_frame(final_prices), "final prices")
    if not final_symbols.issubset(clean_symbols):
        raise ValueError("final prices contain symbols outside provenance clean prices")
    removed_symbols = sorted(clean_symbols.difference(final_symbols))
    expected_removed = manifest_symbol_set(
        manifest.get("prices_filter_removed_symbols", []),
        "prices_filter_removed_symbols",
    )
    if set(removed_symbols) != expected_removed:
        raise ValueError("final prices removals do not match prices filter metadata")
    validate_filter_counts(manifest, proof, clean_symbols, final_symbols, removed_symbols)
    eligible = bool(proof["full_market_closure_eligible"])
    boundary = pre_score_boundary(proof, eligible, removed_symbols)
    proof_fingerprint = artifact_fingerprint(provenance_path)
    return {
        "full_a_provenance_requested": True,
        "full_a_provenance_input": str(provenance_path.resolve()),
        "full_a_provenance_file_sha256": proof_fingerprint["sha256"],
        "full_a_provenance_validation_status": "pre_score_validated",
        "full_a_provenance_validation_error": "",
        "full_a_provenance_closure_eligible": eligible,
        "full_a_provenance_boundary": proof["full_market_closure_boundary"],
        "full_a_provenance_as_of_date": proof["history"]["as_of_date"],
        "full_a_provenance_universe_symbol_count": int(
            proof["universe"]["symbol_count"]
        ),
        "full_a_provenance_clean_symbol_count": len(clean_symbols),
        "full_a_provenance_clean_pool_removed_symbol_count": int(
            proof["clean_pool"]["removed_symbol_count"]
        ),
        "full_a_provenance_final_prices_symbol_count": len(final_symbols),
        "full_a_provenance_final_filter_removed_symbol_count": len(removed_symbols),
        "full_a_provenance_final_filter_removed_symbols": removed_symbols,
        "full_a_provenance_final_scoring_validated": False,
        "full_a_provenance_candidate_symbol_count": 0,
        "full_a_provenance_diagnostic_symbol_count": 0,
        "full_market_claim_allowed": False,
        "full_market_claim_boundary": boundary,
    }


def validate_full_a_scoring_outputs(
    *,
    final_prices: Path,
    candidates: Path,
    diagnostics: Path,
) -> dict[str, Any]:
    final_symbols = validated_symbol_set(read_frame(final_prices), "final prices")
    diagnostic_symbols = csv_symbol_set(diagnostics, "diagnostics", allow_empty=False)
    candidate_symbols = csv_symbol_set(candidates, "candidates", allow_empty=True)
    if diagnostic_symbols != final_symbols:
        raise ValueError("diagnostics symbols do not exactly cover final prices")
    if not candidate_symbols.issubset(final_symbols):
        raise ValueError("candidate symbols are outside final prices")
    return {
        "full_a_provenance_validation_status": "valid",
        "full_a_provenance_validation_error": "",
        "full_a_provenance_final_scoring_validated": True,
        "full_a_provenance_candidate_symbol_count": len(candidate_symbols),
        "full_a_provenance_diagnostic_symbol_count": len(diagnostic_symbols),
    }


def full_market_decision(manifest: dict[str, Any]) -> dict[str, Any]:
    eligible = bool(manifest.get("full_a_provenance_closure_eligible", False))
    removed_count = int(
        manifest.get("full_a_provenance_final_filter_removed_symbol_count", 0) or 0
    )
    scoring_validated = bool(
        manifest.get("full_a_provenance_final_scoring_validated", False)
    )
    status_valid = manifest.get("full_a_provenance_validation_status") == "valid"
    allowed = eligible and removed_count == 0 and scoring_validated and status_valid
    if allowed:
        return {
            "coverage_class": "full_a_provenance_verified",
            "full_market_claim_allowed": True,
            "full_market_claim_boundary": VERIFIED_BOUNDARY,
        }
    return {
        "full_market_claim_allowed": False,
        "full_market_claim_boundary": str(
            manifest.get("full_market_claim_boundary", PENDING_BOUNDARY)
        ),
    }


def validate_filter_counts(
    manifest: dict[str, Any],
    proof: dict[str, Any],
    clean_symbols: set[str],
    final_symbols: set[str],
    removed_symbols: list[str],
) -> None:
    expected = {
        "prices_filter_spot_symbol_count": int(proof["universe"]["symbol_count"]),
        "prices_filter_input_symbol_count": len(clean_symbols),
        "prices_filter_kept_symbol_count": len(final_symbols),
        "prices_filter_removed_symbol_count": len(removed_symbols),
    }
    for key, expected_value in expected.items():
        if int(manifest.get(key, -1) or 0) != expected_value:
            raise ValueError(f"{key} does not match full-A provenance artifacts")
    if manifest.get("prices_filter_output_written") is not True:
        raise ValueError("full-A provenance requires a written prices filter output")
    if manifest.get("prices_filter_spot_universe") is not True:
        raise ValueError("full-A provenance requires spot-universe filtering")
    as_of_date = str(proof["history"]["as_of_date"])
    if manifest.get("prices_filter_min_symbol_latest_date") != as_of_date:
        raise ValueError(
            "--min-symbol-latest-date must match full-A provenance as_of_date"
        )
    clean_hash = str(proof["clean_pool"]["symbol_set_sha256"])
    if symbol_set_sha256(clean_symbols) != clean_hash:
        raise ValueError("prices input symbols do not match provenance clean pool")


def pre_score_boundary(
    proof: dict[str, Any], eligible: bool, removed_symbols: list[str]
) -> str:
    if not eligible:
        return str(proof["full_market_closure_boundary"])
    if removed_symbols:
        return FILTER_EXCLUSION_BOUNDARY
    return PENDING_BOUNDARY


def artifact_path(artifacts: dict[str, Any], name: str) -> Path:
    record = artifacts.get(name)
    if not isinstance(record, dict) or not str(record.get("path", "")).strip():
        raise ValueError(f"full-A provenance artifact path is missing: {name}")
    return Path(str(record["path"]))


def require_exact_artifact_path(actual: Path, expected: Path, label: str) -> None:
    if actual.resolve() != expected.resolve():
        raise ValueError(f"{label} must exactly match full-A provenance artifact path")


def manifest_symbol_set(value: Any, label: str) -> set[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a symbol list")
    symbols = {normalized_symbol(item, label) for item in value}
    if len(symbols) != len(value):
        raise ValueError(f"{label} has duplicate symbols")
    return symbols


def csv_symbol_set(path: Path, label: str, *, allow_empty: bool) -> set[str]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} output not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "symbol" not in (reader.fieldnames or []):
            raise ValueError(f"{label} output is missing symbol column")
        values = [row.get("symbol", "") for row in reader]
    symbols = {normalized_symbol(value, label) for value in values}
    if len(symbols) != len(values):
        raise ValueError(f"{label} output has duplicate symbols")
    if not allow_empty and not symbols:
        raise ValueError(f"{label} output has no symbols")
    return symbols


def normalized_symbol(value: Any, label: str) -> str:
    symbol = str(value or "").strip()
    if len(symbol) != 6 or not symbol.isdigit():
        raise ValueError(f"{label} has invalid symbol")
    return symbol
