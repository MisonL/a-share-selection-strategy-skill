"""Auditable sidecars for reusable filtered prices artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_symbols import symbol_set_sha256


SIDECAR_SCHEMA_VERSION = 1
CLAIM_BOUNDARY = "filtered_prices_sidecar_not_new_market_data_or_full_market_proof"


def sidecar_path(prices: Path) -> Path:
    return prices.with_name(prices.name + ".metadata.json")


def build_sidecar(
    *,
    prices: Path,
    frame: Any,
    filter_metadata: dict[str, Any],
    input_metadata: dict[str, Any],
) -> dict[str, Any]:
    dates = normalized_dates(frame)
    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "source": "filtered_prices_sidecar",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": now_iso(),
        "artifact": artifact_fingerprint(prices),
        "rows": int(len(frame)),
        "symbol_count": frame_symbol_count(frame),
        "symbol_set_sha256": frame_symbol_set_sha256(frame),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
        "filter_contract": dict(filter_metadata),
        "input_metadata": dict(input_metadata),
    }


def write_sidecar(data: dict[str, Any], prices: Path) -> Path:
    path = sidecar_path(prices)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def load_verified_sidecar(prices: Path) -> dict[str, Any]:
    path = sidecar_path(prices)
    if not path.is_file():
        raise ValueError(f"filtered prices sidecar not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"filtered prices sidecar must be a JSON object: {path}")
    if data.get("schema_version") != SIDECAR_SCHEMA_VERSION:
        raise ValueError(f"filtered prices sidecar schema_version is invalid: {path}")
    if data.get("claim_boundary") != CLAIM_BOUNDARY:
        raise ValueError(f"filtered prices sidecar claim_boundary is invalid: {path}")
    expected = data.get("artifact")
    actual = artifact_fingerprint(prices)
    if not isinstance(expected, dict) or not artifact_identity_matches(expected, actual):
        raise ValueError(f"filtered prices sidecar fingerprint mismatch: {path}")
    metadata = data.get("input_metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"filtered prices sidecar input_metadata is missing: {path}")
    contract = data.get("filter_contract")
    if not isinstance(contract, dict):
        raise ValueError(f"filtered prices sidecar filter_contract is missing: {path}")
    actual_summary = artifact_table_summary(prices)
    summary_keys = ["rows", "symbol_count", "date_min", "date_max"]
    if "symbol_set_sha256" in data:
        summary_keys.append("symbol_set_sha256")
    expected_summary = {key: data.get(key) for key in summary_keys}
    if expected_summary != {key: actual_summary[key] for key in summary_keys}:
        raise ValueError(
            f"filtered prices sidecar table statistics mismatch: {path}"
        )
    validate_filter_contract(contract, actual_summary, prices, path)
    return data


def artifact_table_summary(prices: Path) -> dict[str, Any]:
    import pandas as pd

    try:
        frame = pd.read_parquet(prices, columns=["symbol", "date"])
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            f"filtered prices sidecar cannot read symbol/date columns: {prices}"
        ) from exc
    symbols = validated_symbol_series(frame, prices)
    dates = normalized_dates(frame)
    return {
        "rows": int(len(frame)),
        "symbol_count": int(symbols.nunique()),
        "symbol_set_sha256": symbol_set_sha256(set(symbols.tolist())),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
    }


def validate_filter_contract(
    contract: dict[str, Any],
    summary: dict[str, Any],
    prices: Path,
    sidecar: Path,
) -> None:
    checks = (
        ("prices_filter_output_rows", "rows"),
        ("prices_filter_kept_symbol_count", "symbol_count"),
    )
    for contract_key, summary_key in checks:
        if contract_key not in contract:
            continue
        try:
            value = int(contract[contract_key])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"filtered prices sidecar {contract_key} is invalid: {sidecar}"
            ) from exc
        if value != summary[summary_key]:
            raise ValueError(
                f"filtered prices sidecar filter contract mismatch: {contract_key}"
            )
    declared_hash = str(contract.get("prices_filter_kept_symbol_set_sha256", ""))
    if declared_hash and declared_hash != summary["symbol_set_sha256"]:
        raise ValueError(
            "filtered prices sidecar filter contract mismatch: "
            "prices_filter_kept_symbol_set_sha256"
        )
    declared = str(contract.get("prices_filter_output_prices", "")).strip()
    if declared and Path(declared).resolve() != prices.resolve():
        raise ValueError(
            "filtered prices sidecar filter contract output path mismatch: "
            f"{sidecar}"
        )


def artifact_fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"prices artifact not found: {path}")
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.resolve()),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": digest.hexdigest(),
    }


def artifact_identity_matches(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> bool:
    return all(
        expected.get(key) == actual.get(key)
        for key in ("path", "size_bytes", "sha256")
    )


def normalized_dates(frame: Any) -> list[str]:
    if "date" not in frame or frame.empty:
        return []
    from lib.selection_core.a_share_selection_data import parse_dates

    parsed = parse_dates(frame["date"])
    if parsed.isna().any():
        raise ValueError("filtered prices contains invalid date values")
    return parsed.dt.date.astype(str).tolist()


def frame_symbol_count(frame: Any) -> int:
    if "symbol" not in frame or frame.empty:
        return 0
    return int(validated_symbol_series(frame, None).nunique())


def frame_symbol_set_sha256(frame: Any) -> str:
    if "symbol" not in frame or frame.empty:
        return symbol_set_sha256(set())
    return symbol_set_sha256(set(validated_symbol_series(frame, None).tolist()))


def validated_symbol_series(frame: Any, prices: Path | None) -> Any:
    raw = frame["symbol"]
    location = f": {prices}" if prices is not None else ""
    if raw.isna().any():
        raise ValueError(f"filtered prices contains missing symbol values{location}")
    if not raw.map(lambda value: isinstance(value, str)).all():
        raise ValueError(f"filtered prices symbol values must be text{location}")
    symbols = raw.astype(str).str.strip()
    if symbols.eq("").any():
        raise ValueError(f"filtered prices contains empty symbol values{location}")
    return symbols


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
