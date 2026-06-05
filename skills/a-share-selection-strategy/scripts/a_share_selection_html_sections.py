"""HTML section builders for the local A-share selection report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from a_share_selection_html_data import (
    HTML_DIAGNOSTIC_ROWS_LIMIT,
    HTML_REPORT_ROWS_LIMIT,
    evidence_path,
    first_line,
    manifest_path,
    report_output_dir,
    summary_path,
)
from a_share_selection_html_format import (
    bilingual,
    display_with_title,
    esc,
    i18n,
    table_cell,
)
from a_share_selection_html_modes import (
    boundary_summary,
    limit_key,
    mode_unresolved,
    mode_reason,
    prediction_status_key,
    scoring_method_key,
)
from run_today_a_share_selection_input_metadata import is_synthetic_demo


DISPLAY_CANDIDATE_COLUMNS = (
    "rank",
    "symbol",
    "name",
    "date",
    "close",
    "spot_price",
    "spot_pct_chg",
    "total_score",
    "key_reasons",
    "risk_notes",
)
DISPLAY_DIAGNOSTIC_COLUMNS = (
    "symbol",
    "name",
    "close",
    "total_score",
    "selection_status",
    "failure_reason",
)


def hero(summary: dict[str, Any], language: str) -> str:
    status = str(summary.get("status", "unknown"))
    heading_key = f"{status}_report"
    return (
        '<section class="hero"><div class="hero-main">'
        f'<p class="eyebrow">{i18n("brand", language)}</p>'
        f"<h1>{i18n(heading_key, language, 'unknown_report')}</h1>"
        f"<p>{i18n('scoring_method', language)}: "
        f"<strong>{i18n(scoring_method_key(summary), language)}</strong>. "
        f"{i18n('candidates_count', language)}: "
        f"<strong>{esc(summary.get('candidate_rows', 0))}</strong>.</p></div>"
        '<div class="hero-actions">'
        f'<span class="status {esc(status_class(status))}">'
        f"{i18n(status_label_key(status), language)}</span>"
        '<div class="language-toggle" aria-label="Language">'
        '<button type="button" data-set-lang="zh">中文</button>'
        '<button type="button" data-set-lang="en">EN</button>'
        "</div></div></section>"
    )


def metric_grid(summary: dict[str, Any], language: str) -> str:
    metrics = [
        (i18n("prices_rows", language), summary.get("prices_rows", 0)),
        (i18n("candidate_rows", language), summary.get("candidate_rows", 0)),
        (i18n("diagnostic_rows", language), summary.get("diagnostic_rows", 0)),
        (i18n("spot_rows", language), summary.get("spot_rows", 0)),
        (i18n("spot_matches", language), summary.get("spot_matched_symbols", 0)),
        (i18n("failed_steps", language), len(summary.get("failed_steps", []))),
    ]
    cards = "".join(
        f'<div class="metric"><span>{label}</span><strong>{esc(value)}</strong></div>'
        for label, value in metrics
    )
    return f'<div class="metrics">{cards}</div>'


def boundary_panel(summary: dict[str, Any], language: str) -> str:
    return (
        f'<p class="explain-lead">{boundary_summary(summary, language)}</p>'
        f'<div class="note-grid">{boundary_cards(summary, language)}</div>'
        f'<div class="limit-panel">{limit_panel(summary, language)}</div>'
        f"{technical_details(summary, language)}"
    )


def boundary_cards(summary: dict[str, Any], language: str) -> str:
    rows = [
        ("scoring_method", i18n(scoring_method_key(summary), language)),
        ("why_this_mode", mode_reason(summary, language)),
        ("prediction_status", i18n(prediction_status_key(summary), language)),
        ("data_scope", data_scope_value(summary, language)),
    ]
    return "".join(
        f'<div class="note-card"><span class="note-label">{i18n(label, language)}</span>'
        f"<strong>{value}</strong></div>"
        for label, value in rows
    )


def limit_panel(summary: dict[str, Any], language: str) -> str:
    key = limit_key(summary)
    return f'<strong>{i18n("limits", language)}</strong><p>{i18n(key, language)}</p>'


def technical_details(summary: dict[str, Any], language: str) -> str:
    metadata = summary.get("input_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    fields = [
        (i18n("requested_mode", language), summary.get("requested_mode")),
        (i18n("mode_decision", language), summary.get("mode_decision")),
        (i18n("consumes_prediction_columns", language), summary.get("consumes_prediction_columns")),
        (i18n("prediction_input_source", language), summary.get("prediction_input_source")),
        (
            i18n("requested_prediction_input_source", language),
            summary.get("requested_prediction_input_source"),
        ),
        (i18n("prediction_model_executed_by_runner", language), summary.get("prediction_model_executed_by_runner")),
        (i18n("source_scope", language), summary.get("source_scope")),
        (i18n("source_type", language), metadata.get("source_type", "unknown")),
        (i18n("real_market_data", language), metadata.get("real_market_data", "unknown")),
        (i18n("scenario", language), metadata.get("scenario", "")),
    ]
    rows = "".join(f"<dt>{label}</dt><dd>{esc(value)}</dd>" for label, value in fields)
    return (
        '<details class="technical-details">'
        f'<summary>{i18n("technical_details", language)}'
        f'<span>{i18n("technical_details_hint", language)}</span></summary>'
        f'<dl class="facts">{rows}</dl>'
        f"{machine_boundary(summary, language)}</details>"
    )


def machine_boundary(summary: dict[str, Any], language: str) -> str:
    if mode_unresolved(summary):
        boundary_html = boundary_summary(summary, language)
    else:
        boundary = str(summary.get("boundary", ""))
        boundary_html = esc(boundary)
    if not boundary_html:
        return ""
    return (
        f'<p class="boundary"><strong>{i18n("machine_boundary", language)}:</strong> '
        f"{boundary_html}</p>"
    )


def steps_table(steps: list[dict[str, Any]], language: str) -> str:
    rows = [
        {
            "step": step.get("step", ""),
            "returncode": step.get("returncode", ""),
            "allowed": ",".join(str(code) for code in step.get("allowed_returncodes", [])),
            "stderr": display_with_title(
                display=first_line(step.get("stderr", "")),
                title=str(step.get("stderr", "")),
            ),
        }
        for step in steps
    ]
    return table(rows, ("step", "returncode", "allowed", "stderr"), language)


def collapsible_details(label: str, content: str) -> str:
    return f'<details class="report-details"><summary>{label}</summary>{content}</details>'


def evidence_list(summary: dict[str, Any], language: str) -> str:
    output_dir = report_output_dir(summary)
    paths = evidence_paths(summary, output_dir, language)
    items = "".join(
        f"<li><span>{label}</span><code title=\"{esc(path['title'])}\">"
        f"{esc(path['display'])}</code></li>"
        for label, path in paths
        if path["display"]
    )
    return f'<ul class="evidence">{items}</ul>'


def evidence_paths(
    summary: dict[str, Any],
    output_dir: Path | None,
    language: str,
) -> list[tuple[str, dict[str, str]]]:
    paths = [
        (i18n("summary_json", language), evidence_path(summary_path(summary), output_dir)),
        (i18n("manifest_json", language), evidence_path(manifest_path(summary), output_dir)),
    ]
    optional = [
        ("candidates_output", "candidates_output_written", "candidates_csv"),
        ("diagnostics_output", "diagnostics_output_written", "diagnostics_csv"),
        ("prices_output", "prices_output_written", "prices"),
    ]
    for path_key, written_key, label_key in optional:
        if summary.get(written_key):
            paths.append((i18n(label_key, language), evidence_path(summary.get(path_key, ""), output_dir)))
    return paths


def section(title: str, content: str) -> str:
    return f'<section class="section"><h2>{title}</h2>{content}</section>'


def table(rows: list[dict[str, Any]], columns: tuple[str, ...], language: str) -> str:
    if not rows:
        return f'<p class="empty">{i18n("empty", language)}</p>'
    header = "".join(f"<th>{i18n(column, language)}</th>" for column in columns)
    body = "".join(table_row(row, columns, language) for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>'


def limited_table(
    rows: list[dict[str, Any]],
    columns: tuple[str, ...],
    language: str,
    *,
    truncated: bool,
    limit: int,
    csv_path: Any,
) -> str:
    content = table(rows, columns, language)
    if not truncated:
        return content
    return content + truncation_note(limit=limit, csv_path=csv_path, language=language)


def truncation_note(*, limit: int, csv_path: Any, language: str) -> str:
    path = evidence_path(csv_path, Path(str(csv_path)).parent if csv_path else None)
    en = f"Showing the first {limit} rows only. See the CSV for the full result."
    zh = f"仅展示前 {limit} 行，完整结果请查看 CSV。"
    if path["display"]:
        en = f"Showing the first {limit} rows only. Full result: {path['display']}."
        zh = f"仅展示前 {limit} 行，完整结果：{path['display']}。"
    return f'<p class="table-note">{bilingual(en, zh, language)}</p>'


def table_row(row: dict[str, Any], columns: tuple[str, ...], language: str) -> str:
    cells = "".join(table_cell(row.get(column, ""), column, language) for column in columns)
    return f"<tr>{cells}</tr>"


def status_class(status: str) -> str:
    return "ok" if status == "completed" else "failed"


def status_label_key(status: str) -> str:
    return f"status_{status}" if status in {"completed", "failed"} else "status_unknown"


def data_scope_value(summary: dict[str, Any], language: str) -> str:
    metadata = summary.get("input_metadata", {})
    if isinstance(metadata, dict) and is_synthetic_demo(metadata):
        scenario = str(metadata.get("scenario", "unknown"))
        en = f"Synthetic demo data ({scenario}); not real market data."
        zh = f"合成 demo 数据（{scenario}）；不是真实行情。"
        return bilingual(en, zh, language)
    source_scope = str(summary.get("source_scope", ""))
    if source_scope == "local_prices_input":
        return i18n("generic_scope_value", language)
    if source_scope == "unresolved":
        return i18n("unresolved_scope_value", language)
    en = f"Recorded source scope: {source_scope or 'unknown'}"
    zh = f"已记录数据来源范围：{source_scope or 'unknown'}"
    return bilingual(en, zh, language)
