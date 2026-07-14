"""Execute and aggregate incremental history fetch buckets."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from lib.gates.incremental_history_plan import validate_bucket_coverage


CLAIM_BOUNDARY = "bucket_fetch_execution_not_full_market_or_selection_proof"
PLAN_BOUNDARY = "incremental_history_plan_only_not_history_fetch_success"
FAILURE_LISTS = ("failed_symbols", "empty_symbols", "possibly_truncated_symbols")
PYTDX_ALLOWED_MERGE_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
Executor = Callable[[list[str]], int]


def load_plan(path: Path) -> dict[str, Any]:
    plan = read_json(path)
    if plan.get("source") != "incremental_history_plan":
        raise ValueError("incremental plan source is invalid")
    if plan.get("claim_boundary") != PLAN_BOUNDARY:
        raise ValueError("incremental plan claim_boundary is invalid")
    buckets = plan.get("fetch_buckets")
    if not isinstance(buckets, list):
        raise ValueError("incremental plan requires fetch_buckets")
    validate_bucket_coverage(plan.get("fetch_symbols", []), buckets)
    validate_buckets(buckets, str(plan.get("target_end_date", "")))
    return plan


def validate_buckets(buckets: list[dict[str, Any]], target: str) -> None:
    ids = []
    for bucket in buckets:
        ids.append(required_text(bucket, "bucket_id"))
        mode = required_text(bucket, "fetch_mode")
        if mode not in {"full", "delta"}:
            raise ValueError(f"invalid fetch_mode: {mode}")
        if mode == "delta" and not required_text(bucket, "start_date"):
            raise ValueError("delta bucket requires start_date")
        if required_text(bucket, "end_date") != target:
            raise ValueError("bucket end_date does not match target_end_date")
        symbols = bucket.get("symbols", [])
        if int(bucket.get("symbol_count", -1)) != len(symbols):
            raise ValueError("bucket symbol_count does not match symbols")
    if len(ids) != len(set(ids)):
        raise ValueError("fetch bucket ids must be unique")


def execute_plan(
    plan: dict[str, Any],
    config: dict[str, Any],
    executor: Executor,
) -> dict[str, Any]:
    execution_started = time.monotonic()
    contract = execution_contract(plan, config)
    contract_digest = json_digest(contract)
    manifest = initial_manifest(plan, config, contract, contract_digest)
    if not plan["fetch_buckets"]:
        return finalize_noop_execution(manifest, config, execution_started)
    prior = load_prior_manifest(config, plan, contract_digest)
    for bucket in plan["fetch_buckets"]:
        paths = bucket_paths(config["output_dir"], bucket["bucket_id"])
        if reusable_bucket(
            prior,
            bucket,
            paths,
            config["resume"],
            config["provider"],
            contract_digest,
        ):
            manifest["buckets"].append(
                reused_bucket_record(prior_bucket(prior, bucket["bucket_id"]))
            )
            continue
        record = execute_bucket(bucket, paths, config, executor, contract_digest)
        manifest["buckets"].append(record)
        write_manifest(manifest, config["manifest_output"])
        if record["status"] != "complete":
            manifest["status"] = "partial"
            manifest["failed_bucket_id"] = bucket["bucket_id"]
            finalize_execution_metrics(manifest, execution_started)
            write_manifest(manifest, config["manifest_output"])
            return manifest
    try:
        aggregate_outputs(plan, manifest, config)
    except Exception as exc:  # noqa: BLE001
        manifest["status"] = "partial"
        manifest["failed_stage"] = "aggregate_outputs"
        manifest["error"] = str(exc)
        finalize_execution_metrics(manifest, execution_started)
        write_manifest(manifest, config["manifest_output"])
        return manifest
    manifest["status"] = "complete"
    manifest["completed_at"] = now_iso()
    finalize_execution_metrics(manifest, execution_started)
    write_manifest(manifest, config["manifest_output"])
    return manifest


def execute_bucket(
    bucket: dict[str, Any],
    paths: dict[str, Path],
    config: dict[str, Any],
    executor: Executor,
    contract_digest: str,
) -> dict[str, Any]:
    prepare_bucket(paths, bucket)
    command = build_fetch_command(bucket, paths, config)
    started = time.monotonic()
    try:
        return_code = executor(command)
        duration = round(time.monotonic() - started, 6)
        record = bucket_record(
            bucket, paths, command, return_code, duration, contract_digest
        )
        if return_code != 0:
            return record
        validate_bucket_artifacts(bucket, paths, config["provider"])
        record["artifact_fingerprints"] = bucket_artifact_fingerprints(paths)
        record["status"] = "complete"
        return record
    except Exception as exc:  # noqa: BLE001
        duration = round(time.monotonic() - started, 6)
        record = bucket_record(bucket, paths, command, -1, duration, contract_digest)
        record["error"] = str(exc)
        return record


def build_fetch_command(
    bucket: dict[str, Any], paths: dict[str, Path], config: dict[str, Any]
) -> list[str]:
    provider = config["provider"]
    script = config["scripts_dir"] / f"fetch_{provider}_a_share.py"
    start = bucket["start_date"] or config["full_start_date"]
    command = [
        config["python_executable"],
        str(script),
        *symbol_arguments(provider, bucket, paths),
        "--start-date",
        start,
        "--end-date",
        bucket["end_date"],
        "--output",
        str(paths["prices"]),
        "--metadata-output",
        str(paths["metadata"]),
        "--fail-on-fetch-error",
    ]
    if provider == "zzshare":
        command.extend(zzshare_checkpoint_arguments(paths, config))
        command.extend(zzshare_runtime_arguments(config))
    return command


def symbol_arguments(
    provider: str, bucket: dict[str, Any], paths: dict[str, Path]
) -> list[str]:
    if provider == "zzshare":
        return ["--symbols-file", str(paths["symbols"])]
    return ["--symbols", ",".join(bucket["symbols"])]


def zzshare_checkpoint_arguments(
    paths: dict[str, Path], config: dict[str, Any]
) -> list[str]:
    values = [
        "--checkpoint-dir",
        str(paths["checkpoint"]),
        "--checkpoint-batch-size",
        str(config["checkpoint_batch_size"]),
    ]
    if config["resume"] and (paths["checkpoint"] / "manifest.json").is_file():
        values.append("--resume-from-checkpoint")
    return values


def zzshare_runtime_arguments(config: dict[str, Any]) -> list[str]:
    values = [
        "--non-trading-policy",
        str(config.get("zzshare_non_trading_policy", "fail")),
    ]
    options = (
        ("--request-interval-seconds", "zzshare_request_interval_seconds"),
        (
            "--max-concurrent-symbol-requests",
            "zzshare_max_concurrent_symbol_requests",
        ),
        (
            "--max-rate-limit-sleep-seconds",
            "zzshare_max_rate_limit_sleep_seconds",
        ),
        ("--max-429-events", "zzshare_max_429_events"),
        ("--max-runtime-seconds", "zzshare_max_runtime_seconds"),
        ("--progress-interval", "zzshare_progress_interval"),
    )
    for flag, key in options:
        value = config.get(key)
        if value is not None:
            values.extend([flag, str(value)])
    return values


def validate_bucket_artifacts(
    bucket: dict[str, Any], paths: dict[str, Path], provider: str
) -> None:
    if not paths["prices"].is_file() or not paths["metadata"].is_file():
        raise ValueError(f"bucket artifacts missing: {bucket['bucket_id']}")
    metadata = read_json(paths["metadata"])
    artifact_provider = str(
        metadata.get("provider") or metadata.get("source") or ""
    ).strip()
    if artifact_provider != provider:
        raise ValueError(
            "bucket metadata provider does not match execution contract"
        )
    if metadata.get("output_written") is not True:
        raise ValueError("bucket metadata requires output_written=true")
    if metadata.get("metadata_output_written") is not True:
        raise ValueError("bucket metadata requires metadata_output_written=true")
    for key in FAILURE_LISTS:
        if metadata_symbols(metadata.get(key, [])):
            raise ValueError(f"bucket metadata has {key}")
    if int(metadata.get("invalid_rows", 0) or 0) != 0:
        raise ValueError("bucket metadata has invalid_rows")
    if metadata.get("partial_result") is True:
        raise ValueError("bucket metadata has partial_result=true")
    if metadata.get("rate_limit_budget_exhausted") is True:
        raise ValueError("bucket metadata exhausted its rate-limit budget")
    if metadata_symbols(metadata.get("unprocessed_symbols", [])):
        raise ValueError("bucket metadata has unprocessed_symbols")
    if int(metadata.get("tradestatus_missing_rows", 0) or 0) != 0:
        raise ValueError("bucket metadata has tradestatus_missing_rows")
    requested = metadata_symbols(metadata.get("requested_symbols", []))
    if requested != sorted(bucket["symbols"]):
        raise ValueError("bucket metadata requested_symbols do not match plan")
    prices = bucket_price_stats(paths["prices"], bucket)
    validate_bucket_metadata_stats(metadata, prices, bucket)


def bucket_price_stats(
    path: Path,
    bucket: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = {"symbol", "date"}.difference(fields)
        if missing:
            raise ValueError(
                "bucket prices missing required columns: " + ", ".join(sorted(missing))
            )
        for row in reader:
            symbol = str(row.get("symbol", "")).strip()
            if len(symbol) != 6 or not symbol.isdigit():
                raise ValueError(f"bucket prices has invalid symbol: {symbol}")
            date = normalize_bucket_date(row.get("date", ""))
            key = (symbol, date)
            if key in seen:
                raise ValueError(f"bucket prices has duplicate symbol/date: {symbol} {date}")
            seen.add(key)
            item = stats.setdefault(
                symbol,
                {"rows": 0, "date_min": date, "date_max": date},
            )
            item["rows"] += 1
            item["date_min"] = min(item["date_min"], date)
            item["date_max"] = max(item["date_max"], date)
    if not seen:
        raise ValueError("bucket prices is empty")
    actual_symbols = sorted(stats)
    expected_symbols = sorted(bucket["symbols"])
    if actual_symbols != expected_symbols:
        raise ValueError("bucket prices symbols do not match plan")
    start = str(bucket.get("start_date", "")).strip()
    end = required_text(bucket, "end_date")
    for symbol, item in stats.items():
        if start and item["date_min"] < start:
            raise ValueError(f"bucket prices date precedes planned start: {symbol}")
        if item["date_max"] > end:
            raise ValueError(f"bucket prices date exceeds planned end: {symbol}")
    return stats


def validate_bucket_metadata_stats(
    metadata: dict[str, Any],
    prices: dict[str, dict[str, Any]],
    bucket: dict[str, Any],
) -> None:
    records = metadata.get("symbols")
    if not isinstance(records, list):
        raise ValueError("bucket metadata symbols must be a list")
    expected: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("bucket metadata symbol record must be an object")
        symbol = str(record.get("symbol", "")).strip()
        if symbol in expected:
            raise ValueError(f"bucket metadata has duplicate symbol record: {symbol}")
        expected[symbol] = record
    if sorted(expected) != sorted(bucket["symbols"]):
        raise ValueError("bucket metadata symbols do not match plan")
    for symbol, actual in prices.items():
        record = expected[symbol]
        try:
            rows = int(record.get("rows", -1))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"bucket metadata rows is invalid: {symbol}") from exc
        if rows != actual["rows"]:
            raise ValueError(f"bucket metadata rows do not match prices: {symbol}")
        for key in ("date_min", "date_max"):
            value = str(record.get(key, "")).strip()
            if not value:
                raise ValueError(f"bucket metadata {key} is missing: {symbol}")
            if normalize_bucket_date(value) != actual[key]:
                raise ValueError(f"bucket metadata {key} does not match prices: {symbol}")
    if "rows" in metadata:
        try:
            metadata_rows = int(metadata["rows"])
        except (TypeError, ValueError) as exc:
            raise ValueError("bucket metadata rows must be an integer") from exc
        actual_rows = sum(item["rows"] for item in prices.values())
        if metadata_rows != actual_rows:
            raise ValueError("bucket metadata total rows do not match prices")


def normalize_bucket_date(value: Any) -> str:
    text = str(value or "").strip()
    compact = text.replace("-", "")
    try:
        parsed = datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"bucket prices has invalid date: {text}") from exc
    return parsed.date().isoformat()


def aggregate_outputs(
    plan: dict[str, Any], manifest: dict[str, Any], config: dict[str, Any]
) -> None:
    records = manifest["buckets"]
    price_paths = [Path(record["prices_output"]) for record in records]
    metadata = [read_json(Path(record["metadata_output"])) for record in records]
    prices_output = Path(config["prices_output"])
    metadata_output = Path(config["metadata_output"])
    token = uuid.uuid4().hex
    staged_prices = staged_output_path(prices_output, token)
    staged_metadata = staged_output_path(metadata_output, token)
    try:
        row_count = combine_csv(price_paths, staged_prices)
        combined = combine_metadata(plan, metadata, config["provider"], row_count)
        write_json(combined, staged_metadata)
        publish_output_pair(
            [(staged_prices, prices_output), (staged_metadata, metadata_output)],
            token,
        )
    except Exception:
        remove_staged_output(staged_prices)
        remove_staged_output(staged_metadata)
        raise
    manifest["prices_output"] = str(config["prices_output"])
    manifest["metadata_output"] = str(config["metadata_output"])
    manifest["row_count"] = row_count
    manifest["prices_output_written"] = True
    manifest["metadata_output_written"] = True


def staged_output_path(output: Path, token: str) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    return output.with_name(f".{output.name}.{token}.stage")


def publish_output_pair(
    outputs: list[tuple[Path, Path]],
    token: str,
) -> None:
    backups: list[tuple[Path, Path]] = []
    published: list[Path] = []
    try:
        for _staged, target in outputs:
            backup = target.with_name(f".{target.name}.{token}.previous")
            if target.exists() or target.is_symlink():
                target.replace(backup)
                backups.append((target, backup))
        for staged, target in outputs:
            staged.replace(target)
            published.append(target)
    except Exception:
        for target in published:
            target.unlink(missing_ok=True)
        for target, backup in reversed(backups):
            if backup.exists() or backup.is_symlink():
                backup.replace(target)
        raise
    else:
        for _target, backup in backups:
            backup.unlink(missing_ok=True)


def remove_staged_output(path: Path) -> None:
    path.unlink(missing_ok=True)
    path.with_suffix(path.suffix + ".tmp").unlink(missing_ok=True)


def finalize_noop_execution(
    manifest: dict[str, Any],
    config: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    for key in ("prices_output", "metadata_output"):
        Path(config[key]).unlink(missing_ok=True)
    manifest.update(
        {
            "status": "complete",
            "no_op": True,
            "no_op_reason": "plan_has_no_fetch_symbols",
            "prices_output_written": False,
            "metadata_output_written": False,
            "row_count": 0,
            "completed_at": now_iso(),
        }
    )
    finalize_execution_metrics(manifest, started)
    write_manifest(manifest, config["manifest_output"])
    return manifest


def combine_csv(inputs: list[Path], output: Path) -> int:
    if not inputs:
        raise ValueError("incremental aggregation requires bucket prices")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    header: list[str] | None = None
    rows = 0
    try:
        with temporary.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target)
            for path in inputs:
                with path.open(encoding="utf-8", newline="") as source:
                    reader = csv.reader(source)
                    current = next(reader, None)
                    if not current:
                        raise ValueError(f"bucket prices has no header: {path}")
                    if header is None:
                        header = current
                        writer.writerow(header)
                    elif current != header:
                        raise ValueError(f"bucket prices columns differ: {path}")
                    for row in reader:
                        writer.writerow(row)
                        rows += 1
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return rows


def combine_metadata(
    plan: dict[str, Any], items: list[dict[str, Any]], provider: str, rows: int
) -> dict[str, Any]:
    symbols = [entry for item in items for entry in item.get("symbols", [])]
    combined = {
        "source": f"{provider}_incremental_bucket_execution",
        "source_claim_boundary": CLAIM_BOUNDARY,
        "generated_at": now_iso(),
        "provider": provider,
        "rows": rows,
        "symbol_count": len(plan["fetch_symbols"]),
        "requested_symbols": plan["fetch_symbols"],
        "symbols": symbols,
        "failed_symbols": [],
        "empty_symbols": [],
        "possibly_truncated_symbols": [],
        "unprocessed_symbols": [],
        "invalid_rows": 0,
        "partial_result": False,
        "rate_limit_budget_exhausted": False,
        "rate_limit_exhaustion_reason": "",
        "output_written": True,
        "metadata_output_written": True,
        "bucket_count": len(items),
    }
    combined.update(combined_fetch_metrics(items, rows))
    combined.update(combined_quality_metrics(items))
    combined.update(provider_capabilities(items, provider))
    return combined


def combined_fetch_metrics(items: list[dict[str, Any]], rows: int) -> dict[str, Any]:
    has_raw_rows = any("raw_rows" in item for item in items)
    raw_rows = (
        sum(int(item.get("raw_rows", 0) or 0) for item in items)
        if has_raw_rows
        else rows
    )
    has_requested_rows = any("requested_raw_rows" in item for item in items)
    requested_rows = (
        sum(int(item.get("requested_raw_rows", 0) or 0) for item in items)
        if has_requested_rows
        else raw_rows
    )
    result = {
        "raw_rows": raw_rows,
        "output_rows": rows,
        "requested_raw_rows": requested_rows,
        "api_request_count": sum(
            int(item.get("api_request_count", 0) or 0) for item in items
        ),
        "overfetch_rows": raw_rows - rows,
        "raw_to_output_ratio": round(raw_rows / rows, 6) if rows else None,
    }
    for key in (
        "rate_limit_429_events",
        "network_retry_events",
        "checkpoint_symbols_skipped",
        "checkpoint_requests_executed",
        "checkpoint_integrity_issue_count",
    ):
        if any(key in item for item in items):
            result[key] = sum(int(item.get(key, 0) or 0) for item in items)
    for key in ("rate_limit_sleep_seconds", "network_retry_sleep_seconds"):
        if any(key in item for item in items):
            result[key] = round(
                sum(float(item.get(key, 0) or 0) for item in items), 6
            )
    return result


def combined_quality_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "raw_non_trading_rows",
        "raw_invalid_non_trading_overlap_rows",
        "non_trading_rows",
        "dropped_non_trading_rows",
        "retained_non_trading_rows",
        "dropped_invalid_rows",
        "tradestatus_missing_rows",
    ):
        if any(key in item for item in items):
            result[key] = sum(int(item.get(key, 0) or 0) for item in items)
    policies = {
        str(item.get("non_trading_policy", "")).strip()
        for item in items
        if str(item.get("non_trading_policy", "")).strip()
    }
    if len(policies) > 1:
        raise ValueError("bucket metadata non_trading_policy values differ")
    if policies:
        result["non_trading_policy"] = next(iter(policies))
    semantics = {
        str(item.get("raw_quality_counter_semantics", "")).strip()
        for item in items
        if str(item.get("raw_quality_counter_semantics", "")).strip()
    }
    if len(semantics) > 1:
        raise ValueError("bucket metadata raw_quality_counter_semantics values differ")
    if semantics:
        result["raw_quality_counter_semantics"] = next(iter(semantics))
    return result


def provider_capabilities(
    items: list[dict[str, Any]], provider: str
) -> dict[str, Any]:
    if provider != "pytdx":
        return {}
    first = items[0] if items else {}
    return {
        "allowed_merge_fields": first.get(
            "allowed_merge_fields", PYTDX_ALLOWED_MERGE_FIELDS
        ),
        "merge_join_keys": first.get("merge_join_keys", ["symbol", "date"]),
        "strict_fields_same_date_required": True,
        "selection_ready": False,
    }


def initial_manifest(
    plan: dict[str, Any],
    config: dict[str, Any],
    contract: dict[str, Any],
    contract_digest: str,
) -> dict[str, Any]:
    return {
        "source": "incremental_history_bucket_execution",
        "claim_boundary": CLAIM_BOUNDARY,
        "generated_at": now_iso(),
        "status": "running",
        "provider": config["provider"],
        "execution_contract": contract,
        "execution_contract_digest": contract_digest,
        "zzshare_non_trading_policy": (
            str(config.get("zzshare_non_trading_policy", "fail"))
            if config["provider"] == "zzshare"
            else "not_applicable"
        ),
        "zzshare_request_interval_seconds": config.get(
            "zzshare_request_interval_seconds"
        ),
        "zzshare_max_concurrent_symbol_requests": config.get(
            "zzshare_max_concurrent_symbol_requests"
        ),
        "zzshare_max_rate_limit_sleep_seconds": config.get(
            "zzshare_max_rate_limit_sleep_seconds"
        ),
        "zzshare_max_429_events": config.get("zzshare_max_429_events"),
        "zzshare_max_runtime_seconds": config.get("zzshare_max_runtime_seconds"),
        "zzshare_progress_interval": config.get("zzshare_progress_interval"),
        "plan_path": str(config["plan_path"]),
        "target_end_date": plan["target_end_date"],
        "planned_bucket_count": len(plan["fetch_buckets"]),
        "planned_symbol_count": len(plan["fetch_symbols"]),
        "buckets": [],
    }


def bucket_record(
    bucket: dict[str, Any],
    paths: dict[str, Path],
    command: list[str],
    return_code: int,
    duration: float,
    contract_digest: str,
) -> dict[str, Any]:
    return {
        "bucket_id": bucket["bucket_id"],
        "fetch_mode": bucket["fetch_mode"],
        "symbol_count": bucket["symbol_count"],
        "status": "failed" if return_code else "validating",
        "return_code": return_code,
        "duration_seconds": duration,
        "artifact_fetch_duration_seconds": duration,
        "current_run_duration_seconds": duration,
        "executed_this_run": True,
        "reused": False,
        "execution_contract_digest": contract_digest,
        "command": command,
        "prices_output": str(paths["prices"]),
        "metadata_output": str(paths["metadata"]),
    }


def reused_bucket_record(record: dict[str, Any]) -> dict[str, Any]:
    reused = dict(record)
    reused["artifact_fetch_duration_seconds"] = float(
        record.get("artifact_fetch_duration_seconds", record.get("duration_seconds", 0.0))
        or 0.0
    )
    reused["current_run_duration_seconds"] = 0.0
    reused["executed_this_run"] = False
    reused["reused"] = True
    return reused


def finalize_execution_metrics(
    manifest: dict[str, Any], started: float
) -> None:
    records = manifest["buckets"]
    executed = [record for record in records if record.get("executed_this_run")]
    reused = [record for record in records if record.get("reused")]
    fetch_duration = sum(
        float(record.get("current_run_duration_seconds", 0.0) or 0.0)
        for record in executed
    )
    executed_symbols = sum(int(record.get("symbol_count", 0) or 0) for record in executed)
    duration = round(max(time.monotonic() - started, 0.0), 6)
    rows = int(manifest.get("row_count", 0) or 0)
    manifest.update(
        {
            "execution_duration_seconds": duration,
            "current_run_fetch_duration_seconds": round(fetch_duration, 6),
            "executed_bucket_count": len(executed),
            "reused_bucket_count": len(reused),
            "executed_symbol_count": executed_symbols,
            "rows_per_second": round(rows / duration, 6) if rows and duration else None,
            "executed_symbols_per_fetch_second": (
                round(executed_symbols / fetch_duration, 6)
                if executed_symbols and fetch_duration
                else None
            ),
        }
    )


def prepare_bucket(paths: dict[str, Path], bucket: dict[str, Any]) -> None:
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["symbols"].write_text("\n".join(bucket["symbols"]) + "\n", encoding="utf-8")
    paths["prices"].unlink(missing_ok=True)
    paths["metadata"].unlink(missing_ok=True)


def bucket_paths(root: Path, bucket_id: str) -> dict[str, Path]:
    bucket_root = root / "buckets" / bucket_id
    return {
        "root": bucket_root,
        "symbols": bucket_root / "symbols.txt",
        "prices": bucket_root / "prices.csv",
        "metadata": bucket_root / "metadata.json",
        "checkpoint": bucket_root / "checkpoint",
    }


def run_command(command: list[str]) -> int:
    return subprocess.run(command, cwd=Path.cwd(), check=False).returncode


def load_prior_manifest(
    config: dict[str, Any], plan: dict[str, Any], contract_digest: str
) -> dict[str, Any]:
    path = config["manifest_output"]
    if not config["resume"] or not path.is_file():
        return {}
    prior = read_json(path)
    if prior.get("plan_path") != str(config["plan_path"]):
        raise ValueError("resume manifest plan_path does not match")
    if prior.get("target_end_date") != plan["target_end_date"]:
        raise ValueError("resume manifest target_end_date does not match")
    if prior.get("execution_contract_digest") != contract_digest:
        raise ValueError("resume manifest execution contract does not match")
    return prior


def reusable_bucket(
    prior: dict[str, Any],
    bucket: dict[str, Any],
    paths: dict[str, Path],
    resume: bool,
    provider: str,
    contract_digest: str,
) -> bool:
    if not resume:
        return False
    record = prior_bucket(prior, bucket["bucket_id"])
    if not record or record.get("status") != "complete":
        return False
    if record.get("execution_contract_digest") != contract_digest:
        raise ValueError("resume bucket execution contract does not match")
    expected_fingerprints = record.get("artifact_fingerprints")
    if not isinstance(expected_fingerprints, dict):
        return False
    if expected_fingerprints != bucket_artifact_fingerprints(paths):
        return False
    validate_bucket_artifacts(bucket, paths, provider)
    return True


def bucket_artifact_fingerprints(paths: dict[str, Path]) -> dict[str, Any]:
    return {
        key: file_fingerprint(paths[key])
        for key in ("prices", "metadata")
    }


def file_fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"size_bytes": -1, "sha256": ""}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def execution_contract(
    plan: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    provider = str(config["provider"])
    contract = {
        "schema_version": 2,
        "provider": provider,
        "plan_digest": json_digest(stable_plan_contract(plan)),
        "full_start_date": str(config.get("full_start_date", "")),
        "checkpoint_batch_size": int(config.get("checkpoint_batch_size", 0) or 0),
    }
    if provider == "zzshare":
        contract["zzshare"] = {
            "non_trading_policy": str(
                config.get("zzshare_non_trading_policy", "fail")
            ),
            "request_interval_seconds": config.get(
                "zzshare_request_interval_seconds"
            ),
            "max_concurrent_symbol_requests": config.get(
                "zzshare_max_concurrent_symbol_requests"
            ),
            "max_rate_limit_sleep_seconds": config.get(
                "zzshare_max_rate_limit_sleep_seconds"
            ),
            "max_429_events": config.get("zzshare_max_429_events"),
            "max_runtime_seconds": config.get("zzshare_max_runtime_seconds"),
            "progress_interval": config.get("zzshare_progress_interval"),
        }
    return contract


def stable_plan_contract(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        key: plan.get(key)
        for key in (
            "source",
            "claim_boundary",
            "target_end_date",
            "min_history_rows",
            "fetch_symbols",
            "fetch_buckets",
        )
        if key in plan
    }


def json_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def prior_bucket(prior: dict[str, Any], bucket_id: str) -> dict[str, Any]:
    return next(
        (item for item in prior.get("buckets", []) if item.get("bucket_id") == bucket_id),
        {},
    )


def metadata_symbols(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    symbols = []
    for item in value:
        raw = item.get("symbol", "") if isinstance(item, dict) else item
        if str(raw).strip():
            symbols.append(str(raw).strip())
    return sorted(set(symbols))


def required_text(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key, "")).strip()
    if not value:
        raise ValueError(f"fetch bucket requires {key}")
    return value


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    manifest["updated_at"] = now_iso()
    write_json(manifest, path)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_scripts_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def default_python() -> str:
    return sys.executable
