"""Data loading helpers for the local A-share HTML report."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from a_share_selection_html_format import failure_reason


HTML_REPORT_ROWS_LIMIT = 25
HTML_DIAGNOSTIC_ROWS_LIMIT = 80


def candidate_rows(summary: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    if not output_written(summary, "candidates_output_written"):
        return [], False
    return read_csv_rows(summary.get("candidates_output", ""), HTML_REPORT_ROWS_LIMIT)


def diagnostic_rows(summary: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    if not output_written(summary, "diagnostics_output_written"):
        return [], False
    rows, truncated = read_csv_rows(summary.get("diagnostics_output", ""), HTML_DIAGNOSTIC_ROWS_LIMIT)
    return [diagnostic_display_row(row) for row in rows], truncated


def output_written(summary: dict[str, Any], key: str) -> bool:
    return summary.get(key) is True


def diagnostic_display_row(row: dict[str, Any]) -> dict[str, Any]:
    display = dict(row)
    display["failure_reason"] = failure_reason(row)
    return display


def read_csv_rows(path_value: Any, limit: int) -> tuple[list[dict[str, Any]], bool]:
    path = Path(str(path_value)) if path_value else Path()
    if not path_value or not path.is_file() or path.suffix.lower() != ".csv":
        return [], False
    with path.open(encoding="utf-8", newline="") as handle:
        rows = []
        for index, row in enumerate(csv.DictReader(handle)):
            if index >= limit:
                return rows, True
            rows.append(row)
    return rows, False


def report_output_dir(summary: dict[str, Any]) -> Path | None:
    for key in ("html_report", "candidates_output", "diagnostics_output", "prices_output"):
        value = str(summary.get(key, ""))
        if value:
            return Path(value).parent
    return None


def evidence_path(value: Any, output_dir: Path | None) -> dict[str, str]:
    path_text = str(value) if value else ""
    if not path_text:
        return {"display": "", "title": ""}
    path = Path(path_text)
    display = relative_or_name(path, output_dir)
    return {"display": display, "title": path_text}


def relative_or_name(path: Path, output_dir: Path | None) -> str:
    if output_dir is not None:
        try:
            relative = path.resolve().relative_to(output_dir.resolve())
            return f"./{relative.as_posix()}"
        except (OSError, ValueError):
            pass
    return path.name or str(path)


def summary_path(summary: dict[str, Any]) -> str:
    output_dir = report_output_dir(summary)
    return str(output_dir / "summary.json") if output_dir is not None else ""


def manifest_path(summary: dict[str, Any]) -> str:
    output_dir = report_output_dir(summary)
    return str(output_dir / "run_manifest.json") if output_dir is not None else ""


def first_line(value: Any) -> str:
    for line in str(value).splitlines():
        if line.strip():
            return line.strip()
    return ""
