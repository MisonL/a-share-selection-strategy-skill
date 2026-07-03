"""Output finalization and stale cleanup for today's A-share runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from a_share_selection_html_i18n import initial_report_language
from a_share_selection_html_report import write_html_report
from run_today_a_share_selection_helpers import (
    same_existing_path,
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
) -> None:
    requested_language = str(args.html_report_language)
    initial_language = initial_report_language(requested_language)
    manifest["html_report_language"] = requested_language
    manifest["html_report_initial_language"] = initial_language
    manifest["html_report_written"] = False
    manifest["html_report_error_type"] = ""
    manifest["html_report_error"] = ""
    write_json(manifest, manifest_path)

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
    else:
        write_optional_report(summary, manifest, report_path, requested_language)
    mark_core_outputs_written(summary, manifest, manifest_path, summary_path)
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
) -> None:
    fields = {
        "manifest_output": str(manifest_path),
        "manifest_output_written": manifest_path.exists(),
        "summary_output": str(summary_path),
        "summary_output_written": summary_path.exists(),
    }
    manifest.update(fields)
    summary.update(fields)


def remove_stale_output_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        raise IsADirectoryError(f"stale run output path is a directory: {path}")
    path.unlink()


def clear_stale_run_outputs(args: Any, output: Path) -> None:
    paths = [output / name for name in STALE_RUN_OUTPUTS]
    paths.append(output / f"prices{tabular_suffix(args.prices_input or '')}")
    if args.spot_input or args.fetch_spot:
        paths.append(output / f"spot{tabular_suffix(args.spot_input or '')}")
    protected = [Path(value) for value in [args.prices_input, args.spot_input] if value]
    for path in paths:
        if not protected_run_output(path, protected):
            remove_stale_output_path(path)


def protected_run_output(path: Path, protected: list[Path]) -> bool:
    return any(same_existing_path(path, source) for source in protected)


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
    "candidates.csv", "diagnostics.csv", "history_metadata.json",
    "selected_symbols.json", "spot_metadata.json",
)

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
