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
    KEY_DISCLOSURE_COLUMNS,
    bilingual,
    display_with_title,
    esc,
    format_numeric,
    i18n,
    localized_phrase_html,
    missing_key_disclosure_value,
    raw_text,
    table_cell,
)
from a_share_selection_html_history import history_selection_fields
from a_share_selection_html_modes import (
    boundary_summary,
    candidate_count_key,
    limit_key,
    mode_unresolved,
    mode_reason,
    prediction_status_key,
    report_heading_key,
    report_status_key,
    scoring_method_key,
)
from a_share_selection_html_spot import spot_metadata_fields
from run_today_a_share_selection_input_metadata import is_synthetic_demo


DISPLAY_CANDIDATE_COLUMNS = (
    "rank",
    "symbol",
    "name",
    "date",
    "requested_as_of_date",
    "actual_data_date",
    "as_of_date_observed",
    "close",
    "spot_price",
    "spot_pct_chg",
    "prediction_source",
    "prediction_input_source",
    "prediction_model_quality_scope",
    "volume_unit_verification",
    "source_type",
    "real_market_data",
    "total_score",
    "cash_budget",
    "lot_size",
    "capital_model",
    "signal_close",
    "cash_slot",
    "quantity",
    "cash_reserved",
    "notional",
    "weight",
    "unallocated",
    "sizing_claim_boundary",
    "key_reasons",
    "risk_notes",
)
DISPLAY_DIAGNOSTIC_COLUMNS = (
    "symbol",
    "name",
    "requested_as_of_date",
    "actual_data_date",
    "as_of_date_observed",
    "close",
    "prediction_source",
    "prediction_input_source",
    "prediction_model_quality_scope",
    "volume_unit_verification",
    "source_type",
    "real_market_data",
    "total_score",
    "selection_status",
    "failure_reason",
)


def hero(summary: dict[str, Any], language: str) -> str:
    status = str(summary.get("status", "unknown"))
    heading_key = report_heading_key(summary, status)
    return (
        '<section class="hero executive-hero"><div class="hero-main">'
        f'<p class="eyebrow">{i18n("brand", language)}</p>'
        f"<h1>{i18n(heading_key, language, 'unknown_report')}</h1>"
        f"<p>{i18n('scoring_method', language)}: "
        f"<strong>{i18n(scoring_method_key(summary), language)}</strong>. "
        f"{i18n(candidate_count_key(summary), language)}: "
        f"<strong>{esc(summary.get('candidate_rows', 0))}</strong>.</p>"
        f"{signal_bars(summary)}</div>"
        '<div class="hero-actions">'
        f'<span class="status {esc(status_class(status))}">'
        f"{i18n(report_status_key(summary, status), language)}</span>"
        '<div class="language-toggle" aria-label="Language">'
        '<button type="button" data-set-lang="zh">中文</button>'
        '<button type="button" data-set-lang="en">EN</button>'
        "</div></div></section>"
    )


def signal_bars(summary: dict[str, Any]) -> str:
    try:
        count = int(summary.get("candidate_rows", 0))
    except (TypeError, ValueError):
        count = 0
    active = min(max(count, 0), 5)
    bars = "".join(
        f'<span class="{"active" if index < active else ""}"></span>' for index in range(5)
    )
    return f'<div class="signal-bars" aria-hidden="true">{bars}</div>'


def executive_summary(
    summary: dict[str, Any],
    language: str,
    candidate_rows: list[dict[str, Any]],
) -> str:
    count = int(summary.get("candidate_rows", 0) or 0)
    status = str(summary.get("status", "unknown"))
    lead = summary_lead(count, status, language)
    bullets = summary_bullets(summary, language)
    bullet_html = "".join(f"<li>{item}</li>" for item in bullets)
    source_boundary = summary_source_boundary(summary, language)
    return (
        '<section class="executive-summary">'
        f"{source_boundary}"
        f'<div><span>{bilingual("At a glance", "一眼结论", language)}</span>'
        f"<strong>{lead}</strong></div>"
        f'<div><span>{bilingual("How to read it", "怎么理解", language)}</span>'
        f"<ul>{bullet_html}</ul></div>"
        f"{top_candidate_hint(candidate_rows, language)}</section>"
    )


def summary_lead(count: int, status: str, language: str) -> str:
    if status != "completed":
        return bilingual(
            "This run did not finish candidate screening.",
            "本次没有完成候选筛选。",
            language,
        )
    if count == 0:
        return bilingual(
            "No candidate passed the configured gates.",
            "没有候选通过当前配置门禁。",
            language,
        )
    en = f"Found {count} candidate rows from the configured gates."
    zh = f"找到 {count} 条候选。"
    return bilingual(en, zh, language)


def summary_bullets(summary: dict[str, Any], language: str) -> list[str]:
    items = [
        bilingual(
            "This is a screening report, not a buy or sell instruction.",
            "这是筛选报告，不是买卖指令。",
            language,
        ),
        bilingual(
            "Read scores as gate results, not as return forecasts.",
            "分数代表门禁结果，不代表收益预测。",
            language,
        ),
    ]
    if str(summary.get("source_scope", "")) == "local_prices_input":
        items.append(
            bilingual(
                "The result depends on the local data file you provided.",
                "结果取决于你提供的本地数据文件。",
                language,
            )
        )
    return items


def summary_source_boundary(summary: dict[str, Any], language: str) -> str:
    metadata = summary.get("input_metadata", {})
    if not isinstance(metadata, dict) or not is_synthetic_demo(metadata):
        return ""
    value = metadata.get("real_market_data", "unknown")
    real_market_data = str(value).strip().lower()
    en_tail = "Not today's real market data or full-market scan."
    zh_tail = "不是今日真实行情或全市场扫描。"
    return (
        '<div class="summary-source-boundary">'
        f'<span>{bilingual("Data source boundary", "数据来源边界", language)}</span>'
        f"<strong>{data_scope_value(summary, language)}</strong>"
        f"<small>real_market_data={esc(real_market_data)}; "
        f"{bilingual(en_tail, zh_tail, language)}</small></div>"
    )


def top_candidate_hint(rows: list[dict[str, Any]], language: str) -> str:
    if not rows:
        return ""
    first = rows[0]
    name = raw_text(first.get("name")) or raw_text(first.get("symbol")) or "-"
    score = format_numeric(first.get("total_score", ""), 3, "")
    label = bilingual("Top row", "首位候选", language)
    score_label = bilingual("score", "分数", language)
    return (
        f'<div class="summary-highlight"><span>{label}</span>'
        f"<strong>{esc(name)}</strong><small>{score_label} {esc(score or '-')}</small></div>"
    )


def metric_grid(summary: dict[str, Any], language: str) -> str:
    metrics = [
        (i18n("prices_rows", language), summary.get("prices_rows", 0)),
        (i18n("candidate_rows", language), summary.get("candidate_rows", 0)),
        (i18n("diagnostic_rows", language), summary.get("diagnostic_rows", 0)),
        (i18n("spot_rows", language), summary.get("spot_rows", 0)),
        (i18n("spot_matches", language), summary.get("spot_matched_symbols", 0)),
        (i18n("history_symbols", language), summary.get("history_symbol_count", 0)),
        (i18n("failed_steps", language), len(summary.get("failed_steps", []))),
    ]
    cards = "".join(
        f'<div class="metric"><span>{label}</span><strong>{esc(value)}</strong></div>'
        for label, value in metrics
    )
    return f'<div class="metrics">{cards}</div>'


def report_overview(
    summary: dict[str, Any],
    language: str,
    candidate_rows: list[dict[str, Any]],
) -> str:
    return executive_summary(summary, language, candidate_rows) + metric_grid(summary, language)


def boundary_panel(
    summary: dict[str, Any],
    language: str,
    candidate_rows: list[dict[str, Any]] | None = None,
) -> str:
    return (
        f'<p class="explain-lead">{boundary_summary(summary, language)}</p>'
        f'<div class="note-grid">{boundary_cards(summary, language)}</div>'
        f'<div class="limit-panel">{limit_panel(summary, language)}</div>'
        f"{disclosure_alerts(summary, language, candidate_rows or [])}"
        f"{technical_details(summary, language)}"
    )


def candidate_cards(rows: list[dict[str, Any]], language: str) -> str:
    if not rows:
        return ""
    cards = "".join(candidate_card(row, language) for row in rows)
    return f'<div class="candidate-cards">{cards}</div>'


def candidate_card(row: dict[str, Any], language: str) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = raw_text(row.get("name")) or symbol
    rank = raw_text(row.get("rank")) or "-"
    score = format_numeric(row.get("total_score", ""), 3, "")
    close = format_numeric(row.get("close", ""), 4, "")
    quantity = format_numeric(row.get("quantity", ""), 0, "")
    cash_reserved = format_numeric(row.get("cash_reserved", ""), 2, "")
    reasons = localized_phrase_html(raw_text(row.get("key_reasons")), language)
    risks = localized_phrase_html(raw_text(row.get("risk_notes")), language)
    return (
        '<article class="candidate-card">'
        f'<div class="candidate-rank">#{esc(rank)}</div>'
        f'<div class="candidate-main"><strong>{esc(name)}</strong><span>{esc(symbol)}</span></div>'
        f'<div class="candidate-score"><span>{bilingual("Score", "评分", language)}</span>'
        f"<strong>{esc(score or '-')}</strong></div>"
        '<div class="candidate-facts">'
        f"<span>{bilingual('Close', '收盘价', language)} <strong>{esc(close or '-')}</strong></span>"
        f"<span>{bilingual('Quantity', '数量', language)} <strong>{esc(quantity or '-')}</strong></span>"
        f"<span>{bilingual('Cash reserved', '预留现金', language)} "
        f"<strong>{esc(cash_reserved or '-')}</strong></span></div>"
        '<div class="candidate-copy">'
        f"<p><b>{bilingual('Why it passed', '为什么入选', language)}</b>{reasons}</p>"
        f"<p><b>{bilingual('Risk notes', '风险提示', language)}</b>{risks}</p>"
        f"<small>{bilingual('Not a broker order', '不是券商订单', language)}</small>"
        "</div></article>"
    )


def candidates_panel(
    rows: list[dict[str, Any]],
    columns: tuple[str, ...],
    language: str,
    *,
    truncated: bool,
    limit: int,
    csv_path: Any,
    empty_key: str = "empty",
    empty_html: str = "",
) -> str:
    cards = candidate_cards(rows, language)
    table_html = limited_table(
        rows,
        columns,
        language,
        truncated=truncated,
        limit=limit,
        csv_path=csv_path,
        empty_key=empty_key,
        empty_html=empty_html,
    )
    if not cards:
        return table_html
    title = bilingual("Full detail table", "完整明细表", language)
    hint = bilingual(
        "Cards are for quick reading. The table keeps every auditable field.",
        "卡片方便快速阅读，表格保留可审计字段。",
        language,
    )
    return f"{cards}<div class=\"detail-table-heading\"><strong>{title}</strong><p>{hint}</p></div>{table_html}"


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


def disclosure_alerts(
    summary: dict[str, Any],
    language: str,
    candidate_rows: list[dict[str, Any]] | None = None,
) -> str:
    alerts = (
        advice_alerts(summary, language)
        + input_metadata_alerts(summary, language)
        + input_csv_provenance_alerts(summary, language)
        + sizing_alerts(candidate_rows or [], language)
        + spot_alerts(summary, language)
        + history_alerts(summary, language)
    )
    if not alerts:
        return ""
    items = "".join(f"<li>{alert}</li>" for alert in alerts)
    return f'<ul class="disclosure-alerts">{items}</ul>'


def advice_alerts(summary: dict[str, Any], language: str) -> list[str]:
    boundary = str(summary.get("advice_boundary", ""))
    if boundary != "not_investment_advice_not_trade_instruction_not_real_fill_not_return_proof":
        return []
    en = (
        "Not investment advice; not a trade instruction; "
        "not proof of real fills or returns."
    )
    zh = "不是投资建议；不是交易指令；不是真实成交或收益证明。"
    return [bilingual(en, zh, language)]


def input_metadata_alerts(summary: dict[str, Any], language: str) -> list[str]:
    metadata = summary.get("input_metadata", {})
    if not isinstance(metadata, dict) or is_synthetic_demo(metadata):
        return []
    alerts = []
    if local_real_market_unknown(summary, metadata):
        en = "Real market data is unknown; the local file is not proof of real A-share market data."
        zh = "真实行情未知；本地文件不能证明是真实 A 股行情。"
        alerts.append(bilingual(en, zh, language))
    if market_label_only(metadata):
        en = "The market is a label only; not exchange or calendar proof."
        zh = "market 只是输出标签；不是交易所或交易日历证明。"
        alerts.append(bilingual(en, zh, language))
    return alerts


def local_real_market_unknown(summary: dict[str, Any], metadata: dict[str, Any]) -> bool:
    if str(summary.get("source_scope", "")) != "local_prices_input":
        return False
    value = metadata.get("real_market_data", "unknown")
    return str(value).strip().lower() in {"", "none", "unknown"}


def market_label_only(metadata: dict[str, Any]) -> bool:
    boundary = str(metadata.get("source_claim_boundary", ""))
    if boundary == "market_label_not_source_exchange_or_calendar_proof":
        return True
    value = metadata.get("market_label_only", False)
    return value is True or str(value).strip().lower() == "true"


def input_csv_provenance_alerts(summary: dict[str, Any], language: str) -> list[str]:
    provenance = summary.get("input_csv_provenance", {})
    if not isinstance(provenance, dict) or not provenance:
        return []
    real_market_data = str(provenance.get("real_market_data", "unknown")).strip().lower()
    boundary = str(provenance.get("source_claim_boundary", "")).strip()
    if real_market_data != "false" and not boundary:
        return []
    en = (
        f"CSV embedded provenance says real_market_data={real_market_data}; "
        f"source_claim_boundary={boundary or 'unknown'}."
    )
    zh = (
        f"CSV 内嵌 provenance 声明 real_market_data={real_market_data}；"
        f"source_claim_boundary={boundary or 'unknown'}。"
    )
    return [bilingual(en, zh, language)]


def sizing_alerts(rows: list[dict[str, Any]], language: str) -> list[str]:
    for row in rows:
        if str(row.get("sizing_claim_boundary", "")) == "local_sizing_not_broker_order":
            en = "Local sizing only; not a broker order, real fill, or cash capacity proof."
            zh = "仅本地资金分配；不是券商订单、真实成交或现金容量证明。"
            return [bilingual(en, zh, language)]
    return []


def spot_alerts(summary: dict[str, Any], language: str) -> list[str]:
    metadata = summary.get("spot_metadata", {})
    if not isinstance(metadata, dict):
        return []
    partial = metadata.get("partial_result") is True
    coverage = str(metadata.get("coverage_claim", ""))
    if not partial and coverage != "partial_not_full_market":
        return []
    en = (
        "Partial realtime snapshot; do not describe this as a completed live "
        "full-market scan."
    )
    zh = "部分实时快照；不能写成实时全市场扫描完成。"
    return [bilingual(en, zh, language)]


def history_alerts(summary: dict[str, Any], language: str) -> list[str]:
    selection = summary.get("history_selection", {})
    if not isinstance(selection, dict):
        return []
    requested = str(selection.get("requested_end_date", ""))
    actual = str(selection.get("history_metadata_actual_date_max", ""))
    all_reached = selection.get("history_metadata_all_symbols_reached_end_date")
    reached_count = selection.get("history_metadata_symbols_reached_end_date_count")
    selected_count = selection.get("selected_symbol_count")
    has_rows = selection.get("history_metadata_end_date_has_rows")
    if not requested or not actual:
        return []
    if all_reached is True:
        return []
    if all_reached is not False and has_rows is not False:
        return []
    reached = reached_count if isinstance(reached_count, int) else "unknown"
    total = selected_count if isinstance(selected_count, int) else "unknown"
    en = (
        f"Requested {requested}, actual latest {actual}; "
        f"{reached}/{total} symbols reached the requested end date."
    )
    zh = (
        f"请求截止日 {requested}，历史实际最新日期 {actual}；"
        f"{reached}/{total} 个标的到达请求截止日。"
    )
    return [bilingual(en, zh, language)]


def technical_details(summary: dict[str, Any], language: str) -> str:
    metadata = summary.get("input_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    fields = [
        (i18n("requested_mode", language), summary.get("requested_mode")),
        (i18n("mode_decision", language), summary.get("mode_decision")),
        ("run_error_type", summary.get("run_error_type", "")),
        ("run_error", summary.get("run_error", "")),
        (i18n("consumes_prediction_columns", language), summary.get("consumes_prediction_columns")),
        (i18n("prediction_input_source", language), summary.get("prediction_input_source")),
        (
            i18n("requested_prediction_input_source", language),
            summary.get("requested_prediction_input_source"),
        ),
        (i18n("prediction_model_executed_by_runner", language), summary.get("prediction_model_executed_by_runner")),
        ("prediction_claim_boundary", summary.get("prediction_claim_boundary", "")),
        (i18n("source_scope", language), summary.get("source_scope")),
        (i18n("source_type", language), metadata.get("source_type", "unknown")),
        ("source", metadata.get("source", "")),
        ("market", metadata.get("market", "")),
        ("market_label_only", metadata.get("market_label_only", "")),
        ("source_claim_boundary", metadata.get("source_claim_boundary", "")),
        ("adjustment", metadata.get("adjustment", "")),
        (i18n("real_market_data", language), metadata.get("real_market_data", "unknown")),
        (i18n("scenario", language), metadata.get("scenario", "")),
        ("advice_boundary", summary.get("advice_boundary", "")),
        ("recommendation_boundary", summary.get("recommendation_boundary", "")),
    ]
    fields.extend(input_csv_provenance_fields(summary))
    fields.extend(spot_metadata_fields(summary))
    fields.extend(history_selection_fields(summary, language))
    fields.extend(score_detail_fields(summary))
    rows = "".join(f"<dt>{label}</dt><dd>{esc(value)}</dd>" for label, value in fields)
    return (
        '<details class="technical-details">'
        f'<summary>{i18n("technical_details", language)}'
        f'<span>{i18n("technical_details_hint", language)}</span></summary>'
        f'<dl class="facts">{rows}</dl>'
        f"{machine_boundary(summary, language)}</details>"
    )


def input_csv_provenance_fields(summary: dict[str, Any]) -> list[tuple[str, Any]]:
    provenance = summary.get("input_csv_provenance", {})
    if not isinstance(provenance, dict) or not provenance:
        return []
    keys = (
        "source_type",
        "source_scope",
        "real_market_data",
        "source_claim_boundary",
    )
    return [(f"input_csv_{key}", provenance.get(key, "")) for key in keys]


def machine_boundary(summary: dict[str, Any], language: str) -> str:
    if mode_unresolved(summary):
        boundary_html = boundary_summary(summary, language)
    else:
        boundary = str(summary.get("boundary", ""))
        boundary_html = esc(boundary)
    advice = str(summary.get("advice_boundary", ""))
    if advice:
        suffix = f" advice_boundary={esc(advice)}"
        boundary_html = f"{boundary_html}{suffix}" if boundary_html else suffix.strip()
    if not boundary_html:
        return ""
    return (
        f'<p class="boundary"><strong>{i18n("machine_boundary", language)}:</strong> '
        f"{boundary_html}</p>"
    )


def score_detail_fields(summary: dict[str, Any]) -> list[tuple[str, Any]]:
    score = summary.get("score", {})
    if not isinstance(score, dict):
        return []
    fields = []
    for key in (
        "effective_empty_result",
        "empty_result_reason",
        "threshold_failures",
        "failed_symbol_examples",
        "insufficient_history_symbol_examples",
    ):
        if key in score:
            fields.append((key, score.get(key)))
    return fields


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
    return table(
        rows,
        ("step", "returncode", "allowed", "stderr"),
        language,
        empty_key="empty_steps",
    )


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
        ("spot_output", "spot_output_written", "spot_csv"),
        ("spot_metadata_output", "spot_metadata_output_written", "spot_metadata_json"),
        ("selected_symbols_output", "selected_symbols_output_written", "selected_symbols_json"),
        ("history_metadata_output", "history_metadata_output_written", "history_metadata_json"),
    ]
    for path_key, written_key, label_key in optional:
        if summary.get(written_key):
            paths.append((i18n(label_key, language), evidence_path(summary.get(path_key, ""), output_dir)))
    return paths


def section(title: str, content: str) -> str:
    return f'<section class="section"><h2>{title}</h2>{content}</section>'


def table(
    rows: list[dict[str, Any]],
    columns: tuple[str, ...],
    language: str,
    *,
    empty_key: str = "empty",
) -> str:
    if not rows:
        return f'<p class="empty">{i18n(empty_key, language)}</p>'
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
    empty_key: str = "empty",
    empty_html: str = "",
) -> str:
    if not rows and empty_html:
        content = empty_html
    else:
        content = table(rows, columns, language, empty_key=empty_key)
    if not truncated:
        return content
    return content + truncation_note(limit=limit, csv_path=csv_path, language=language)


def zero_candidates_message(summary: dict[str, Any], language: str) -> str:
    score = summary.get("score", {})
    if not isinstance(score, dict) or score.get("effective_empty_result") is not True:
        return ""
    if str(summary.get("status", "")) != "completed":
        return ""
    if summary.get("candidates_output_written") is not True:
        return ""
    reason = str(score.get("empty_result_reason", "unknown"))
    en = (
        "Completed run with zero candidates; effective_empty_result=true "
        f"empty_result_reason={reason}."
    )
    zh = f"本次成功运行但没有候选；effective_empty_result=true empty_result_reason={reason}。"
    return f'<p class="empty">{bilingual(en, zh, language)}</p>'


def empty_key_for(summary: dict[str, Any]) -> str:
    return "no_table_rows" if str(summary.get("status", "")) == "completed" else "empty"


def truncation_note(*, limit: int, csv_path: Any, language: str) -> str:
    path = evidence_path(csv_path, Path(str(csv_path)).parent if csv_path else None)
    en = f"Showing the first {limit} rows only. See the CSV for the full result."
    zh = f"仅展示前 {limit} 行，完整结果请查看 CSV。"
    if path["display"]:
        en = f"Showing the first {limit} rows only. Full result: {path['display']}."
        zh = f"仅展示前 {limit} 行，完整结果：{path['display']}。"
    return f'<p class="table-note">{bilingual(en, zh, language)}</p>'


def table_row(row: dict[str, Any], columns: tuple[str, ...], language: str) -> str:
    cells = "".join(table_cell(table_value(row, column), column, language) for column in columns)
    return f"<tr>{cells}</tr>"


def table_value(row: dict[str, Any], column: str) -> Any:
    if column in row:
        return row[column]
    if column in KEY_DISCLOSURE_COLUMNS:
        return missing_key_disclosure_value(column)
    return ""


def status_class(status: str) -> str:
    return "ok" if status == "completed" else "failed"


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
