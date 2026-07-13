"""Checkpoint artifact helpers for zzshare A-share fetches."""

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

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from lib.fetch.zzshare_a_share_checkpoint_frames import (
    checkpoint_frame,
    checkpoint_metadata,
)


CHECKPOINT_MANIFEST_NAME = "manifest.json"
CHECKPOINT_SCHEMA_VERSION = 2


def prepare_checkpoint(args: Any) -> Optional[dict[str, Any]]:
    path_text = str(getattr(args, "checkpoint_dir", "") or "").strip()
    batch_size = int(getattr(args, "checkpoint_batch_size", 0) or 0)
    if not path_text or batch_size < 1:
        return None
    path = Path(path_text)
    resume = bool(getattr(args, "resume_from_checkpoint", False))
    if path.exists() and not resume:
        reset_checkpoint_dir(path)
    path.mkdir(parents=True, exist_ok=True)
    manifest_path = path / CHECKPOINT_MANIFEST_NAME
    contract = checkpoint_execution_contract(args)
    contract_digest = checkpoint_contract_digest(contract)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_checkpoint_manifest(manifest, contract, contract_digest, manifest_path)
    elif resume:
        raise FileNotFoundError(f"checkpoint manifest not found: {manifest_path}")
    else:
        manifest = {
            "version": CHECKPOINT_SCHEMA_VERSION,
            "execution_contract": contract,
            "execution_contract_sha256": contract_digest,
            "parts": [],
            "part_artifacts": {},
            "symbols": {},
        }
    manifest.setdefault("version", CHECKPOINT_SCHEMA_VERSION)
    manifest.setdefault("parts", [])
    manifest.setdefault("part_artifacts", {})
    manifest.setdefault("symbols", {})
    checkpoint = {
        "dir": path,
        "batch_size": batch_size,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "parts_written": 0,
        "part_symbol_cache": {},
        "part_fingerprint_cache": {},
        "part_integrity_cache": {},
        "integrity_issues": [],
    }
    if not manifest_path.exists():
        write_checkpoint_manifest(checkpoint)
    return checkpoint


def checkpoint_execution_contract(args: Any) -> dict[str, Any]:
    endpoint = checkpoint_endpoint_contract(getattr(args, "http_url", ""))
    return {
        "provider": "zzshare",
        **endpoint,
        "start_date": normalized_contract_date(getattr(args, "start_date", "")),
        "end_date": normalized_contract_date(getattr(args, "end_date", "")),
        "fields": str(getattr(args, "fields", "") or "").strip(),
        "adjust": str(getattr(args, "adjust", "") or "").strip(),
        "limit": int(getattr(args, "limit", 0) or 0),
        "max_pages": int(getattr(args, "max_pages", 0) or 0),
        "timeout_seconds": float(getattr(args, "timeout_seconds", 0) or 0),
        "request_interval_seconds": float(
            getattr(args, "request_interval_seconds", 0) or 0
        ),
        "max_concurrent_symbol_requests": int(
            getattr(args, "max_concurrent_symbol_requests", 1) or 1
        ),
        "max_rate_limit_sleep_seconds": float(
            getattr(args, "max_rate_limit_sleep_seconds", 0) or 0
        ),
        "max_429_events": int(getattr(args, "max_429_events", 0) or 0),
        "max_runtime_seconds": float(
            getattr(args, "max_runtime_seconds", 0) or 0
        ),
        "non_trading_policy": str(
            getattr(args, "non_trading_policy", "fail") or "fail"
        ),
        "drop_invalid_rows": bool(getattr(args, "drop_invalid_rows", False)),
    }


def checkpoint_endpoint_contract(value: Any) -> dict[str, str]:
    raw = str(value or "").strip().rstrip("/")
    parsed = urlsplit(raw)
    host = str(parsed.hostname or "")
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is not None:
        host = f"{host}:{port}"
    return {
        "http_url_host": host,
        "http_url_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


def normalized_contract_date(value: Any) -> str:
    return str(value or "").strip().replace("-", "")


def checkpoint_contract_digest(contract: dict[str, Any]) -> str:
    payload = json.dumps(
        contract,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_checkpoint_manifest(
    manifest: Any,
    contract: dict[str, Any],
    contract_digest: str,
    path: Path,
) -> None:
    if not isinstance(manifest, dict):
        raise ValueError(f"checkpoint manifest must be a JSON object: {path}")
    if manifest.get("version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError(
            "checkpoint execution contract is missing or incompatible; "
            f"start a fresh checkpoint directory: {path}"
        )
    if manifest.get("execution_contract_sha256") != contract_digest:
        raise ValueError(
            "checkpoint execution contract does not match the current fetch: "
            f"{path}"
        )
    if manifest.get("execution_contract") != contract:
        raise ValueError(
            "checkpoint execution contract payload does not match its digest: "
            f"{path}"
        )
    if not isinstance(manifest.get("parts"), list):
        raise ValueError(f"checkpoint manifest parts must be a list: {path}")
    if "part_artifacts" in manifest and not isinstance(
        manifest.get("part_artifacts"), dict
    ):
        raise ValueError(f"checkpoint manifest part_artifacts must be an object: {path}")
    if not isinstance(manifest.get("symbols"), dict):
        raise ValueError(f"checkpoint manifest symbols must be an object: {path}")


def empty_checkpoint_batch() -> dict[str, Any]:
    return {"rows": [], "records": []}


def completed_checkpoint_record(
    checkpoint: Optional[dict[str, Any]],
    symbol: str,
) -> Optional[dict[str, Any]]:
    if checkpoint is None:
        return None
    record = checkpoint["manifest"].get("symbols", {}).get(symbol)
    if not isinstance(record, dict) or record.get("status") != "completed":
        return None
    part = str(record.get("part", ""))
    expected_rows = int(record.get("rows", 0) or 0)
    if expected_rows < 1 or not part:
        append_checkpoint_integrity_issue(
            checkpoint,
            symbol,
            part,
            "completed_record_has_no_rows",
        )
        return None
    if not (checkpoint["dir"] / part).is_file():
        append_checkpoint_integrity_issue(
            checkpoint,
            symbol,
            part,
            "completed_record_part_missing",
        )
        return None
    integrity_issue = checkpoint_part_integrity_issue(checkpoint, part)
    if integrity_issue:
        append_checkpoint_integrity_issue(
            checkpoint,
            "",
            part,
            integrity_issue,
        )
        return None
    actual_rows = checkpoint_part_symbol_count(checkpoint, part, symbol)
    if actual_rows < 1:
        append_checkpoint_integrity_issue(
            checkpoint,
            symbol,
            part,
            "completed_record_symbol_missing_from_part",
        )
        return None
    if actual_rows != expected_rows:
        append_checkpoint_integrity_issue(
            checkpoint,
            symbol,
            part,
            "completed_record_symbol_row_count_mismatch",
        )
        return None
    return record


def reset_checkpoint_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if child.name == CHECKPOINT_MANIFEST_NAME or child.name == "manifest.tmp":
            child.unlink()
            continue
        if (
            child.is_file()
            and child.name.startswith("prices_part_")
            and child.name.endswith((".csv", ".csv.tmp"))
        ):
            child.unlink()


def checkpoint_part_symbol_count(
    checkpoint: dict[str, Any],
    part: str,
    symbol: str,
) -> int:
    cache = checkpoint.setdefault("part_symbol_cache", {})
    if part not in cache:
        cache[part] = checkpoint_part_symbol_counts(checkpoint["dir"] / part)
    return int(cache.get(part, {}).get(str(symbol), 0))


def checkpoint_part_symbol_counts(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if "symbol" not in (reader.fieldnames or []):
            return {}
        counts: dict[str, int] = {}
        for row in reader:
            symbol = str(row.get("symbol", "")).strip()
            if symbol:
                counts[symbol] = counts.get(symbol, 0) + 1
        return counts


def checkpoint_part_integrity_issue(
    checkpoint: dict[str, Any],
    part: str,
) -> str:
    cache = checkpoint.setdefault("part_integrity_cache", {})
    if part in cache:
        return str(cache[part])
    expected = checkpoint["manifest"].get("part_artifacts", {}).get(part)
    if not isinstance(expected, dict):
        issue = "completed_record_part_fingerprint_missing"
    else:
        actual = checkpoint_part_fingerprint_cached(checkpoint, part)
        issue = (
            ""
            if checkpoint_part_fingerprint_matches(expected, actual)
            else "completed_record_part_fingerprint_mismatch"
        )
    cache[part] = issue
    return issue


def checkpoint_part_fingerprint_cached(
    checkpoint: dict[str, Any],
    part: str,
) -> dict[str, Any]:
    cache = checkpoint.setdefault("part_fingerprint_cache", {})
    if part not in cache:
        cache[part] = checkpoint_part_fingerprint(checkpoint["dir"] / part)
    return dict(cache[part])


def checkpoint_part_fingerprint(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "size_bytes": int(path.stat().st_size),
        "sha256": digest.hexdigest(),
    }


def checkpoint_part_fingerprint_matches(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> bool:
    return all(
        expected.get(key) == actual.get(key)
        for key in ("size_bytes", "sha256")
    )


def append_checkpoint_integrity_issue(
    checkpoint: dict[str, Any],
    symbol: str,
    part: str,
    issue: str,
) -> None:
    issues = checkpoint.setdefault("integrity_issues", [])
    record = {"symbol": str(symbol), "part": str(part), "issue": str(issue)}
    if record not in issues:
        issues.append(record)


def append_checkpoint_record(
    checkpoint: Optional[dict[str, Any]],
    batch: dict[str, Any],
    symbol: str,
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    failure: Optional[dict[str, Any]],
    possible_truncated: bool,
) -> None:
    if checkpoint is None:
        return
    batch["rows"].extend(rows)
    batch["records"].append(
        {
            "symbol": symbol,
            "rows": len(rows),
            "metadata": metadata,
            "failure": failure or {},
            "possibly_truncated": bool(possible_truncated),
        }
    )


def flush_checkpoint_batch_if_ready(
    checkpoint: Optional[dict[str, Any]],
    batch: dict[str, Any],
    pd_module: Any,
    output_columns: list[str],
) -> None:
    if checkpoint is None:
        return
    if len(batch["records"]) >= int(checkpoint["batch_size"]):
        flush_checkpoint_batch(checkpoint, batch, pd_module, output_columns)


def flush_checkpoint_batch(
    checkpoint: Optional[dict[str, Any]],
    batch: dict[str, Any],
    pd_module: Any,
    output_columns: list[str],
) -> None:
    if checkpoint is None or not batch["records"]:
        return
    manifest = checkpoint["manifest"]
    parts = manifest["parts"]
    part_name = ""
    if batch["rows"]:
        part_name = f"prices_part_{len(parts) + 1:05d}.csv"
        frame = pd_module.DataFrame(batch["rows"], columns=output_columns)
        part_path = checkpoint["dir"] / part_name
        temporary = part_path.with_suffix(part_path.suffix + ".tmp")
        frame.to_csv(temporary, index=False)
        temporary.replace(part_path)
        parts.append(part_name)
        artifact = checkpoint_part_fingerprint(part_path)
        manifest["part_artifacts"][part_name] = artifact
        checkpoint.setdefault("part_fingerprint_cache", {})[part_name] = artifact
        checkpoint.setdefault("part_integrity_cache", {})[part_name] = ""
        checkpoint["parts_written"] += 1
    symbols = manifest["symbols"]
    for record in batch["records"]:
        status = checkpoint_record_status(record)
        symbols[record["symbol"]] = {
            "status": status,
            "rows": int(record["rows"]),
            "part": part_name if record["rows"] else "",
            "metadata": record["metadata"],
            "failure": record["failure"],
            "possibly_truncated": bool(record["possibly_truncated"]),
        }
    write_checkpoint_manifest(checkpoint)
    batch["rows"].clear()
    batch["records"].clear()


def checkpoint_record_status(record: dict[str, Any]) -> str:
    if record["failure"]:
        return "failed"
    if record["possibly_truncated"]:
        return "truncated"
    if int(record["rows"]) < 1:
        return "empty"
    return "completed"


def write_checkpoint_manifest(checkpoint: dict[str, Any]) -> None:
    path = checkpoint["manifest_path"]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            checkpoint["manifest"],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)
