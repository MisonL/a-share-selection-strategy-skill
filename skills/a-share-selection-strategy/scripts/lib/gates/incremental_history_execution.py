"""Execute and aggregate incremental history fetch buckets."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from lib.gates.incremental_history_artifacts import (
    CLAIM_BOUNDARY,
    combine_csv,
    combine_metadata,
    now_iso,
    publish_output_pair,
    read_json,
    remove_staged_output,
    required_text,
    staged_output_path,
    validate_bucket_artifacts,
    write_json,
)
from lib.gates.incremental_history_plan import validate_bucket_coverage


PLAN_BOUNDARY = "incremental_history_plan_only_not_history_fetch_success"
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
            bool(config.get("baostock_allow_non_trading_empty")),
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
        validate_bucket_artifacts(
            bucket,
            paths,
            config["provider"],
            allow_non_trading_empty=bool(
                config.get("baostock_allow_non_trading_empty")
            ),
        )
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
    ]
    if not (
        provider == "baostock"
        and config.get("baostock_allow_non_trading_empty")
    ):
        command.append("--fail-on-fetch-error")
    if provider == "zzshare":
        command.extend(zzshare_checkpoint_arguments(paths, config))
        command.extend(zzshare_runtime_arguments(config))
    elif provider == "baostock":
        command.extend(baostock_runtime_arguments(config))
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


def baostock_runtime_arguments(config: dict[str, Any]) -> list[str]:
    values: list[str] = []
    names_input = config.get("baostock_names_input")
    if names_input is not None:
        values.extend(["--names-input", str(names_input)])
    missing_name_policy = config.get("baostock_missing_name_policy")
    if missing_name_policy is not None:
        values.extend(["--missing-name-policy", str(missing_name_policy)])
    non_trading_policy = config.get("baostock_non_trading_policy")
    if non_trading_policy is not None:
        values.extend(["--non-trading-policy", str(non_trading_policy)])
    if config.get("baostock_drop_invalid_rows"):
        values.append("--drop-invalid-rows")
    return values


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
        "baostock_names_input": (
            str(config["baostock_names_input"])
            if config.get("baostock_names_input") is not None
            else ""
        ),
        "baostock_missing_name_policy": config.get(
            "baostock_missing_name_policy"
        ),
        "baostock_non_trading_policy": config.get(
            "baostock_non_trading_policy"
        ),
        "baostock_drop_invalid_rows": bool(
            config.get("baostock_drop_invalid_rows")
        ),
        "baostock_allow_non_trading_empty": bool(
            config.get("baostock_allow_non_trading_empty")
        ),
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
    allow_non_trading_empty: bool,
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
    validate_bucket_artifacts(
        bucket,
        paths,
        provider,
        allow_non_trading_empty=allow_non_trading_empty,
    )
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
        "schema_version": 3,
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
    elif provider == "baostock":
        names_input = config.get("baostock_names_input")
        contract["baostock"] = {
            "names_input": str(names_input) if names_input is not None else "",
            "names_input_fingerprint": (
                file_fingerprint(Path(names_input))
                if names_input is not None
                else None
            ),
            "missing_name_policy": config.get("baostock_missing_name_policy"),
            "non_trading_policy": config.get("baostock_non_trading_policy"),
            "drop_invalid_rows": bool(config.get("baostock_drop_invalid_rows")),
            "allow_non_trading_empty": bool(
                config.get("baostock_allow_non_trading_empty")
            ),
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
            "max_bucket_symbols",
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


def write_manifest(manifest: dict[str, Any], path: Path) -> None:
    manifest["updated_at"] = now_iso()
    write_json(manifest, path)


def default_scripts_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def default_python() -> str:
    return sys.executable
