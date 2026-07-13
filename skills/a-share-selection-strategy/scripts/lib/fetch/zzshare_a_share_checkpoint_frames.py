"""Checkpoint frame loading helpers for zzshare A-share fetches."""

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

from typing import Any, Optional


def checkpoint_frame(
    checkpoint: Optional[dict[str, Any]],
    pd_module: Any,
    output_columns: list[str],
    requested_symbols: list[str] | None = None,
) -> Optional[Any]:
    if checkpoint is None:
        return None
    frames = completed_checkpoint_frames(checkpoint, pd_module, requested_symbols)
    if not frames:
        return pd_module.DataFrame(columns=output_columns)
    return pd_module.concat(frames, ignore_index=True)


def completed_checkpoint_frames(
    checkpoint: dict[str, Any],
    pd_module: Any,
    requested_symbols: list[str] | None = None,
) -> list[Any]:
    part_cache = {}
    frames = []
    symbols = checkpoint["manifest"].get("symbols", {})
    if not isinstance(symbols, dict):
        return frames
    requested = (
        None
        if requested_symbols is None
        else {str(symbol) for symbol in requested_symbols}
    )
    part_symbols = completed_part_symbols(symbols, requested)
    for part in unique_parts(checkpoint["manifest"].get("parts", [])):
        frame = cached_checkpoint_part(checkpoint, part_cache, part, pd_module)
        if frame is None or frame.empty:
            continue
        allowed = part_symbols.get(part, set())
        if not allowed:
            continue
        frames.append(frame[frame["symbol"].astype(str).isin(allowed)])
    return frames


def completed_part_symbols(
    symbols: dict[str, Any],
    requested_symbols: set[str] | None = None,
) -> dict[str, set[str]]:
    parts: dict[str, set[str]] = {}
    for symbol, record in symbols.items():
        if not isinstance(record, dict) or record.get("status") != "completed":
            continue
        if requested_symbols is not None and str(symbol) not in requested_symbols:
            continue
        part = str(record.get("part", ""))
        if not part:
            continue
        parts.setdefault(part, set()).add(str(symbol))
    return parts


def cached_checkpoint_part(
    checkpoint: dict[str, Any],
    part_cache: dict[str, Any],
    part: str,
    pd_module: Any,
) -> Any:
    if part in part_cache:
        return part_cache[part]
    path = checkpoint["dir"] / part
    if not path.is_file():
        part_cache[part] = None
        return None
    frame = pd_module.read_csv(path, dtype={"symbol": str})
    part_cache[part] = frame
    return frame


def unique_parts(parts: Any) -> list[str]:
    seen = set()
    result = []
    for part in parts if isinstance(parts, list) else []:
        name = str(part)
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def checkpoint_metadata(
    args: Any,
    checkpoint: Optional[dict[str, Any]],
    skipped: int,
    requests: int,
) -> dict[str, Any]:
    if checkpoint is None:
        return {
            "checkpoint_enabled": False,
            "resume_from_checkpoint": False,
            "checkpoint_batch_size": int(getattr(args, "checkpoint_batch_size", 0) or 0),
            "checkpoint_symbols_skipped": 0,
            "checkpoint_requests_executed": requests,
            "checkpoint_parts_written": 0,
            "checkpoint_parts_available": 0,
            "checkpoint_dir": "",
            "checkpoint_integrity_issue_count": 0,
            "checkpoint_integrity_issues": [],
            "checkpoint_schema_version": 0,
            "checkpoint_execution_contract_sha256": "",
        }
    parts = unique_parts(checkpoint["manifest"].get("parts", []))
    issues = list(checkpoint.get("integrity_issues", []))
    return {
        "checkpoint_enabled": True,
        "resume_from_checkpoint": bool(getattr(args, "resume_from_checkpoint", False)),
        "checkpoint_batch_size": int(checkpoint["batch_size"]),
        "checkpoint_symbols_skipped": int(skipped),
        "checkpoint_requests_executed": int(requests),
        "checkpoint_parts_written": int(checkpoint["parts_written"]),
        "checkpoint_parts_available": len(parts),
        "checkpoint_dir": str(checkpoint["dir"]),
        "checkpoint_manifest": str(checkpoint["manifest_path"]),
        "checkpoint_integrity_issue_count": len(issues),
        "checkpoint_integrity_issues": issues,
        "checkpoint_schema_version": int(
            checkpoint["manifest"].get("version", 0) or 0
        ),
        "checkpoint_execution_contract_sha256": str(
            checkpoint["manifest"].get("execution_contract_sha256", "")
        ),
    }
