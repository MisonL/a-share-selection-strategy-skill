"""Output finalization and stale cleanup for today's A-share runner."""

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
import time
from typing import Any

from lib.report_html.a_share_selection_html_i18n import initial_report_language
from lib.report_html.a_share_selection_html_report import write_html_report
from lib.runner.run_today_a_share_selection_helpers import (
    same_existing_path,
    same_path_or_existing_file,
    summary_view,
    tabular_suffix,
    write_json,
)


def finalize_outputs(
    *,
    args: Any,
    manifest: dict[str, Any],
    manifest_path: Path,
    output: Path,
    status: str,
    run_started_monotonic: float,
) -> None:
    finalize_started = time.monotonic()
    requested_language = str(args.html_report_language)
    initial_language = initial_report_language(requested_language)
    manifest["html_report_language"] = requested_language
    manifest["html_report_initial_language"] = initial_language
    manifest["html_report_written"] = False
    manifest["html_report_error_type"] = ""
    manifest["html_report_error"] = ""

    summary = summary_view(manifest, status)
    report_path = output / "report.html"
    summary["html_report"] = str(report_path)
    summary["html_report_written"] = False
    summary["html_report_error_type"] = ""
    summary["html_report_error"] = ""
    summary["html_report_language"] = requested_language
    summary["html_report_initial_language"] = initial_language
    summary_path = output / "summary.json"
    write_json(summary, summary_path)

    if args.no_html_report:
        remove_optional_report(report_path, summary, manifest)
        report_duration = 0.0
    else:
        report_started = time.monotonic()
        write_optional_report(summary, manifest, report_path, requested_language)
        report_duration = round(max(time.monotonic() - report_started, 0.0), 6)
    manifest["html_report_duration_seconds"] = report_duration
    summary["html_report_duration_seconds"] = report_duration
    finalize_duration = round(max(time.monotonic() - finalize_started, 0.0), 6)
    run_duration = round(max(time.monotonic() - run_started_monotonic, 0.0), 6)
    manifest["finalize_duration_seconds"] = finalize_duration
    summary["finalize_duration_seconds"] = finalize_duration
    manifest["run_duration_seconds"] = run_duration
    summary["run_duration_seconds"] = run_duration
    mark_core_outputs_written(
        summary,
        manifest,
        manifest_path,
        summary_path,
        manifest_will_be_written=True,
    )
    sync_summary_fields_to_manifest(summary, manifest)
    write_json(manifest, manifest_path)
    write_json(summary, summary_path)


def write_optional_report(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    report_path: Path,
    language: str,
) -> None:
    try:
        write_html_report(
            summary=summary,
            manifest=manifest,
            output_path=report_path,
            language=language,
        )
    except OSError as exc:
        record_html_report_error(summary, manifest, exc)
        return
    summary["html_report_written"] = True
    manifest["html_report_written"] = True


def remove_optional_report(
    path: Path,
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    try:
        remove_stale_output_path(path)
    except OSError as exc:
        record_html_report_error(summary, manifest, exc)


def record_html_report_error(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    exc: OSError,
) -> None:
    error_type = exc.__class__.__name__
    message = str(exc)
    summary["html_report_error_type"] = error_type
    summary["html_report_error"] = message
    manifest["html_report_error_type"] = error_type
    manifest["html_report_error"] = message


def mark_core_outputs_written(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path,
    summary_path: Path,
    *,
    manifest_will_be_written: bool = False,
) -> None:
    fields = {
        "manifest_output": str(manifest_path),
        "manifest_output_written": manifest_path.is_file() or manifest_will_be_written,
        "summary_output": str(summary_path),
        "summary_output_written": summary_path.is_file(),
    }
    manifest.update(fields)
    summary.update(fields)


def sync_summary_fields_to_manifest(
    summary: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    for key in MANIFEST_SUMMARY_FIELD_KEYS:
        if key in summary:
            manifest[key] = summary[key]


MANIFEST_SUMMARY_FIELD_KEYS = (
    "status",
    "selection_failed_reason",
    "selection_failed_next_action",
    "plan_only_reason",
    "plan_only_next_action",
    "planned_parameters",
    "candidates_output_written",
    "diagnostics_output_written",
    "score_profile_output",
    "score_profile_output_written",
    "history_output_written",
    "history_metadata_output_written",
    "history_metadata_file_exists",
    "history_artifact_status",
    "source_provenance",
    "short_history_symbol_count",
    "short_history_symbols_metadata_output",
    "short_history_symbols_output",
)


def remove_stale_output_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        raise IsADirectoryError(f"stale run output path is a directory: {path}")
    path.unlink()


def clear_stale_run_outputs(args: Any, output: Path) -> None:
    paths = [output / name for name in STALE_RUN_OUTPUTS]
    paths.extend(prices_output_candidates(args, output))
    if args.spot_input or args.fetch_spot:
        paths.append(output / f"spot{tabular_suffix(args.spot_input or '')}")
    validate_symbols_file_cleanup_collision(args, output, paths)
    protected = [
        Path(value)
        for value in [
            args.prices_input,
            args.spot_input,
            getattr(args, "symbols_file", None),
            getattr(args, "full_a_provenance", None),
        ]
        if value
    ]
    for path in paths:
        if not protected_run_output(path, protected):
            remove_stale_output_path(path)


def validate_symbols_file_cleanup_collision(
    args: Any, output: Path, stale_paths: list[Path]
) -> None:
    symbols_file = getattr(args, "symbols_file", None)
    if not symbols_file:
        return
    source = Path(symbols_file)
    blocked = [output / name for name in SYMBOLS_FILE_BLOCKED_OUTPUTS]
    blocked.extend(
        path for path in stale_paths if path.name not in STALE_INPUT_ONLY_OUTPUTS
    )
    for path in blocked:
        if same_path_or_existing_file(path, source):
            raise ValueError(
                f"--symbols-file must not point to runner output path: {source}"
            )


def protected_run_output(path: Path, protected: list[Path]) -> bool:
    return any(same_existing_path(path, source) for source in protected)


def prices_output_candidates(args: Any, output: Path) -> list[Path]:
    suffixes = [".csv", ".parquet", ".pq", tabular_suffix(args.prices_input or "")]
    return [output / f"prices{suffix}" for suffix in dict.fromkeys(suffixes)]


def html_report_stdout_value(manifest: dict[str, Any], output: Path) -> str:
    if not manifest.get("html_report_enabled", True):
        return "disabled"
    if manifest.get("html_report_written"):
        return str(output / "report.html")
    if manifest.get("html_report_error_type"):
        return "unavailable"
    return str(output / "report.html")


def html_report_error_stdout(manifest: dict[str, Any]) -> str:
    error_type = str(manifest.get("html_report_error_type", ""))
    return f" html_report_error_type={error_type}" if error_type else ""


STALE_RUN_OUTPUTS = (
    "candidates.csv",
    "diagnostics.csv",
    "score_profile.json",
    "history_metadata.json",
    "history_symbols.txt",
    "prices_filter.json",
    "prices.parquet.metadata.json",
    "prices.pq.metadata.json",
    "retry_plan.json",
    "retry_symbols.txt",
    "selected_symbols.json",
    "short_history_symbols.json",
    "short_history_symbols.txt",
    "spot_metadata.json",
)
SYMBOLS_FILE_BLOCKED_OUTPUTS = (
    "run_manifest.json",
    "summary.json",
    "report.html",
)
STALE_INPUT_ONLY_OUTPUTS = {"history_symbols.txt", "retry_plan.json", "retry_symbols.txt"}
