"""Master-detail candidate table for the local A-share HTML report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from a_share_selection_html_data import evidence_path
from a_share_selection_html_candidate_helpers import (
    candidate_evidence,
    candidate_entry_body,
    candidate_entry_button_text,
    candidate_field,
    candidate_field_notice_needed,
    candidate_industry,
    candidate_level,
    candidate_reason,
    candidate_review_action,
    candidate_risk_level,
    level_badge,
    level_css_class,
    plain_bilingual,
    risk_badge,
    score_value,
    strip_tags,
)
from a_share_selection_html_format import (
    bilingual,
    esc,
    i18n,
    raw_text,
)


def candidate_open_banner(rows: list[dict[str, Any]], csv_path: Any, language: str) -> str:
    if not rows:
        return ""
    title = bilingual("Complete candidate table entry", "完整候选表入口", language)
    button = candidate_entry_button_text(len(rows), language)
    _ = csv_path
    body = candidate_entry_body(len(rows), language)
    return (
        '<a class="candidate-open-banner" href="#complete-candidates">'
        f'<strong class="candidate-open-title">{title}</strong>'
        f'<span class="candidate-open-body">{body}</span>'
        f'<b class="candidate-open-button">{button}</b>'
        f'<em class="candidate-open-foot">{bilingual("Complete table below", "完整候选表（在下方）", language)}</em></a>'
    )


def candidate_master_detail(
    rows: list[dict[str, Any]],
    language: str,
    *,
    csv_path: Any,
    truncated: bool,
    empty_key: str,
    empty_html: str,
) -> str:
    title = bilingual("Complete Candidate Table", "完整候选表", language)
    hint = bilingual(
        "Data is generated into this HTML. Search, filtering, sorting, and row details run locally in the browser.",
        "数据已随 HTML 生成；搜索、筛选、排序和行详情都在本地浏览器完成。",
        language,
    )
    if not rows:
        empty = empty_html or f'<p class="empty">{i18n(empty_key, language)}</p>'
        return f'<section id="complete-candidates" class="candidate-master-detail"><h3>{title}</h3>{empty}</section>'
    limit_note = ""
    if truncated:
        limit_note = bilingual(
            "Only the first 1000 rows are embedded here; the CSV keeps the full result.",
            "这里仅嵌入前 1000 行；完整结果保留在 CSV 中。",
            language,
        )
    note_html = f'<p class="table-note">{limit_note}</p>' if limit_note else ""
    return (
        '<section id="complete-candidates" class="candidate-master-detail" data-candidate-master-detail>'
        f'<div class="master-detail-header"><div><h3>{title}</h3><p>{hint}</p>'
        f"{note_html}</div>"
        f"{candidate_file_chip(csv_path, language)}</div>"
        f"{candidate_field_notice(rows, language)}"
        '<div class="master-detail-grid">'
        f"{candidate_master_table(rows, language)}"
        f"{candidate_detail_panel(rows[0], language)}"
        "</div></section>"
    )


def candidate_field_notice(rows: list[dict[str, Any]], language: str) -> str:
    if not candidate_field_notice_needed(rows):
        return ""
    text = bilingual(
        "Some fields are blank because the input file did not provide industry, valuation, or long-range performance columns. This table only displays traceable source fields.",
        "部分字段为空，是因为本次输入文件没有提供行业、估值或长期涨跌幅等列。本表只展示可追溯的来源字段。",
        language,
    )
    return f'<p class="field-notice">{text}</p>'


def candidate_file_chip(csv_path: Any, language: str) -> str:
    path = evidence_path(csv_path, Path(str(csv_path)).parent if csv_path else None)
    label = bilingual("CSV backup", "CSV 备用文件", language)
    display = path["display"] or "candidates.csv"
    return f'<code class="file-chip" title="{esc(path["title"])}">{label}: {esc(display)}</code>'


def candidate_master_toolbar(rows: list[dict[str, Any]], language: str) -> str:
    search_label = bilingual("Search", "搜索", language)
    search_placeholder = plain_bilingual(
        "Code / name / industry / keyword",
        "代码 / 名称 / 行业 / 关键词",
        language,
    )
    all_label = plain_bilingual("All", "全部", language)
    industry_label = bilingual("Industry", "行业", language)
    level_label = bilingual("Observation level", "观察等级", language)
    sort_label = bilingual("Sort", "排序", language)
    clear_label = bilingual("Clear", "清空", language)
    industry_options = filter_options(candidate_industry(row) for row in rows)
    level_options = filter_options(candidate_level(row, language) for row in rows)
    return (
        '<div class="candidate-toolbar">'
        f'<label><span>{search_label}</span><input type="search" data-candidate-search placeholder="{esc(search_placeholder)}"></label>'
        f'<label><span>{industry_label}</span><select data-candidate-industry><option value="">{all_label}</option>{industry_options}</select></label>'
        f'<label><span>{level_label}</span><select data-candidate-level><option value="">{all_label}</option>{level_options}</select></label>'
        f'<label><span>{sort_label}</span><select data-candidate-sort>'
        f'<option value="score">{plain_bilingual("Score", "评分", language)}</option>'
        f'<option value="rank">{plain_bilingual("Rank", "序号", language)}</option>'
        f'</select></label><button type="button" data-candidate-reset>{clear_label}</button></div>'
    )


def filter_options(values: Any) -> str:
    unique = sorted({str(value) for value in values if str(value)})
    return "".join(f'<option value="{esc(value)}">{esc(value)}</option>' for value in unique)


def candidate_master_table(rows: list[dict[str, Any]], language: str) -> str:
    header = (
        bilingual("No.", "序号", language),
        bilingual("Stock code", "股票代码", language),
        bilingual("Stock name", "股票名称", language),
        bilingual("Industry", "行业", language),
        bilingual("Score", "综合评分", language),
        bilingual("Level", "观察等级", language),
        bilingual("1Y change", "近一年涨跌幅", language),
        bilingual("Market cap", "市值（亿元）", language),
        bilingual("PE TTM", "PE（TTM）", language),
        bilingual("PB LF", "PB（LF）", language),
    )
    head = "".join(f"<th>{label}</th>" for label in header)
    body = "".join(candidate_master_row(row, index, language) for index, row in enumerate(rows))
    footer = candidate_table_footer(len(rows), language)
    sparse_note = candidate_sparse_note(len(rows), language)
    return (
        '<div class="master-list-panel">'
        f"{candidate_master_toolbar(rows, language)}"
        f'<div class="master-table"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table>{sparse_note}</div>{footer}</div>"
    )


def candidate_sparse_note(row_count: int, language: str) -> str:
    if row_count > 5:
        return ""
    text = bilingual(
        "Only traceable rows from this run are shown. No placeholder stocks were added.",
        "仅展示本次可追溯候选行，未添加占位股票。",
        language,
    )
    return f'<div class="sparse-note">{text}</div>'


def candidate_table_footer(row_count: int, language: str) -> str:
    total_label = plain_bilingual("Total", "共", language)
    rows_label = plain_bilingual("rows", "条", language)
    page_label = plain_bilingual("Page", "页", language)
    per_page_label = plain_bilingual("Rows per page", "每页", language)
    previous = plain_bilingual("Previous", "上一页", language)
    next_page = plain_bilingual("Next", "下一页", language)
    return (
        '<div class="master-table-footer">'
        f'<span>{total_label} <b data-candidate-visible-count>{row_count}</b> / '
        f'<b data-candidate-total-count>{row_count}</b> {rows_label}</span>'
        '<div class="candidate-pager">'
        f'<button type="button" data-candidate-prev>{previous}</button>'
        '<span class="candidate-page-numbers" data-candidate-page-numbers></span>'
        f'<span class="candidate-page-status">{page_label} <b data-candidate-page-current>1</b> / '
        '<b data-candidate-page-total>1</b></span>'
        f'<button type="button" data-candidate-next>{next_page}</button>'
        f'<label>{per_page_label} <select data-candidate-page-size>'
        '<option value="10">10</option><option value="25">25</option>'
        '<option value="50">50</option></select></label>'
        "</div></div>"
    )


def candidate_master_row(row: dict[str, Any], index: int, language: str) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = raw_text(row.get("name")) or symbol
    rank = raw_text(row.get("rank")) or str(index + 1)
    level = candidate_level(row, language)
    summary = candidate_reason(row, language)
    risk_label, risk_class = candidate_risk_level(row, language)
    action = candidate_review_action(row, language)
    industry = candidate_industry(row)
    selected = ' data-selected="true"' if index == 0 else ""
    attrs = candidate_detail_attrs(row, rank, level, summary, risk_label, risk_class, action, language)
    search = f"{symbol} {name} {industry} {summary} {risk_label} {action}".lower()
    score = score_value(row)
    return (
        f'<tr data-candidate-row data-rank="{esc(rank)}" data-score="{esc(score_value(row))}" '
        f'data-search="{esc(search)}" data-industry="{esc(industry)}" data-level="{esc(level)}" data-risk="{esc(risk_label)}"{selected}{attrs}>'
        f'<td><span class="row-check" aria-hidden="true"></span> {esc(rank)}</td>'
        f'<td><span class="symbol-cell">{esc(symbol)}</span></td>'
        f'<td><strong class="name-cell">{esc(name)}</strong></td>'
        f"<td>{esc(industry)}</td>"
        f"<td><strong>{esc(score or '-')}</strong></td>"
        f"<td>{level_badge(level, css_class=level_css_class(row))}</td>"
        f"<td>{esc(candidate_field(row, ('pct_chg_1y', 'one_year_pct_chg', 'spot_pct_chg'), percent=True))}</td>"
        f"<td>{esc(candidate_field(row, ('market_cap_billion', 'market_cap_cny_billion', 'market_cap')))}</td>"
        f"<td>{esc(candidate_field(row, ('pe_ttm', 'peTTM', 'pe')))}</td>"
        f"<td>{esc(candidate_field(row, ('pb_lf', 'pbLF', 'pb')))}</td></tr>"
    )


def candidate_detail_attrs(
    row: dict[str, Any],
    rank: str,
    level: str,
    summary: str,
    risk_label: str,
    risk_class: str,
    action: str,
    language: str,
) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = raw_text(row.get("name")) or symbol
    fields = {
        "row-title": f"{name} {symbol}",
        "row-date": raw_text(row.get("date")) or "-",
        "row-rank": rank,
        "row-level": level,
        "row-level-class": level_css_class(row),
        "row-summary": summary,
        "row-reason": summary,
        "row-risk": risk_label,
        "row-risk-class": risk_class,
        "row-action": action,
        "row-evidence": candidate_evidence(row, language),
    }
    return "".join(f' data-{key}="{esc(value)}"' for key, value in fields.items())


def candidate_detail_panel(row: dict[str, Any], language: str) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = raw_text(row.get("name")) or symbol
    level = candidate_level(row, language)
    summary = candidate_reason(row, language)
    risk_label, risk_class = candidate_risk_level(row, language)
    action = candidate_review_action(row, language)
    evidence = strip_tags(candidate_evidence(row, language))
    date = raw_text(row.get("date")) or "-"
    evidence_html = esc(evidence).replace("\n", "<br>")
    return (
        '<aside class="candidate-detail-panel" data-candidate-detail>'
        f"{candidate_detail_head(name, symbol, date, level, level_css_class(row))}"
        '<div class="detail-body">'
        '<div class="detail-main">'
        f"{level_detail_grid(level, level_css_class(row), language)}"
        f"{detail_grid('One-line summary', '一句话摘要', summary, 'detail-summary', language)}"
        f"{detail_grid('Why selected', '入选原因', summary, 'detail-reason', language)}"
        f"{risk_detail_grid(risk_label, risk_class, language)}"
        f"{detail_grid('Next check', '下一步核验', action, 'detail-action', language)}"
        "</div>"
        f"{evidence_detail_card(evidence_html, language)}</div>"
        "</aside>"
    )


def candidate_detail_head(name: str, symbol: str, date: str, level: str, css_class: str) -> str:
    return (
        '<div class="detail-head">'
        f'<div><h3 data-detail-title>{esc(name)} {esc(symbol)}</h3>'
        f'<span data-detail-date>{esc(date)}</span></div>'
        f'{level_badge(level, attrs=" data-detail-level", css_class=css_class)}</div>'
    )


def level_detail_grid(level: str, css_class: str, language: str) -> str:
    return (
        '<div class="detail-grid">'
        f"{detail_title('Observation level', '观察等级', language)}"
        f'<p>{level_badge(level, attrs=" data-detail-level", css_class=css_class)}</p></div>'
    )


def risk_detail_grid(risk_label: str, risk_class: str, language: str) -> str:
    return (
        '<div class="detail-grid">'
        f"{detail_title('Risk severity', '风险严重度', language)}"
        f'<p>{risk_badge(risk_label, risk_class, attrs=" data-detail-risk")}</p></div>'
    )


def evidence_detail_card(evidence_html: str, language: str) -> str:
    return (
        '<div class="detail-evidence-card">'
        f"<span>{bilingual('Public evidence', '公开证据', language)}</span>"
        f'<p data-detail-evidence>{evidence_html}</p></div>'
    )


def detail_grid(en: str, zh: str, value: str, attr: str, language: str) -> str:
    safe_value = esc(value).replace("\n", "<br>")
    return (
        f'<div class="detail-grid">{detail_title(en, zh, language)}'
        f"<p data-{attr}>{safe_value}</p></div>"
    )


def detail_title(en: str, zh: str, language: str) -> str:
    return f"<span>{bilingual(en, zh, language)}</span>"


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
