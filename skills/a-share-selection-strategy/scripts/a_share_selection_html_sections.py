"""HTML section builders for the local A-share selection report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from a_share_selection_candidate_fields import candidate_field_value_present
from a_share_selection_html_candidate_master import (
    candidate_master_detail,
    candidate_open_banner,
)
from a_share_selection_html_candidate_helpers import candidate_listing_board, plain_bilingual
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
    attr_text,
    display_with_title,
    esc,
    format_numeric,
    i18n,
    i18n_attr,
    localized_phrase_html,
    missing_key_disclosure_value,
    phrase_translation,
    raw_text,
    table_cell,
)
from a_share_selection_html_i18n import localized_text
from a_share_selection_html_history import history_selection_fields
from a_share_selection_html_modes import (
    boundary_summary,
    generic_mode_not_ready,
    generic_scoring_failed_at_strict_gate,
    limit_key,
    mode_unresolved,
    mode_reason,
    prediction_columns_missing,
    prediction_mode_not_ready,
    prediction_scoring_failed_after_consumption,
    prediction_status_key,
    report_status_key,
    scoring_method_key,
)
from a_share_selection_html_spot import spot_metadata_fields
from run_today_a_share_selection_input_metadata import (
    history_selection_partial_result,
    is_synthetic_demo,
    local_input_partial_result,
)

STRATEGY_MATCH_HIGH = 0.75
STRATEGY_MATCH_MEDIUM = 0.55
HK_MARKET_LABELS = {
    "hk",
    "hkex",
    "hkg",
    "hong kong",
    "hong-kong",
    "h-share",
    "h share",
    "港股",
    "香港",
}
A_SHARE_MARKET_LABELS = {"a-share", "a share", "a股", "a股市场"}


DISPLAY_CANDIDATE_COLUMNS = (
    "rank",
    "symbol",
    "name",
    "listing_board",
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
MASTER_DETAIL_PREVIEW_LIMIT = 5


def hero_copy(title: str, badges: str, note: str) -> str:
    return (
        '<div class="hero-copy">'
        f"<h1>{title}</h1>"
        f'<div class="hero-badges">{badges}</div>'
        f'<p class="hero-note">{note}</p>'
        "</div>"
    )


def hero_badges(summary: dict[str, Any], language: str) -> list[tuple[str, str]]:
    prediction = bool(summary.get("prediction_mode"))
    return [
        (bilingual("Static HTML", "纯静态 HTML", language), "neutral"),
        (hero_market_label(summary, language), "neutral"),
        (bilingual("Public or user-provided data", "公开或用户提供数据", language), "blue"),
        (bilingual("Not investment advice", "非投资建议", language), "neutral"),
        (
            bilingual("Prediction model used", "已使用预测模型", language)
            if prediction
            else bilingual("No prediction model", "无预测模型", language),
            "neutral",
        ),
        (bilingual("No real fill proof", "无真实成交证明", language), "neutral"),
    ]


def hero_title(summary: dict[str, Any], language: str) -> str:
    market_kind, _ = hero_market_identity(summary)
    if market_kind == "a-share":
        return bilingual("A-share Strategy Selection Report", "A 股策略选股报告", language)
    return bilingual("Strategy Selection Report", "策略选股报告", language)


def hero_market_label(summary: dict[str, Any], language: str) -> str:
    market_kind, market = hero_market_identity(summary)
    if market_kind == "hk":
        return bilingual("HK", "港股", language)
    if market_kind == "a-share":
        return bilingual("A-share", "A 股", language)
    return esc(market)


def hero_market_identity(summary: dict[str, Any]) -> tuple[str, str]:
    input_metadata = summary.get("input_metadata", {})
    market = ""
    if isinstance(input_metadata, dict):
        market = str(input_metadata.get("market", "") or "").strip()
    if market:
        normalized = market.lower().replace("_", "-")
        if normalized in HK_MARKET_LABELS:
            return "hk", market
        if normalized in A_SHARE_MARKET_LABELS:
            return "a-share", market
        return "custom", market
    if hero_market_from_source_scope(str(summary.get("source_scope", "") or "")) == "HK":
        return "hk", "HK"
    return "a-share", "A-share"


def hero_market_from_source_scope(source_scope: str) -> str:
    scopes = {part.strip().lower() for part in source_scope.split("+") if part.strip()}
    if scopes & {"akshare_hk_daily_history_fetch"}:
        return "HK"
    return "HK" if any("_hk_" in scope or scope.startswith("hk_") for scope in scopes) else ""


def hero_badge(label: str, kind: str) -> str:
    return f'<span class="hero-badge {esc(kind)}">{label}</span>'


def hero_fact_card(summary: dict[str, Any], language: str) -> str:
    rows = [
        (
            bilingual("Report subject", "报告主题", language),
            hero_report_subject(summary, language),
        ),
        (
            bilingual("Generated at", "生成时间", language),
            report_generated_at(summary, language),
        ),
        (
            bilingual("Data source", "数据来源", language),
            data_scope_value(summary, language),
        ),
        (
            bilingual("File note", "文件说明", language),
            bilingual("Single static HTML, local browser only", "单个静态 HTML 文件，纯前端实现", language),
        ),
        (
            bilingual("Execution path", "执行路径", language),
            str(summary.get("execution_path", "unresolved")),
        ),
        (
            bilingual("Coverage class", "覆盖等级", language),
            str(summary.get("coverage_class", "unknown")),
        ),
        (
            bilingual("Full-market claim", "全市场声明", language),
            full_market_claim_value(summary, language),
        ),
    ]
    items = "".join(f"<div><span>{label}</span><strong>{value}</strong></div>" for label, value in rows)
    return f'<aside class="hero-fact-card">{items}</aside>'


def hero_report_subject(summary: dict[str, Any], language: str) -> str:
    market_kind, market = hero_market_identity(summary)
    if market_kind == "hk":
        return bilingual("HK rule-based screening watchlist", "港股规则筛选观察", language)
    if market_kind == "a-share":
        return bilingual("A-share rule-based screening watchlist", "A 股规则筛选观察", language)
    en = f"{market} rule-based screening watchlist"
    zh = f"{market} 规则筛选观察"
    return bilingual(en, zh, language)


def hero_machine_note(summary: dict[str, Any], language: str) -> str:
    execution_path = str(summary.get("execution_path", "unresolved"))
    coverage_class = str(summary.get("coverage_class", "unknown"))
    claim_boundary = str(summary.get("full_market_claim_boundary", "not_evaluated"))
    allowed = bool(summary.get("full_market_claim_allowed", False))
    en = (
        "Machine fields explain how the run was executed: "
        f"execution_path={execution_path} describes how the pool was built and scored; "
        f"coverage_class={coverage_class} describes how broad the pool is; "
        f"full_market_claim_allowed={'allowed' if allowed else 'not allowed'}, "
        f"full_market_claim_boundary={claim_boundary} explains whether this report may be described as a full-market scan."
    )
    zh = (
        "机器字段说明："
        f"execution_path={execution_path} 说明这轮如何构建和评分样本池；"
        f"coverage_class={coverage_class} 说明样本池覆盖到什么广度；"
        f"full_market_claim_allowed={'允许' if allowed else '不允许'}，"
        f"full_market_claim_boundary={claim_boundary} 说明这份报告能否按全市场闭环来表述。"
    )
    return f'<p class="hero-machine-note">{bilingual(en, zh, language)}</p>'


def full_market_claim_value(summary: dict[str, Any], language: str) -> str:
    allowed = bool(summary.get("full_market_claim_allowed", False))
    boundary = str(summary.get("full_market_claim_boundary", "not_evaluated"))
    en = f"{'allowed' if allowed else 'not allowed'} / {boundary}"
    zh = f"{'允许' if allowed else '不允许'} / {boundary}"
    return bilingual(en, zh, language)


def report_generated_at(summary: dict[str, Any], language: str) -> str:
    candidates_path = raw_text(summary.get("candidates_output"))
    if candidates_path:
        path = Path(candidates_path)
        try:
            value = path_mtime(path)
        except OSError:
            pass
        else:
            from datetime import datetime

            dt = datetime.fromtimestamp(value)
            return dt.strftime("%Y-%m-%d %H:%M")
    return bilingual("Generated when this report was written", "随本报告生成时间写入", language)


def path_mtime(path: Path) -> float:
    return path.stat().st_mtime


def hero_subtitle(summary: dict[str, Any], language: str) -> str:
    status = str(summary.get("status", "unknown"))
    count = candidate_count(summary)
    if status != "completed":
        return bilingual(
            "The AI agent did not produce a usable watchlist in this run.",
            "AI Agent 本次没有生成可用的观察清单。",
            language,
        )
    if count == 0:
        return bilingual(
            "The AI agent checked the current data and found no watchlist item.",
            "AI Agent 已检查当前数据，但没有找到观察对象。",
            language,
        )
    en = f"The AI agent produced {count} watchlist item for this report."
    if count != 1:
        en = f"The AI agent produced {count} watchlist items for this report."
    zh = f"AI Agent 已生成 {count} 个观察对象。"
    return bilingual(en, zh, language)


def candidate_count(summary: dict[str, Any]) -> int:
    try:
        return int(summary.get("candidate_rows", 0) or 0)
    except (TypeError, ValueError):
        return 0


def input_stock_count(summary: dict[str, Any]) -> int:
    score = summary.get("score", {})
    score_symbols = score.get("input_symbols", 0) if isinstance(score, dict) else 0
    for value in (
        summary.get("history_symbol_count", 0),
        score_symbols,
        summary.get("diagnostic_rows", 0),
    ):
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            continue
        if count > 0:
            return count
    return 0


def executive_summary(
    summary: dict[str, Any],
    language: str,
    candidate_rows: list[dict[str, Any]],
) -> str:
    count = candidate_count(summary)
    status = str(summary.get("status", "unknown"))
    lead = summary_lead(count, status, language)
    bullets = summary_bullets(summary, language)
    bullet_html = "".join(f"<li>{item}</li>" for item in bullets)
    source_boundary = summary_source_boundary(summary, language)
    return (
        '<section class="executive-summary">'
        f"{source_boundary}"
        f'<div><span>{bilingual("Agent result", "AI Agent 结论", language)}</span>'
        f"<strong>{lead}</strong></div>"
        f'<div><span>{bilingual("How to use it", "该怎么用", language)}</span>'
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
            "No watchlist item matched this run.",
            "本次没有筛出观察对象。",
            language,
        )
    en = f"Found {count} watchlist item in this report."
    if count != 1:
        en = f"Found {count} watchlist items in this report."
    zh = f"找到 {count} 个观察对象。"
    return bilingual(en, zh, language)


def summary_bullets(summary: dict[str, Any], language: str) -> list[str]:
    status = str(summary.get("status", "unknown"))
    count = candidate_count(summary)
    items = [
        bilingual(
            "Use this as a report watchlist, not as a buy or sell instruction.",
            "把它当作报告中的观察清单，不要当作买卖指令。",
            language,
        ),
        bilingual(
            "A match only means it fits the current strategy rules; it is not a return forecast.",
            "匹配只表示符合当前策略规则，不代表收益预测。",
            language,
        ),
    ]
    if status != "completed":
        items.extend(
            [
                bilingual(
                    "It did not finish the workflow, so this report has no usable watchlist.",
                    "本次流程没有跑完，所以没有可用观察清单。",
                    language,
                ),
                bilingual(
                    "Do not reuse older watchlists as this result.",
                    "不要把旧观察清单当成本次结果。",
                    language,
                ),
                bilingual(
                    "Check the failure message before doing anything with the result.",
                    "先看失败说明，不要直接使用本次结果。",
                    language,
                ),
            ]
        )
        return items
    if count == 0:
        items.extend(
            [
                bilingual(
                    "No stock matched the current strategy rules.",
                    "没有股票符合当前策略规则。",
                    language,
                ),
                bilingual(
                    "Confirm whether the data source and strategy scope are what you intended.",
                    "先确认数据来源和策略范围是不是你想要的。",
                    language,
                ),
            ]
        )
    if summary_uses_local_prices_input(summary):
        items.append(
            bilingual(
                "The result depends on the data file or data source used by this run.",
                "结果取决于本次使用的数据文件或数据源。",
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
    en_tail = "Use it only to inspect the workflow and presentation, not as a live market result."
    zh_tail = "只能用来查看流程和展示效果，不能当作实盘结果。"
    return (
        '<div class="summary-source-boundary">'
        f'<span>{bilingual("Data used", "本次使用的数据", language)}</span>'
        f"<strong>{data_scope_value(summary, language)}</strong>"
        f"<small>{bilingual(en_tail, zh_tail, language)}</small></div>"
    )


def top_candidate_hint(rows: list[dict[str, Any]], language: str) -> str:
    if not rows:
        return ""
    first = rows[0]
    name = raw_text(first.get("name")) or raw_text(first.get("symbol")) or "-"
    score = format_numeric(first.get("total_score", ""), 3, "")
    label = bilingual("Top candidate", "首个候选", language)
    match_label = bilingual("priority check", "优先查看", language)
    return (
        f'<div class="summary-highlight"><span>{label}</span>'
        f"<strong>{esc(name)}</strong>"
        f"<small>{match_label} {strategy_match_label(score, language)}</small></div>"
    )


def watchlist_title(summary: dict[str, Any], language: str) -> str:
    metadata = summary.get("input_metadata", {})
    demo = isinstance(metadata, dict) and is_synthetic_demo(metadata)
    if demo:
        return bilingual("Demo Watchlist", "Demo 观察清单", language)
    return bilingual("Watchlist", "观察清单", language)


def user_result_title(language: str) -> str:
    return bilingual("AI Agent Result", "AI Agent 结论", language)


def confirmation_title(language: str) -> str:
    return bilingual("Check Before Use", "使用前先确认", language)


def appendix_title(language: str) -> str:
    return bilingual("Report Appendix", "报告附录", language)


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
    all_candidate_rows: list[dict[str, Any]],
    columns: tuple[str, ...],
    *,
    truncated: bool,
    limit: int,
    csv_path: Any,
    empty_key: str,
    empty_html: str,
) -> str:
    badges = "".join(hero_badge(label, kind) for label, kind in hero_badges(summary, language))
    title = hero_title(summary, language)
    note = bilingual(
        "Data is written into this HTML. Search, filters, sorting, and details run locally in the browser.",
        "数据随 HTML 生成，搜索筛选排序均在本地浏览器完成。",
        language,
    )
    preview_html = candidate_preview_pane(
        candidate_rows,
        columns,
        language,
        truncated=truncated,
        limit=limit,
        csv_path=csv_path,
        empty_key=empty_key,
        empty_html=empty_html,
    )
    open_html = candidate_open_banner(all_candidate_rows, csv_path, language)
    open_slot = f'<div class="candidate-open-slot">{open_html}</div>' if open_html else ""
    return (
        '<div class="overview-shell">'
        '<div class="overview-lead">'
        '<div class="overview-title">'
        f"{hero_copy(title, badges, note)}"
        "</div>"
        '<div class="overview-metrics">'
        f"{pipeline_metric_cards(summary, language)}"
        "</div>"
        "</div>"
        '<div class="overview-facts">'
        f"{hero_fact_card(summary, language)}"
        f"{hero_machine_note(summary, language)}"
        "</div>"
        '<div class="overview-flow">'
        f"{selection_flow_card(summary, language)}"
        "</div>"
        '<div class="overview-preview">'
        f"{preview_html}"
        "</div>"
        '<div class="overview-open">'
        f"{open_slot}"
        "</div></div>"
    )


def candidate_preview_pane(
    rows: list[dict[str, Any]],
    columns: tuple[str, ...],
    language: str,
    *,
    truncated: bool,
    limit: int,
    csv_path: Any,
    empty_key: str,
    empty_html: str,
) -> str:
    cards = candidate_cards(rows, language)
    if cards:
        return f'<div class="watchlist-preview-pane">{cards}</div>'
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
    return f'<div class="watchlist-preview-pane">{table_html}</div>'


def pipeline_metric_cards(summary: dict[str, Any], language: str) -> str:
    candidate_total = candidate_count(summary)
    input_total = input_stock_count(summary)
    diagnostics_total = summary.get("diagnostic_rows", 0)
    high_total = high_priority_count(summary)
    cards = [
        (
            bilingual("Sample stocks", "样本股票", language),
            input_total,
            bilingual("unique symbols in scope", "本次股票池", language),
            "input",
            metric_insight(summary, "input", language),
        ),
        (
            bilingual("Passed first checks", "通过初筛", language),
            diagnostics_total,
            bilingual("basic rule checks", "通过基础条件检查", language),
            "passed",
            metric_insight(summary, "passed", language),
        ),
        (
            bilingual("View details", "查看详情", language),
            candidate_total,
            bilingual("view details before action", "进入观察名单", language),
            "watch",
            metric_insight(summary, "watch", language),
        ),
        (
            bilingual("Needs risk attention", "需重点关注", language),
            high_total,
            bilingual("read risk note first", "先看风险提示", language),
            "risk",
            metric_insight(summary, "risk", language),
        ),
    ]
    html = "".join(
        pipeline_metric_card(label, value, note, kind, insight)
        for label, value, note, kind, insight in cards
    )
    label_attr = i18n_attr("aria-label", "Pipeline counts", "流程指标", language)
    return f'<section class="pipeline-metrics" {label_attr}>{html}</section>'


def pipeline_metric_card(label: str, value: Any, note: str, kind: str, insight: dict[str, Any]) -> str:
    icon = {
        "input": "circle",
        "passed": "funnel",
        "watch": "eye",
        "risk": "shield",
    }.get(kind, "circle")
    return (
        f'<button type="button" class="pipeline-card {esc(kind)}" '
        f'aria-haspopup="dialog" {insight_attrs(kind, insight)}>'
        f'<span class="pipeline-icon {esc(icon)}" aria-hidden="true"></span>'
        f'<div class="pipeline-copy"><span>{label}</span><strong>{esc(value)}</strong><small>{note}</small></div></button>'
    )


def selection_flow_card(summary: dict[str, Any], language: str) -> str:
    title = bilingual("Selection flow", "选股流程", language)
    subtitle = bilingual("Clickable details", "可点查看细节", language)
    return f'<section class="selection-flow-card"><h2>{title}<span>{subtitle}</span></h2>{selection_flow(summary, language)}</section>'


def selection_flow(summary: dict[str, Any], language: str) -> str:
    candidate_total = candidate_count(summary)
    input_total = input_stock_count(summary)
    diagnostics_total = summary.get("diagnostic_rows", 0)
    high_total = high_priority_count(summary)
    steps = [
        (
            bilingual("Sample stocks", "样本股票", language),
            input_total,
            bilingual("read price history", "读取历史行情", language),
            "input",
            flow_insight(summary, "input", language),
        ),
        (
            bilingual("First checks", "基础检查", language),
            diagnostics_total,
            bilingual("remove obvious mismatches", "排除明显不符合项", language),
            "passed",
            flow_insight(summary, "passed", language),
        ),
        (
            bilingual("Watchlist", "观察名单", language),
            candidate_total,
            bilingual("needs a closer look", "需要进一步查看", language),
            "watch",
            flow_insight(summary, "watch", language),
        ),
        (
            bilingual("Risk note", "风险提示", language),
            high_total,
            bilingual("read warnings first", "先看风险提示", language),
            "risk",
            flow_insight(summary, "risk", language),
        ),
    ]
    cards = "".join(flow_steps_with_arrows(steps))
    label_attr = i18n_attr("aria-label", "Selection flow", "选股流程", language)
    return f'<section class="selection-flow" {label_attr}>{cards}</section>'


def flow_steps_with_arrows(steps: list[tuple[str, Any, str, str, dict[str, Any]]]) -> str:
    parts = []
    for index, (label, value, note, kind, insight) in enumerate(steps):
        parts.append(flow_step(label, value, note, kind, insight))
        if index < len(steps) - 1:
            parts.append('<span class="flow-arrow" aria-hidden="true"></span>')
    return "".join(parts)


def high_priority_count(summary: dict[str, Any]) -> int:
    try:
        return int(summary.get("high_priority_candidate_rows", "") or 0)
    except (TypeError, ValueError):
        return min(candidate_count(summary), 5)


def flow_step(label: str, value: Any, note: str, kind: str, insight: dict[str, Any]) -> str:
    index = {"input": "1", "passed": "2", "watch": "3", "risk": "4"}.get(kind, "")
    return (
        f'<button type="button" class="flow-step {esc(kind)}" '
        f'aria-haspopup="dialog" {insight_attrs(kind, insight)}>'
        f'<span class="flow-index">{index}</span>'
        f"<span>{label}</span><strong>{esc(value)}</strong>"
        f"<small>{note}</small></button>"
    )


def metric_insight(summary: dict[str, Any], kind: str, language: str) -> dict[str, Any]:
    _ = language
    details = shared_insight_facts(summary)
    templates = {
        "input": (
            ("Input data scope", "输入数据范围"),
            ("Unique symbols are shown as the primary scope; price rows remain a separate report fact.", "主指标展示去重股票数；行情行数保留为单独报告事实。"),
            details["input"],
            [("Check source files in the report appendix.", "在报告附录核对数据文件。")],
        ),
        "passed": (
            ("First-check result", "初筛通过情况"),
            ("Rows that reached the diagnostic result table after basic rule checks.", "通过基础规则检查后进入诊断结果表的行数。"),
            details["passed"],
            [("Review rejected rows before changing thresholds.", "调整阈值前先查看被排除记录。")],
        ),
        "watch": (
            ("Watchlist scope", "观察名单范围"),
            ("Candidates that need a closer look before any real trading decision.", "需要进一步查看后才能进入真实决策的候选范围。"),
            details["watch"],
            [("Open the full candidate table for row-level evidence.", "打开完整候选表查看逐行依据。")],
        ),
        "risk": (
            ("Risk note scope", "风险提示范围"),
            ("High-priority rows or failed steps that must be checked before use.", "使用前必须核验的高优先级候选或失败步骤。"),
            details["risk"],
            [("Read risk notes before considering the shortlist.", "查看短名单前先阅读风险提示。")],
        ),
    }
    return insight_payload(*templates[kind])


def flow_insight(summary: dict[str, Any], kind: str, language: str) -> dict[str, Any]:
    _ = language
    details = shared_insight_facts(summary)
    templates = {
        "input": (
            ("Step 1: sample", "步骤 1：样本"),
            ("The flow starts from unique stocks in the local data; history rows remain separately listed in the report.", "流程从本地数据中的去重股票开始；历史行情行数仍可在报告中单独查看。"),
            details["input"],
            [("Confirm the data source before reading downstream counts.", "阅读下游数量前先确认数据来源。")],
        ),
        "passed": (
            ("Step 2: basic checks", "步骤 2：基础检查"),
            ("Configured rules remove obvious mismatches and keep diagnostic evidence.", "配置规则会排除明显不符合项，并保留诊断依据。"),
            details["passed"],
            [("Use diagnostics to understand why rows were rejected.", "用诊断表理解行被排除的原因。")],
        ),
        "watch": (
            ("Step 3: watchlist", "步骤 3：观察名单"),
            ("This is an observation list, not an order list or investment recommendation.", "这里是观察名单，不是订单清单或投资建议。"),
            details["watch"],
            [("Inspect row details before taking any external action.", "采取外部动作前先查看逐行详情。")],
        ),
        "risk": (
            ("Step 4: risk note", "步骤 4：风险提示"),
            ("Risk notes keep the report boundary visible before users read candidates.", "风险提示让用户在查看候选前先看到使用边界。"),
            details["risk"],
            [("Resolve high-priority warnings before reuse.", "复用前先处理高优先级提示。")],
        ),
    }
    return insight_payload(*templates[kind])


def shared_insight_facts(summary: dict[str, Any]) -> dict[str, list[tuple[str, str, Any]]]:
    failed_steps = len(summary.get("failed_steps", []))
    status = summary.get("status", "unknown")
    return {
        "input": [
            ("Sample stocks", "样本股票", input_stock_count(summary)),
            ("Price rows", "行情行数", summary.get("prices_rows", 0)),
            ("Spot rows", "实时行情行数", summary.get("spot_rows", 0)),
            ("History symbols", "历史样本股票", summary.get("history_symbol_count", 0)),
        ],
        "passed": [
            ("Diagnostic rows", "诊断行数", summary.get("diagnostic_rows", 0)),
            ("Spot matches", "实时匹配股票", summary.get("spot_matched_symbols", 0)),
            ("Failed steps", "失败步骤", failed_steps),
        ],
        "watch": [
            ("Candidate rows", "候选行数", candidate_count(summary)),
            ("Candidate file written", "候选文件已写入", summary.get("candidates_output_written", False)),
            ("Run status", "运行状态", status),
        ],
        "risk": [
            ("High-priority rows", "高优先级行数", high_priority_count(summary)),
            ("Failed steps", "失败步骤", failed_steps),
            ("Run status", "运行状态", status),
        ],
    }


def insight_payload(
    title: tuple[str, str],
    summary: tuple[str, str],
    facts: list[tuple[str, str, Any]],
    actions: list[tuple[str, str]],
) -> dict[str, Any]:
    return {
        "title_en": title[0],
        "title_zh": title[1],
        "summary_en": summary[0],
        "summary_zh": summary[1],
        "facts_en": serialize_facts(facts, "en"),
        "facts_zh": serialize_facts(facts, "zh"),
        "actions_en": "|".join(item[0] for item in actions),
        "actions_zh": "|".join(item[1] for item in actions),
    }


def serialize_facts(facts: list[tuple[str, str, Any]], language: str) -> str:
    return "|".join(
        f"{label_for_language(en, zh, language)}::{raw_text(value) or '-'}"
        for en, zh, value in facts
    )


def label_for_language(en: str, zh: str, language: str) -> str:
    return zh if language == "zh" else en


def insight_attrs(kind: str, payload: dict[str, Any]) -> str:
    kind_en, kind_zh = insight_kind_labels(kind)
    attrs = {
        "data-insight-trigger": "",
        "data-insight-node": kind,
        "data-insight-kind-en": kind_en,
        "data-insight-kind-zh": kind_zh,
        "data-insight-title-en": payload["title_en"],
        "data-insight-title-zh": payload["title_zh"],
        "data-insight-summary-en": payload["summary_en"],
        "data-insight-summary-zh": payload["summary_zh"],
        "data-insight-facts-en": payload["facts_en"],
        "data-insight-facts-zh": payload["facts_zh"],
        "data-insight-actions-en": payload["actions_en"],
        "data-insight-actions-zh": payload["actions_zh"],
    }
    return " ".join(f'{name}="{attr_text(value)}"' for name, value in attrs.items())


def insight_kind_labels(kind: str) -> tuple[str, str]:
    return {
        "input": ("Input data", "输入数据"),
        "passed": ("Basic checks", "基础检查"),
        "watch": ("Watchlist", "观察名单"),
        "risk": ("Risk note", "风险提示"),
    }.get(kind, ("Detail", "详情"))


def insight_drawer(language: str) -> str:
    close_label = bilingual("Close", "关闭", language)
    return (
        '<div class="insight-drawer" data-insight-drawer data-report-modal-root hidden aria-hidden="true">'
        '<section class="insight-dialog" role="dialog" aria-modal="true" aria-labelledby="insight-title" aria-describedby="insight-summary">'
        f'<button type="button" class="insight-close" data-insight-close {i18n_attr("aria-label", "Close", "关闭", language)}>{close_label}</button>'
        '<span class="insight-eyebrow" data-insight-kind></span>'
        '<h3 id="insight-title" data-insight-title></h3>'
        '<p id="insight-summary" class="insight-summary" data-insight-summary></p>'
        '<dl class="insight-facts" data-insight-facts></dl>'
        '<ul class="insight-actions" data-insight-actions></ul>'
        "</section></div>"
    )


def run_numbers_panel(summary: dict[str, Any], language: str) -> str:
    label = bilingual("Run counts", "运行数字", language)
    hint = bilingual(
        "These counts summarize the run and are not needed for normal reading.",
        "这些数字用于概览本次运行，普通阅读不需要理解。",
        language,
    )
    return collapsible_details(
        label,
        f'<p class="report-note">{hint}</p>{metric_grid(summary, language)}',
        "run-metrics",
    )


def boundary_panel(
    summary: dict[str, Any],
    language: str,
    candidate_rows: list[dict[str, Any]] | None = None,
) -> str:
    return (
        '<div class="final-notice-grid">'
        f"{result_notice_card(summary, language)}"
        f"{disclaimer_card(language)}"
        "</div>"
        f"{disclosure_alerts(summary, language, candidate_rows or [])}"
    )


def result_notice_card(summary: dict[str, Any], language: str) -> str:
    title = result_notice_title(summary, language)
    body = (
        f'<p>{plain_result_meaning(summary, language)}</p>'
        f'<p>{plain_usage_story(summary, language)}</p>'
        f'<p>{plain_limit_story(summary, language)}</p>'
    )
    return (
        '<section class="result-notice-card">'
        f"<div><h3>{title}</h3>{body}</div>"
        '<span class="result-notice-illustration" aria-hidden="true"></span></section>'
    )


def result_notice_title(summary: dict[str, Any], language: str) -> str:
    status = str(summary.get("status", "unknown"))
    if status != "completed":
        return bilingual("Run incomplete / no usable result", "未完成 / 无可用结果", language)
    if candidate_count(summary) == 0:
        return bilingual("No candidate / incomplete data", "无候选 / 数据不完整", language)
    return bilingual("Use boundary / risk reminder", "使用边界 / 风险提示", language)


def disclaimer_card(language: str) -> str:
    title = bilingual("Disclaimer", "免责声明（必读）", language)
    paragraphs = (
        bilingual(
            "This report is for reference only and does not constitute any investment advice, contract, or commitment.",
            "本报告仅供参考，不构成任何形式的投资建议、要约或承诺。",
            language,
        ),
        bilingual(
            "The investor bears investment decision risk independently. Review risks carefully before acting.",
            "投资者应自行承担投资决策风险，请在充分了解相关风险的基础上审慎决策。",
            language,
        ),
    )
    body = "".join(f"<p>{item}</p>" for item in paragraphs)
    return (
        f'<section class="disclaimer-card"><div><h3>{title}</h3>{body}</div>'
        '<span class="disclaimer-illustration" aria-hidden="true"></span></section>'
    )


def plain_boundary_cards(summary: dict[str, Any], language: str) -> str:
    rows = [
        (
            bilingual("What this means", "这份结果代表什么", language),
            plain_result_meaning(summary, language),
        ),
        (
            bilingual("How to use it", "适合怎么用", language),
            plain_usage_story(summary, language),
        ),
        (
            bilingual("What it cannot prove", "不能证明什么", language),
            plain_limit_story(summary, language),
        ),
    ]
    return "".join(
        f"<div><span>{label}</span><p>{body}</p></div>" for label, body in rows
    )


def plain_result_meaning(summary: dict[str, Any], language: str) -> str:
    status = str(summary.get("status", "unknown"))
    count = candidate_count(summary)
    if status != "completed":
        return plain_failure_reason(summary, language)
    if count == 0:
        return bilingual(
            "Under the current data and rules, no stock matched the strategy rules or entered the watchlist.",
            "在当前数据和规则下，没有股票符合当前策略规则，因此没有进入观察清单。",
            language,
        )
    en = f"{count} stock matched the current strategy rules and entered the watchlist."
    if count != 1:
        en = f"{count} stocks matched the current strategy rules and entered the watchlist."
    zh = f"{count} 只股票符合当前策略规则，进入观察清单。"
    return bilingual(en, zh, language)


def plain_usage_story(summary: dict[str, Any], language: str) -> str:
    status = str(summary.get("status", "unknown"))
    count = candidate_count(summary)
    if status != "completed":
        return plain_failure_action(summary, language)
    if count == 0:
        return bilingual(
            "First confirm whether the data source and strategy scope are what you intended, then decide whether to adjust them.",
            "先确认数据来源和策略范围是不是你想要的，再判断是否需要调整数据范围、策略规则或数据来源。",
            language,
        )
    return bilingual(
        "Use it as a report watchlist, not as a buy or sell instruction.",
        "把它当作报告中的观察清单，不要当作买卖指令。",
        language,
    )


def plain_limit_story(summary: dict[str, Any], language: str) -> str:
    if str(summary.get("status", "unknown")) != "completed":
        return plain_failure_limit(summary, language)
    return bilingual(
        "It does not prove the stock will rise, that it is suitable to buy, or that a real order can be filled.",
        "它不能证明股票一定会上涨、适合买入，或真实下单一定能成交。",
        language,
    )


def plain_failure_reason(summary: dict[str, Any], language: str) -> str:
    history = summary.get("history_selection", {})
    if isinstance(history, dict) and bool(history.get("selection_failed")):
        return plain_selection_failure_reason(history, language)
    return bilingual(
        f"The AI agent did not produce a usable watchlist in this run. {plain_boundary_text(summary, 'en')}",
        f"AI Agent 在生成可用观察清单前停止了。{plain_boundary_text(summary, 'zh')}",
        language,
    )


def plain_failure_action(summary: dict[str, Any], language: str) -> str:
    history = summary.get("history_selection", {})
    if isinstance(history, dict) and bool(history.get("selection_failed")):
        return plain_selection_failure_action(history, language)
    return bilingual(
        f"Fix the input or settings, then rerun. {plain_mode_reason_text(summary, 'en')}",
        f"先修复输入或设置，再重新运行。{plain_mode_reason_text(summary, 'zh')}",
        language,
    )


def plain_failure_limit(summary: dict[str, Any], language: str) -> str:
    history = summary.get("history_selection", {})
    if isinstance(history, dict) and bool(history.get("selection_failed")):
        return plain_selection_failure_limit(history, language)
    return bilingual(
        f"This failed run has no usable watchlist. {plain_limit_text(summary, 'en')}",
        f"本次失败运行没有可用观察清单。{plain_limit_text(summary, 'zh')}",
        language,
    )


def plain_selection_failure_reason(history: dict[str, Any], language: str) -> str:
    stage = str(history.get("preflight_stage", "unknown"))
    reason = str(history.get("selection_failed_reason", "unknown"))
    en = (
        "The run stopped at the preflight spot-selection stage because the filtered spot "
        f"snapshot produced no history symbols. preflight_stage={stage} "
        f"selection_failed_reason={reason}"
    )
    zh = (
        "本次在前置筛选阶段停止，spot 快照经过过滤后没有留下任何可抓历史的标的。"
        f"preflight_stage={stage} selection_failed_reason={reason}"
    )
    return bilingual(en, zh, language)


def plain_selection_failure_action(history: dict[str, Any], language: str) -> str:
    action = str(history.get("selection_failed_next_action", "")).strip()
    if action == "expand_spot_universe_or_relax_filters":
        en = "Expand the spot universe or relax the filters, then rerun."
        zh = "先扩大 spot 股票池或放宽过滤条件，再重新运行。"
        return bilingual(en, zh, language)
    if action:
        en = f"Follow the reported next action, then rerun. next_action={action}"
        zh = f"按报告给出的下一步处理后重新运行。next_action={action}"
        return bilingual(en, zh, language)
    en = "Fix the preflight spot-selection failure, then rerun."
    zh = "先修复前置 spot 选择失败的问题，再重新运行。"
    return bilingual(en, zh, language)


def plain_selection_failure_limit(history: dict[str, Any], language: str) -> str:
    stage = str(history.get("preflight_stage", "unknown"))
    en = f"This failed run has no usable watchlist because preflight_stage={stage} produced no history symbols."
    zh = f"这次失败没有形成可用观察清单，因为 preflight_stage={stage} 没有产出历史标的。"
    return bilingual(en, zh, language)


def plain_boundary_text(summary: dict[str, Any], language: str) -> str:
    return localized_text(boundary_key(summary), language)


def plain_mode_reason_text(summary: dict[str, Any], language: str) -> str:
    return localized_text(mode_reason_key(summary), language)


def plain_limit_text(summary: dict[str, Any], language: str) -> str:
    return localized_text(limit_key(summary), language)


def boundary_key(summary: dict[str, Any]) -> str:
    if mode_unresolved(summary):
        return "unresolved_boundary_summary"
    if not summary.get("prediction_mode"):
        return generic_boundary_key(summary)
    return prediction_boundary_key(summary)


def generic_boundary_key(summary: dict[str, Any]) -> str:
    if generic_scoring_failed_at_strict_gate(summary):
        return "generic_strict_failed_boundary_summary"
    if generic_mode_not_ready(summary):
        return "generic_not_scored_boundary_summary"
    return "generic_boundary_summary"


def prediction_boundary_key(summary: dict[str, Any]) -> str:
    if prediction_columns_missing(summary):
        return "prediction_missing_boundary_summary"
    if prediction_scoring_failed_after_consumption(summary):
        return "prediction_strict_failed_boundary_summary"
    if prediction_mode_not_ready(summary):
        return "prediction_not_scored_boundary_summary"
    return "prediction_boundary_summary"


def mode_reason_key(summary: dict[str, Any]) -> str:
    if mode_unresolved(summary):
        return "why_unresolved_value"
    if not summary.get("prediction_mode"):
        if generic_scoring_failed_at_strict_gate(summary):
            return "why_generic_strict_failed_value"
        if generic_mode_not_ready(summary):
            return "why_generic_not_scored_value"
        if str(summary.get("requested_mode", "")) == "generic":
            return "why_generic_requested_value"
        return "why_generic_auto_value"
    if prediction_columns_missing(summary):
        return "why_prediction_missing_columns_value"
    if prediction_scoring_failed_after_consumption(summary):
        return "why_prediction_strict_failed_value"
    if prediction_mode_not_ready(summary):
        return "why_prediction_not_scored_value"
    return "why_prediction_ready_value"


def scoring_fields_panel(summary: dict[str, Any], language: str) -> str:
    label = bilingual("Strategy and scoring fields", "策略和评分字段", language)
    return collapsible_details(
        label,
        f'<div class="note-grid">{boundary_cards(summary, language)}</div>'
        f'<div class="limit-panel">{limit_panel(summary, language)}</div>',
        "scoring-fields",
    )


def candidate_cards(rows: list[dict[str, Any]], language: str) -> str:
    if not rows:
        return ""
    return candidate_preview_table(rows[:MASTER_DETAIL_PREVIEW_LIMIT], language)


def candidate_preview_table(rows: list[dict[str, Any]], language: str) -> str:
    title = bilingual("Watchlist Top 5 Preview", "观察池 Top 5 预览", language)
    hint = bilingual(
        "Top 5 are shown first. Open the complete table below for all rows and row details.",
        "这里先显示前 5 条；完整候选表在下方页面内展示，可查看全部行和行详情。",
        language,
    )
    show_industry = any(candidate_field_value_present(candidate_industry(row)) for row in rows)
    headers = [
        bilingual("Stock name (code)", "股票名称（代码）", language),
        bilingual("Board", "板块", language),
        bilingual("Level", "观察等级", language),
        bilingual("Summary", "简述", language),
    ]
    if show_industry:
        headers.insert(2, bilingual("Industry", "行业", language))
    head = "".join(f"<th>{label}</th>" for label in headers)
    body = "".join(
        candidate_preview_row(row, language, show_industry=show_industry)
        for row in rows
    )
    mobile_cards = "".join(
        candidate_preview_card(row, language, show_industry=show_industry)
        for row in rows
    )
    return (
        '<div class="candidate-cards" data-preview-table>'
        f'<div class="preview-heading"><div><h3>{title}</h3><p>{hint}</p></div></div>'
        f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
        f'<div class="preview-mobile-cards">{mobile_cards}</div>'
        "</div>"
    )


def candidate_preview_row(
    row: dict[str, Any],
    language: str,
    *,
    show_industry: bool,
) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = raw_text(row.get("name")) or symbol
    display_name = stock_name_or_missing(name, symbol, language)
    missing_class = " missing" if stock_name_missing(name, symbol) else ""
    score = format_numeric(row.get("total_score", ""), 3, "")
    board = candidate_listing_board(row)
    industry = candidate_industry(row)
    summary = candidate_summary_text(raw_text(row.get("key_reasons")), language)
    industry_cell = f"<td>{esc(industry)}</td>" if show_industry else ""
    return (
        f'<tr data-preview-symbol="{esc(symbol)}" tabindex="0" role="button">'
        f'<td><strong class="stock-anchor{missing_class}">{esc(display_name)}</strong>'
        f'<span class="stock-code">{esc(symbol)}</span></td>'
        f"<td>{esc(board)}</td>"
        f"{industry_cell}"
        f"<td>{strategy_level_badge(score, language)}</td>"
        f'<td class="text-cell">{summary}</td>'
        "</tr>"
    )


def candidate_preview_card(
    row: dict[str, Any],
    language: str,
    *,
    show_industry: bool,
) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = raw_text(row.get("name")) or symbol
    display_name = stock_name_or_missing(name, symbol, language)
    missing_class = " missing" if stock_name_missing(name, symbol) else ""
    score = format_numeric(row.get("total_score", ""), 3, "")
    board = candidate_listing_board(row)
    industry = candidate_industry(row)
    summary = candidate_summary_text(raw_text(row.get("key_reasons")), language)
    industry_html = ""
    if show_industry:
        industry_label = bilingual("Industry", "行业", language)
        industry_html = (
            '<span class="preview-mobile-meta-item">'
            f'<b>{industry_label}</b>{esc(industry)}</span>'
        )
    return (
        f'<article class="preview-mobile-card" data-preview-symbol="{esc(symbol)}" tabindex="0" role="button">'
        '<div class="preview-mobile-head">'
        f'<div><strong class="stock-anchor{missing_class}">{esc(display_name)}</strong>'
        f'<span class="stock-code">{esc(symbol)}</span></div>'
        f"{strategy_level_badge(score, language)}</div>"
        '<div class="preview-mobile-meta">'
        f'<span class="preview-mobile-meta-item"><b>{bilingual("Board", "板块", language)}</b>{esc(board)}</span>'
        f"{industry_html}</div>"
        f'<p class="preview-mobile-summary">{summary}</p>'
        "</article>"
    )


def stock_name_or_missing(name: str, symbol: str, language: str) -> str:
    if stock_name_missing(name, symbol):
        return plain_bilingual("Name not provided", "名称未提供", language)
    return name


def stock_name_missing(name: str, symbol: str) -> bool:
    normalized_name = str(name).strip()
    normalized_symbol = str(symbol).strip()
    return not normalized_name or normalized_name == normalized_symbol


def candidate_industry(row: dict[str, Any]) -> str:
    for key in ("spot_industry", "industry", "sector", "sw_industry", "申万行业"):
        value = raw_text(row.get(key)).strip()
        if candidate_field_value_present(value):
            return value
    return "-"


def strategy_match_label(value: Any, language: str) -> str:
    try:
        score = float(raw_text(value))
    except ValueError:
        return bilingual("Needs check", "待确认", language)
    if score >= STRATEGY_MATCH_HIGH:
        return bilingual("High", "高", language)
    if score >= STRATEGY_MATCH_MEDIUM:
        return bilingual("Medium", "中等", language)
    return bilingual("Low", "偏低", language)


def strategy_level_badge(value: Any, language: str) -> str:
    label = strategy_match_label(value, language)
    try:
        score = float(raw_text(value))
    except ValueError:
        css_class = "low"
    else:
        if score >= STRATEGY_MATCH_HIGH:
            css_class = "high"
        elif score >= STRATEGY_MATCH_MEDIUM:
            css_class = "medium"
        else:
            css_class = "low"
    return f'<span class="level-badge {css_class}">{label}</span>'


def candidate_summary_text(value: str, language: str) -> str:
    text = value.strip()
    if not text:
        return bilingual(
            "This item passed the main screening checks.",
            "这个观察对象通过了主要筛选检查。",
            language,
        )
    parts = [part.strip().lower() for part in text.split(";") if part.strip()]
    labels: list[tuple[str, str]] = []
    if any(part in {"positive momentum", "short-term activity"} for part in parts):
        labels.append(("recent price action looks acceptable", "近期走势表现符合筛选要求"))
    if any(part in {"acceptable volatility", "rsi in range"} for part in parts):
        labels.append(("risk checks did not show an obvious rule breach", "风险检查没有触发明显拦截"))
    if any(part in {"prediction above threshold", "passed configured filters"} for part in parts):
        labels.append(("it passed the configured screening rules", "它通过了已配置的筛选规则"))
    if not labels:
        return localized_phrase_html(text, language)
    en = "; ".join(label[0] for label in labels)
    zh = "；".join(label[1] for label in labels)
    return bilingual(en, zh, language)


def candidate_risk_text(value: str, language: str) -> str:
    text = value.strip()
    if not text:
        return bilingual(
            "Still verify price, liquidity, news, and your own risk limit.",
            "仍需核验价格、流动性、消息面和你自己的风险上限。",
            language,
        )
    parts = [part.strip().lower() for part in text.split(";") if part.strip()]
    if parts == ["no major configured risk flag"]:
        return bilingual(
        "No major configured warning was triggered, but the candidate still needs a look.",
        "未触发主要配置风险提示，但候选仍需要查看。",
            language,
        )
    return localized_phrase_html(text, language)


def candidates_panel(
    rows: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    all_rows_truncated: bool,
    columns: tuple[str, ...],
    language: str,
    *,
    truncated: bool,
    limit: int,
    csv_path: Any,
    field_coverage: dict[str, Any] | None = None,
    candle_rows: dict[str, list[list[Any]]] | None = None,
    empty_key: str = "empty",
    empty_html: str = "",
) -> str:
    master_detail = candidate_master_detail(
        all_rows,
        language,
        csv_path=csv_path,
        truncated=all_rows_truncated,
        field_coverage=field_coverage,
        candle_rows=candle_rows or {},
        empty_html=empty_html,
        empty_key=empty_key,
    )
    _ = rows, columns, truncated, limit
    return master_detail


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
        + input_partial_alerts(summary, language)
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
    if not summary_uses_local_prices_input(summary):
        return False
    value = metadata.get("real_market_data", "unknown")
    return str(value).strip().lower() in {"", "none", "unknown"}


def market_label_only(metadata: dict[str, Any]) -> bool:
    boundary = str(metadata.get("source_claim_boundary", ""))
    if boundary == "market_label_not_source_exchange_or_calendar_proof":
        return True
    value = metadata.get("market_label_only", False)
    return value is True or str(value).strip().lower() == "true"


def input_partial_alerts(summary: dict[str, Any], language: str) -> list[str]:
    metadata = summary.get("input_metadata", {})
    if not isinstance(metadata, dict) or not local_input_partial(metadata):
        return []
    failed = list_count(metadata.get("failed_symbols"))
    empty = list_count(metadata.get("empty_symbols"))
    truncated = list_count(metadata.get("possibly_truncated_symbols"))
    invalid = metadata.get("input_invalid_rows", metadata.get("invalid_rows", 0))
    dropped = metadata.get("input_dropped_invalid_rows", metadata.get("dropped_invalid_rows", 0))
    non_trading = metadata.get("input_non_trading_rows", metadata.get("non_trading_rows", 0))
    missing_status = metadata.get(
        "input_tradestatus_missing_rows",
        metadata.get("tradestatus_missing_rows", 0),
    )
    symbol_count = metadata.get("symbol_count", "unknown")
    requested = metadata.get("input_requested_symbol_count")
    if requested is None:
        requested = list_count(metadata.get("requested_symbols")) or "unknown"
    output_written = metadata_bool_text(metadata.get("output_written"))
    en = (
        "Partial local input metadata; "
        f"failed_symbols={failed} empty_symbols={empty} "
        f"possibly_truncated_symbols={truncated} "
        f"invalid_rows={invalid} dropped_invalid_rows={dropped} "
        f"non_trading_rows={non_trading} tradestatus_missing_rows={missing_status} "
        f"symbol_count={symbol_count}/{requested} "
        f"output_written={output_written}."
    )
    zh = (
        "本地输入 metadata 为部分结果；"
        f"failed_symbols={failed} empty_symbols={empty} "
        f"possibly_truncated_symbols={truncated} "
        f"invalid_rows={invalid} dropped_invalid_rows={dropped} "
        f"non_trading_rows={non_trading} tradestatus_missing_rows={missing_status} "
        f"symbol_count={symbol_count}/{requested} "
        f"output_written={output_written}。"
    )
    return [bilingual(en, zh, language)]


def local_input_partial(metadata: dict[str, Any]) -> bool:
    return local_input_partial_result(metadata)


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
    alerts = []
    if history_partial(selection):
        failed = selection.get("history_metadata_failed_symbol_count", 0)
        empty = selection.get("history_empty_symbol_count", 0)
        truncated = selection.get("history_possibly_truncated_symbol_count", 0)
        invalid = selection.get("history_invalid_rows", 0)
        dropped = selection.get("history_dropped_invalid_rows", 0)
        fallback = selection.get("history_metadata_fallback_error_count", 0)
        output_written = metadata_bool_text(selection.get("history_output_written"))
        en = (
            "Partial history fetch; "
            f"failed_symbols={failed} empty_symbols={empty} "
            f"possibly_truncated_symbols={truncated} "
            f"invalid_rows={invalid} dropped_invalid_rows={dropped} "
            f"fallback_errors={fallback} output_written={output_written}; "
            "cannot be described as complete history."
        )
        zh = (
            "历史抓取为部分结果；"
            f"failed_symbols={failed} empty_symbols={empty} "
            f"possibly_truncated_symbols={truncated} "
            f"invalid_rows={invalid} dropped_invalid_rows={dropped} "
            f"fallback_errors={fallback} output_written={output_written}；"
            "不能描述为完整历史行情。"
        )
        alerts.append(bilingual(en, zh, language))
    requested = str(selection.get("requested_end_date", ""))
    actual = str(selection.get("history_metadata_actual_date_max", ""))
    all_reached = selection.get("history_metadata_all_symbols_reached_end_date")
    reached_count = selection.get("history_metadata_symbols_reached_end_date_count")
    selected_count = selection.get("selected_symbol_count")
    has_rows = selection.get("history_metadata_end_date_has_rows")
    if not requested or not actual:
        return alerts
    if all_reached is True:
        return alerts
    if all_reached is not False and has_rows is not False:
        return alerts
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
    alerts.append(bilingual(en, zh, language))
    return alerts


def history_partial(selection: dict[str, Any]) -> bool:
    return history_selection_partial_result(selection)


def list_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def metadata_bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "unknown"
    return str(value).strip().lower()


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
        ("runner_source_scope", summary.get("runner_source_scope", "")),
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
    fields.extend(input_metadata_detail_fields(metadata))
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


def input_metadata_detail_fields(metadata: dict[str, Any]) -> list[tuple[str, Any]]:
    keys = (
        "source_scope",
        "token_configured",
        "history_token_configured",
        "history_fields",
        "history_request_interval_seconds",
        "history_limit",
        "history_max_pages",
        "fields",
        "request_interval_seconds",
        "limit",
        "max_pages",
        "requested_symbols",
        "symbol_count",
        "rows",
        "failed_symbols",
        "empty_symbols",
        "possibly_truncated_symbols",
        "invalid_rows",
        "invalid_symbols",
        "invalid_row_examples",
        "dropped_invalid_rows",
        "non_trading_rows",
        "non_trading_symbols",
        "non_trading_row_examples",
        "tradestatus_missing_rows",
        "input_partial_result",
        "input_failed_symbol_count",
        "input_empty_symbol_count",
        "input_possibly_truncated_symbol_count",
        "input_invalid_rows",
        "input_dropped_invalid_rows",
        "input_non_trading_rows",
        "input_tradestatus_missing_rows",
        "input_requested_symbol_count",
        "output_written",
        "metadata_output_written",
    )
    return [
        (f"input_metadata.{key}", metadata.get(key, ""))
        for key in keys
        if key in metadata
    ]


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


def diagnostics_panel(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    columns: tuple[str, ...],
    language: str,
    *,
    truncated: bool,
    limit: int,
    csv_path: Any,
) -> str:
    table_html = limited_table(
        rows,
        columns,
        language,
        truncated=truncated,
        limit=limit,
        csv_path=csv_path,
        empty_key=empty_key_for(summary),
    )
    label = bilingual("Gate diagnostics", "门禁诊断", language)
    return (
        f'<p class="diagnostic-intro">{diagnostic_intro(summary, language)}</p>'
        f"{collapsible_details(label, table_html, 'diagnostics-detail')}"
    )


def diagnostic_intro(summary: dict[str, Any], language: str) -> str:
    status = str(summary.get("status", "unknown"))
    if status != "completed":
        return bilingual(
            "This is for debugging failed runs and may be empty when scoring did not finish.",
            "这里用于排查失败运行；如果评分没有完成，可能没有内容。",
            language,
        )
    if candidate_count(summary) == 0:
        return bilingual(
            "No stock entered the watchlist. Open this only to inspect which rules blocked each row.",
            "没有股票进入观察清单。只有想排查哪些规则拦下了标的时，再展开这里。",
            language,
        )
    return bilingual(
        "This keeps per-stock rule results for reference. Normal users can start with the Top 5 preview and complete candidate table.",
        "这里保留每只股票的规则结果，供参考；普通用户先看 Top 5 预览和完整候选表即可。",
        language,
    )


def collapsible_details(label: str, content: str, extra_class: str = "") -> str:
    class_name = "report-details"
    if extra_class:
        class_name = f"{class_name} {extra_class}"
    return f'<details class="{class_name}"><summary>{label}</summary>{content}</details>'


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


def section(
    title: str,
    content: str,
    *,
    section_id: str = "",
    extra_class: str = "",
) -> str:
    id_attr = f' id="{esc(section_id)}"' if section_id else ""
    classes = "section"
    if extra_class:
        classes = f"{classes} {esc(extra_class)}"
    heading = f"<h2>{title}</h2>" if title else ""
    return f'<section{id_attr} class="{classes}">{heading}{content}</section>'


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
    threshold_summary_en, threshold_summary_zh = threshold_failures_summary_pair(score)
    visible = bilingual(
        "The run completed, but no stock entered the watchlist.",
        "本次运行已完成，但没有股票进入观察清单。",
        language,
    )
    review = bilingual(
        "Completed run with zero candidates; "
        f"effective_empty_result=true empty_result_reason={reason}. {threshold_summary_en}",
        f"本次成功运行但没有候选；effective_empty_result=true empty_result_reason={reason}。{threshold_summary_zh}",
        language,
    )
    return (
        f'<p class="empty">{visible}</p>'
        f"{collapsible_details(bilingual('Zero-result details', '0 结果明细', language), review, 'zero-candidate-details')}"
    )


def threshold_failures_summary_pair(score: dict[str, Any]) -> tuple[str, str]:
    failures = score.get("threshold_failures_by_rule", {})
    if not isinstance(failures, dict) or not failures:
        return ("Top blocking rules: none.", "主要拦截规则：无。")
    ordered = sorted(
        ((str(key), int(value)) for key, value in failures.items()),
        key=lambda item: (-item[1], item[0]),
    )
    top = ordered[:3]
    parts = [threshold_failure_summary_part(key, value, "en") for key, value in top]
    parts_zh = [threshold_failure_summary_part(key, value, "zh") for key, value in top]
    return (
        "Top blocking rules: " + ", ".join(parts) + ".",
        "主要拦截规则：" + "，".join(parts_zh) + "。",
    )


def threshold_failure_summary_part(key: str, value: int, language: str) -> str:
    label = phrase_translation(key, language)
    if label == key:
        return f"{key}={value}"
    if language == "zh":
        return f"{label}（{key}）={value}"
    return f"{label} ({key})={value}"


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
        en = "Synthetic demo data; not real market data."
        zh = "合成 demo 数据；不是真实行情。"
        return bilingual(en, zh, language)
    source_scope = str(summary.get("source_scope", ""))
    if summary_uses_local_prices_input(summary) and source_scope == "local_prices_input":
        return i18n("generic_scope_value", language)
    if source_scope == "unresolved":
        return i18n("unresolved_scope_value", language)
    en = f"Recorded source scope: {source_scope or 'unknown'}"
    zh = f"已记录数据来源范围：{source_scope or 'unknown'}"
    return bilingual(en, zh, language)


def summary_uses_local_prices_input(summary: dict[str, Any]) -> bool:
    runner_scope = str(summary.get("runner_source_scope", summary.get("source_scope", "")))
    return "local_prices_input" in runner_scope.split("+")

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
