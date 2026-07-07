"""Master-detail candidate table for the local A-share HTML report."""

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


import json
from pathlib import Path
from typing import Any

from lib.selection_core.a_share_selection_candidate_fields import (
    OPTIONAL_CANDIDATE_FIELD_KEYS,
    candidate_field_aliases,
    candidate_field_labels,
)
from lib.report_html.a_share_selection_html_data import (
    HTML_CANDLE_ROWS_LIMIT,
    HTML_CANDLE_SYMBOL_LIMIT,
    evidence_path,
)
from lib.report_html.a_share_selection_html_candidate_helpers import (
    candidate_evidence,
    candidate_entry_body,
    candidate_entry_button_text,
    candidate_field,
    candidate_industry,
    candidate_listing_board,
    candidate_uses_ticker_as_name,
    candidate_level,
    candidate_reason,
    candidate_data_note,
    candidate_risk_level,
    display_value,
    level_badge,
    level_css_class,
    plain_bilingual,
    risk_badge,
    score_value,
    strip_tags,
)
from lib.report_html.a_share_selection_html_format import (
    bilingual,
    esc,
    i18n,
    i18n_attr,
    raw_text,
)


ONE_YEAR_FIELD_KEYS = candidate_field_aliases("one_year_pct_chg")
MARKET_CAP_FIELD_KEYS = candidate_field_aliases("market_cap")
PE_FIELD_KEYS = candidate_field_aliases("pe_ttm")
PB_FIELD_KEYS = candidate_field_aliases("pb_lf")
OPTIONAL_MASTER_COLUMNS = OPTIONAL_CANDIDATE_FIELD_KEYS


def candidate_open_banner(rows: list[dict[str, Any]], language: str) -> str:
    if not rows:
        return ""
    title = bilingual("Complete candidate table entry", "完整候选表入口", language)
    button = candidate_entry_button_text(len(rows), language)
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
    candle_rows: dict[str, list[list[Any]]],
    empty_key: str,
    empty_html: str,
    field_coverage: dict[str, Any] | None = None,
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
        f"{candidate_field_notice(rows, field_coverage, language)}"
        f"{candidate_field_coverage_panel(field_coverage, language)}"
        '<div class="master-detail-grid">'
        f"{candidate_master_table(rows, language)}"
        f"{candidate_detail_panel(rows[0], language)}"
        "</div>"
        f"{candidate_stock_dialog(language)}"
        f"{candidate_candle_data_script(candle_rows)}"
        "</section>"
    )


def candidate_field_notice(
    rows: list[dict[str, Any]],
    field_coverage: dict[str, Any] | None,
    language: str,
) -> str:
    hidden_en = candidate_hidden_field_labels(rows, field_coverage, "en")
    hidden_zh = candidate_hidden_field_labels(rows, field_coverage, "zh")
    if not hidden_en:
        return ""
    text = bilingual(
        f"Hidden unavailable columns: {', '.join(hidden_en)}. The CSV is still available for raw field audit.",
        f"已隐藏本次源数据未提供或整列为空的字段：{'、'.join(hidden_zh)}。CSV 原始字段仍可下载核查。",
        language,
    )
    return f'<p class="field-notice">{text}</p>'


def candidate_field_coverage_panel(
    field_coverage: dict[str, Any] | None, language: str
) -> str:
    if not isinstance(field_coverage, dict):
        return ""
    rows_evaluated = int(field_coverage.get("rows_evaluated", 0) or 0)
    fields = field_coverage.get("fields", {})
    if rows_evaluated <= 0 or not isinstance(fields, dict):
        return ""
    items = []
    for key in OPTIONAL_CANDIDATE_FIELD_KEYS:
        field = fields.get(key, {})
        if not isinstance(field, dict):
            continue
        present = int(field.get("present_rows", 0) or 0)
        missing = int(field.get("missing_rows", 0) or 0)
        ratio = field.get("coverage_ratio", 0)
        label = bilingual(*candidate_field_labels(key), language)
        items.append(
            f'<div class="field-coverage-chip" data-field-key="{esc(key)}" data-field-missing="{str(missing > 0).lower()}">'
            f"<span>{label}</span><strong>{present}/{rows_evaluated}</strong>"
            f"<b>{field_coverage_ratio_text(ratio)}</b></div>"
        )
    if not items:
        return ""
    note = bilingual(
        "Field coverage only tells whether this run's source columns were present in the candidate CSV. Blank or hidden columns may still carry raw evidence in the CSV.",
        "字段覆盖率只说明本次候选表源字段是否写入 CSV；空列或隐藏列仍可能保留在原始 CSV 中供核查。",
        language,
    )
    title = bilingual("Field coverage", "字段覆盖率", language)
    return (
        '<section class="field-coverage-card">'
        f'<div class="field-coverage-head"><strong>{title}</strong><p>{note}</p></div>'
        f'<div class="field-coverage-grid">{"".join(items)}</div>'
        "</section>"
    )


def field_coverage_ratio_text(value: Any) -> str:
    try:
        ratio = min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return "0%"
    return f"{ratio:.0%}"


def candidate_file_chip(csv_path: Any, language: str) -> str:
    path = evidence_path(csv_path, Path(str(csv_path)).parent if csv_path else None)
    label = bilingual("CSV backup", "CSV 备用文件", language)
    download_label = bilingual("Download CSV", "下载 CSV", language)
    display = path["display"] or "candidates.csv"
    href = esc(display)
    title = esc(path["title"])
    return (
        '<div class="candidate-file-actions">'
        f'<code class="file-chip" title="{title}">{label}: {esc(display)}</code>'
        f'<a class="candidate-download-link" href="{href}" download>{download_label}</a>'
        "</div>"
    )


def candidate_master_toolbar(rows: list[dict[str, Any]], language: str) -> str:
    search_label = bilingual("Search", "搜索", language)
    has_industry = candidate_column_has_values(rows, "industry")
    search_placeholder_en = candidate_search_placeholder(has_industry, "en")
    search_placeholder_zh = candidate_search_placeholder(has_industry, "zh")
    all_label = plain_bilingual("All", "全部", language)
    industry_label = bilingual("Industry", "行业", language)
    board_label = bilingual("Board", "板块", language)
    level_label = bilingual("Observation level", "观察等级", language)
    sort_label = bilingual("Sort", "排序", language)
    clear_label = bilingual("Clear", "清空", language)
    board_options = filter_options(candidate_listing_board(row) for row in rows)
    level_options = level_filter_options(rows, language)
    industry_control = ""
    if has_industry:
        industry_options = filter_options(candidate_industry(row) for row in rows)
        industry_control = (
            f'<label for="candidate-filter-industry"><span>{industry_label}</span>'
            '<select id="candidate-filter-industry" name="candidate_filter_industry" data-candidate-industry>'
            f'<option value="">{all_label}</option>{industry_options}</select></label>'
        )
    toolbar_class = (
        "candidate-toolbar has-industry" if has_industry else "candidate-toolbar"
    )
    return (
        f'<div class="{toolbar_class}">'
        f'<label for="candidate-search"><span>{search_label}</span>'
        '<input id="candidate-search" name="candidate_search" type="search" data-candidate-search '
        f"{i18n_attr('placeholder', search_placeholder_en, search_placeholder_zh, language)}></label>"
        f'<label for="candidate-filter-board"><span>{board_label}</span>'
        f'<select id="candidate-filter-board" name="candidate_filter_board" data-candidate-board><option value="">{all_label}</option>{board_options}</select></label>'
        f"{industry_control}"
        f'<label for="candidate-filter-level"><span>{level_label}</span>'
        f'<select id="candidate-filter-level" name="candidate_filter_level" data-candidate-level><option value="">{all_label}</option>{level_options}</select></label>'
        f'<label for="candidate-sort"><span>{sort_label}</span>'
        '<select id="candidate-sort" name="candidate_sort" data-candidate-sort>'
        f'<option value="score">{plain_bilingual("Score", "评分", language)}</option>'
        f'<option value="rank">{plain_bilingual("Rank", "序号", language)}</option>'
        f'</select></label><button type="button" data-candidate-reset>{clear_label}</button></div>'
        '<p class="candidate-toolbar-status" data-candidate-toolbar-status role="status" aria-live="polite"></p>'
    )


def filter_options(values: Any) -> str:
    unique = sorted({str(value) for value in values if str(value)})
    return "".join(
        f'<option value="{esc(value)}">{esc(value)}</option>' for value in unique
    )


def level_filter_options(rows: list[dict[str, Any]], language: str) -> str:
    options = []
    seen = set()
    for row in rows:
        key = level_css_class(row)
        if key in seen:
            continue
        seen.add(key)
        options.append((key, candidate_level(row, language)))
    order = {"high": 0, "medium": 1, "low": 2}
    options.sort(key=lambda item: (order.get(item[0], 99), item[1]))
    return "".join(
        f'<option value="{esc(value)}">{esc(label)}</option>'
        for value, label in options
    )


def candidate_master_table(rows: list[dict[str, Any]], language: str) -> str:
    columns = candidate_master_columns(rows)
    head = "".join(
        f"<th>{candidate_master_header(column, language)}</th>" for column in columns
    )
    body = "".join(
        candidate_master_row(row, index, language, columns=columns)
        for index, row in enumerate(rows)
    )
    footer = candidate_table_footer(len(rows), language)
    sparse_note = candidate_sparse_note(len(rows), language)
    table_class = "master-table has-wide-table" if len(columns) > 7 else "master-table"
    return (
        '<div class="master-list-panel">'
        f"{candidate_master_toolbar(rows, language)}"
        f'<div class="{table_class}"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table>{sparse_note}</div>{footer}</div>"
    )


def candidate_search_placeholder(has_industry: bool, language: str) -> str:
    if has_industry:
        return plain_bilingual(
            "Code / name / board / industry / keyword",
            "代码 / 名称 / 板块 / 行业 / 关键词",
            language,
        )
    return plain_bilingual(
        "Code / name / board / keyword",
        "代码 / 名称 / 板块 / 关键词",
        language,
    )


def candidate_master_columns(rows: list[dict[str, Any]]) -> list[str]:
    columns = ["rank", "symbol", "name", "board"]
    if candidate_column_has_values(rows, "industry"):
        columns.append("industry")
    columns.extend(["score", "level"])
    for column in ("one_year_pct_chg", "market_cap", "pe_ttm", "pb_lf"):
        if candidate_column_has_values(rows, column):
            columns.append(column)
    return columns


def candidate_master_header(column: str, language: str) -> str:
    labels = {
        "rank": ("No.", "序号"),
        "symbol": ("Stock code", "股票代码"),
        "name": ("Stock name", "股票名称"),
        "board": ("Board", "板块"),
        "score": ("Score", "综合评分"),
        "level": ("Level", "观察等级"),
    }
    en, zh = (
        candidate_field_labels(column)
        if column in OPTIONAL_MASTER_COLUMNS
        else labels[column]
    )
    return bilingual(en, zh, language)


def candidate_hidden_field_labels(
    rows: list[dict[str, Any]],
    field_coverage: dict[str, Any] | None,
    language: str,
) -> list[str]:
    return [
        strip_tags(candidate_master_header(column, language))
        for column in OPTIONAL_MASTER_COLUMNS
        if not candidate_optional_column_available(rows, field_coverage, column)
    ]


def candidate_optional_column_available(
    rows: list[dict[str, Any]],
    field_coverage: dict[str, Any] | None,
    column: str,
) -> bool:
    if field_coverage_optional_present(field_coverage, column):
        return True
    return candidate_column_has_values(rows, column)


def field_coverage_optional_present(
    field_coverage: dict[str, Any] | None,
    column: str,
) -> bool:
    if not isinstance(field_coverage, dict):
        return False
    fields = field_coverage.get("fields", {})
    if not isinstance(fields, dict):
        return False
    field = fields.get(column, {})
    if not isinstance(field, dict):
        return False
    try:
        return int(field.get("present_rows", 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def candidate_column_has_values(rows: list[dict[str, Any]], column: str) -> bool:
    return any(candidate_column_has_value(row, column) for row in rows)


def candidate_column_has_value(row: dict[str, Any], column: str) -> bool:
    if column == "industry":
        return display_value(candidate_industry(row))
    return candidate_has_any_field(row, candidate_field_aliases(column))


def candidate_has_any_field(row: dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(display_value(raw_text(row.get(key))) for key in keys)


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
        f"<span>{total_label} <b data-candidate-visible-count>{row_count}</b> / "
        f"<b data-candidate-total-count>{row_count}</b> {rows_label}</span>"
        '<div class="candidate-pager">'
        f'<button type="button" data-candidate-prev>{previous}</button>'
        '<span class="candidate-page-numbers" data-candidate-page-numbers></span>'
        f'<span class="candidate-page-status">{page_label} <b data-candidate-page-current>1</b> / '
        "<b data-candidate-page-total>1</b></span>"
        f'<button type="button" data-candidate-next>{next_page}</button>'
        f'<label for="candidate-page-size">{per_page_label} <select id="candidate-page-size" name="candidate_page_size" data-candidate-page-size>'
        '<option value="10">10</option><option value="25">25</option>'
        '<option value="50">50</option></select></label>'
        "</div></div>"
    )


def candidate_master_row(
    row: dict[str, Any],
    index: int,
    language: str,
    *,
    columns: list[str],
) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = candidate_stock_name(row, symbol, language)
    name_missing_class = " missing" if candidate_stock_name_missing(row, symbol) else ""
    rank = raw_text(row.get("rank")) or str(index + 1)
    level = candidate_level(row, language)
    level_key = level_css_class(row)
    level_en = candidate_level(row, "en")
    level_zh = candidate_level(row, "zh")
    summary = candidate_reason(row, language)
    summary_en = candidate_reason(row, "en")
    summary_zh = candidate_reason(row, "zh")
    risk_label, risk_class = candidate_risk_level(row, language)
    risk_label_en, _ = candidate_risk_level(row, "en")
    risk_label_zh, _ = candidate_risk_level(row, "zh")
    action = candidate_data_note(row, language)
    action_en = candidate_data_note(row, "en")
    action_zh = candidate_data_note(row, "zh")
    industry = candidate_industry(row)
    board = candidate_listing_board(row)
    selected = ' data-selected="true"' if index == 0 else ""
    initial_hidden = " hidden" if index >= 10 else ""
    attrs = candidate_detail_attrs(
        row, rank, level, summary, risk_label, risk_class, action, language
    )
    search = " ".join(
        str(part)
        for part in (
            symbol,
            name,
            board,
            industry,
            level,
            level_key,
            level_en,
            level_zh,
            summary,
            summary_en,
            summary_zh,
            risk_label,
            risk_label_en,
            risk_label_zh,
            action,
            action_en,
            action_zh,
        )
    ).lower()
    score = score_value(row)
    state = {
        "rank": rank,
        "symbol": symbol,
        "name": name,
        "name_missing_class": name_missing_class,
        "board": board,
        "level": level,
        "level_key": level_key,
        "score": score,
    }
    cells = "".join(candidate_master_cell(column, row, state) for column in columns)
    title_en = "Preview row detail"
    title_zh = "预览行详情"
    row_label_en = f"Preview row detail: {rank} {symbol} {name} {board} {score} {level}"
    row_label_zh = f"预览行详情：{rank} {symbol} {name} {board} {score} {level}"
    return (
        '<tr data-candidate-row role="button" tabindex="0" aria-expanded="false" '
        f"{i18n_attr('title', title_en, title_zh, language)} "
        f"{i18n_attr('aria-label', row_label_en, row_label_zh, language)} "
        f'data-rank="{esc(rank)}" data-score="{esc(score_value(row))}" '
        f'data-search="{esc(search)}" data-board="{esc(board)}" data-industry="{esc(industry)}" data-level="{esc(level_key)}" '
        f'data-level-label="{esc(level)}" data-risk="{esc(risk_class)}" data-risk-label="{esc(risk_label)}"{selected}{initial_hidden}{attrs}>'
        f"{cells}</tr>"
    )


def candidate_master_cell(
    column: str,
    row: dict[str, Any],
    state: dict[str, str],
) -> str:
    if column == "rank":
        return (
            '<td class="rank-cell">'
            f'<span class="rank-number"><span class="row-check" aria-hidden="true"></span> {esc(state["rank"])}</span>'
            "</td>"
        )
    if column == "symbol":
        return f'<td><span class="symbol-cell">{esc(state["symbol"])}</span></td>'
    if column == "name":
        return f'<td><strong class="name-cell{state["name_missing_class"]}">{esc(state["name"])}</strong></td>'
    if column == "board":
        return f"<td>{esc(state['board'])}</td>"
    if column == "industry":
        return f"<td>{esc(candidate_industry(row))}</td>"
    if column == "score":
        return f"<td><strong>{esc(state['score'] or '-')}</strong></td>"
    if column == "level":
        return f"<td>{level_badge(state['level'], css_class=state['level_key'])}</td>"
    if column == "one_year_pct_chg":
        return (
            f"<td>{esc(candidate_field(row, ONE_YEAR_FIELD_KEYS, percent=True))}</td>"
        )
    if column == "market_cap":
        return f"<td>{esc(candidate_field(row, MARKET_CAP_FIELD_KEYS))}</td>"
    if column == "pe_ttm":
        return f"<td>{esc(candidate_field(row, PE_FIELD_KEYS))}</td>"
    if column == "pb_lf":
        return f"<td>{esc(candidate_field(row, PB_FIELD_KEYS))}</td>"
    raise ValueError(f"unknown candidate master column: {column}")


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
    name = candidate_stock_name(row, symbol, language)
    fields = {
        "row-title": f"{name} {symbol}",
        "row-symbol": symbol,
        "row-name": name,
        "row-date": raw_text(row.get("date")) or "-",
        "row-board": candidate_listing_board(row),
        "row-industry": candidate_industry(row),
        "row-rank": rank,
        "row-level": level,
        "row-level-class": level_css_class(row),
        "row-score": score_value(row) or "-",
        "row-close": candidate_field(row, ("close", "signal_close", "spot_price")),
        "row-one-year": candidate_field(row, ONE_YEAR_FIELD_KEYS, percent=True),
        "row-market-cap": candidate_field(row, MARKET_CAP_FIELD_KEYS),
        "row-pe": candidate_field(row, PE_FIELD_KEYS),
        "row-pb": candidate_field(row, PB_FIELD_KEYS),
        "row-summary": summary,
        "row-reason": summary,
        "row-risk": risk_label,
        "row-risk-class": risk_class,
        "row-action": action,
        "row-evidence": candidate_evidence(row, language),
        "row-field-availability": candidate_field_availability(row, language),
    }
    return "".join(f' data-{key}="{esc(value)}"' for key, value in fields.items())


def candidate_stock_name(row: dict[str, Any], symbol: str, language: str) -> str:
    name = raw_text(row.get("name")).strip()
    if candidate_stock_name_missing(row, symbol):
        return plain_bilingual("Name not provided", "名称未提供", language)
    return name


def candidate_stock_name_missing(row: dict[str, Any], symbol: str) -> bool:
    name = raw_text(row.get("name")).strip()
    if not name:
        return True
    return name == symbol and not candidate_uses_ticker_as_name(row)


def candidate_field_availability(row: dict[str, Any], language: str) -> str:
    groups = [
        ("Industry", "行业", candidate_industry(row)),
        (
            "1Y change",
            "近一年涨跌幅",
            candidate_field(row, ONE_YEAR_FIELD_KEYS, percent=True),
        ),
        ("Market cap", "市值", candidate_field(row, MARKET_CAP_FIELD_KEYS)),
        ("PE TTM", "PE TTM", candidate_field(row, PE_FIELD_KEYS)),
        ("PB LF", "PB LF", candidate_field(row, PB_FIELD_KEYS)),
    ]
    provided = [
        plain_bilingual(en, zh, language)
        for en, zh, value in groups
        if display_value(value)
    ]
    missing = [
        plain_bilingual(en, zh, language)
        for en, zh, value in groups
        if not display_value(value)
    ]
    if not missing:
        return plain_bilingual(
            "Key display fields are provided in this row.",
            "本行关键展示字段均已提供。",
            language,
        )
    if not provided:
        return plain_bilingual(
            "Industry, 1Y change, market cap, PE TTM, and PB LF are not provided in this source.",
            "本次源数据未提供行业、近一年涨跌幅、市值、PE TTM、PB LF。",
            language,
        )
    return plain_bilingual(
        f"Provided: {', '.join(provided)}. Not provided: {', '.join(missing)}.",
        f"已提供：{'、'.join(provided)}。未提供：{'、'.join(missing)}。",
        language,
    )


def candidate_detail_panel(row: dict[str, Any], language: str) -> str:
    symbol = raw_text(row.get("symbol")) or "-"
    name = candidate_stock_name(row, symbol, language)
    level = candidate_level(row, language)
    summary = candidate_reason(row, language)
    risk_label, risk_class = candidate_risk_level(row, language)
    action = candidate_data_note(row, language)
    evidence = strip_tags(candidate_evidence(row, language))
    date = raw_text(row.get("date")) or "-"
    evidence_html = esc(evidence).replace("\n", "<br>")
    return (
        '<aside class="candidate-detail-panel" data-candidate-detail>'
        f"{candidate_detail_head(name, symbol, date, level, level_css_class(row), language)}"
        '<div class="detail-body">'
        '<div class="detail-main">'
        f"{level_detail_grid(level, level_css_class(row), language)}"
        f"{detail_grid('One-line summary', '一句话摘要', summary, 'detail-summary', language)}"
        f"{detail_grid('Why selected', '入选原因', summary, 'detail-reason', language)}"
        f"{risk_detail_grid(risk_label, risk_class, language)}"
        f"{detail_grid('Report note', '报告提示', action, 'detail-action', language)}"
        "</div>"
        f"{evidence_detail_card(evidence_html, language)}</div>"
        "</aside>"
    )


def candidate_detail_head(
    name: str,
    symbol: str,
    date: str,
    level: str,
    css_class: str,
    language: str,
) -> str:
    action_label = bilingual(
        "View K-line and indicators", "查看 K 线与技术指标", language
    )
    hint_label = bilingual(
        "Single click previews; double click or press Enter again to open K-line.",
        "单击预览；双击或再次按 Enter 打开 K 线。",
        language,
    )
    return (
        '<div class="detail-head">'
        '<div class="detail-head-copy">'
        f"<h3 data-detail-title>{esc(name)} {esc(symbol)}</h3>"
        f"<span data-detail-date>{esc(date)}</span>"
        f'<span class="detail-head-note">{hint_label}</span>'
        "</div>"
        '<div class="detail-head-actions">'
        f"{level_badge(level, attrs=' data-detail-level', css_class=css_class)}"
        f'<button type="button" class="detail-action-button" data-detail-open-stock aria-haspopup="dialog" '
        'aria-controls="stock-detail-dialog" '
        f"{i18n_attr('aria-label', 'View K-line and indicators', '查看 K 线与技术指标', language)} "
        f"{i18n_attr('title', 'View K-line and indicators', '查看 K 线与技术指标', language)}>{action_label}</button>"
        "</div></div>"
    )


def level_detail_grid(level: str, css_class: str, language: str) -> str:
    return (
        '<div class="detail-grid">'
        f"{detail_title('Observation level', '观察等级', language)}"
        f"<p>{level_badge(level, attrs=' data-detail-level', css_class=css_class)}</p></div>"
    )


def risk_detail_grid(risk_label: str, risk_class: str, language: str) -> str:
    return (
        '<div class="detail-grid">'
        f"{detail_title('Risk severity', '风险严重度', language)}"
        f"<p>{risk_badge(risk_label, risk_class, attrs=' data-detail-risk')}</p></div>"
    )


def evidence_detail_card(evidence_html: str, language: str) -> str:
    return (
        '<div class="detail-evidence-card">'
        f"<span>{bilingual('Public evidence', '公开证据', language)}</span>"
        f"<p data-detail-evidence>{evidence_html}</p></div>"
    )


def detail_grid(en: str, zh: str, value: str, attr: str, language: str) -> str:
    safe_value = esc(value).replace("\n", "<br>")
    return (
        f'<div class="detail-grid">{detail_title(en, zh, language)}'
        f"<p data-{attr}>{safe_value}</p></div>"
    )


def detail_title(en: str, zh: str, language: str) -> str:
    return f"<span>{bilingual(en, zh, language)}</span>"


def candidate_stock_dialog(language: str) -> str:
    close_label = bilingual("Close", "关闭", language)
    note = bilingual(
        (
            "K-line uses only the local prices file embedded in this report; "
            f"up to {HTML_CANDLE_SYMBOL_LIMIT} stocks and {HTML_CANDLE_ROWS_LIMIT} rows per stock are embedded. "
            "It is not live market data or fill proof."
        ),
        (
            "K 线仅使用本报告本地行情文件；最多内嵌 "
            f"{HTML_CANDLE_SYMBOL_LIMIT} 只股票、每只 {HTML_CANDLE_ROWS_LIMIT} 行。"
            "不是实时行情或成交证明。"
        ),
        language,
    )
    basis_sections = [
        ("One-line summary", "一句话摘要", "summary"),
        ("Why selected", "入选原因", "reason"),
        ("Field availability", "字段可用性", "field-availability"),
    ]
    risk_sections = [
        ("Risk note", "风险提示", "risk"),
        ("Report note", "报告提示", "action"),
        ("Public evidence", "公开证据", "evidence"),
    ]
    actions_title = bilingual("Useful actions", "常用操作", language)
    copy_label = bilingual("Copy summary", "复制摘要", language)
    board_filter_label = bilingual("Same board", "同板块筛选", language)
    level_filter_label = bilingual("Same level", "同等级筛选", language)
    locate_label = bilingual("Back to row", "回到表格行", language)
    next_title = bilingual("Report tips", "报告提示", language)
    next_items = [
        bilingual(
            "Use the same-board or same-level filters to compare context inside the report.",
            "使用同板块或同等级筛选，在报告内比较上下文。",
            language,
        ),
        bilingual(
            "The static report does not include live quote or tradability checks.",
            "静态报告不包含实时行情或可交易状态检查。",
            language,
        ),
        bilingual(
            "Use the CSV download when you need the raw row fields.",
            "需要原始字段时下载 CSV 查看。",
            language,
        ),
    ]
    next_body = "".join(f"<li>{item}</li>" for item in next_items)
    return (
        '<div class="stock-detail-drawer" data-stock-detail-drawer data-report-modal-root hidden aria-hidden="true">'
        '<section id="stock-detail-dialog" class="stock-dialog" role="dialog" aria-modal="true" aria-labelledby="stock-detail-title">'
        '<div class="stock-dialog-head">'
        '<div><span class="stock-dialog-eyebrow" data-stock-field="board"></span>'
        '<h3 id="stock-detail-title" data-stock-field="title"></h3>'
        '<p><span data-stock-field="date"></span><span data-stock-field="industry"></span></p></div>'
        f'<button type="button" class="stock-dialog-close" data-stock-detail-close {i18n_attr("aria-label", "Close", "关闭", language)}>{close_label}</button>'
        "</div>"
        '<div class="stock-dialog-grid">'
        '<div class="stock-chart-panel">'
        f'<div class="stock-chart-head"><div><strong>{bilingual("K-line Chart", "K 线图", language)}</strong>'
        '<span data-stock-field="candle-range">-</span></div>'
        '<span data-stock-field="candle-count">0</span></div>'
        '<div class="stock-chart-wrap" data-stock-chart-wrap><canvas data-stock-chart></canvas>'
        '<div class="stock-chart-tooltip" data-stock-chart-tooltip hidden></div>'
        '<p class="stock-chart-empty" data-stock-chart-empty hidden></p></div>'
        f'<p class="stock-chart-note">{note}</p></div>'
        '<div class="stock-facts-panel">'
        '<section class="stock-panel-section stock-action-section">'
        f'<h4 class="stock-panel-title">{actions_title}</h4>'
        '<div class="stock-action-grid">'
        f'<button type="button" data-stock-copy>{copy_label}</button>'
        f'<button type="button" data-stock-filter-board>{board_filter_label}</button>'
        f'<button type="button" data-stock-filter-level>{level_filter_label}</button>'
        f'<button type="button" data-stock-locate-row>{locate_label}</button>'
        "</div>"
        '<p class="stock-action-status" data-stock-action-status aria-live="polite"></p>'
        "</section>"
        f"{stock_panel_section('Key metrics', '关键指标', stock_fact_grid(language), language)}"
        f"{stock_panel_section('Technical indicators', '技术指标', stock_technical_panel(language), language)}"
        f"{stock_panel_section('Selection basis', '筛选依据', stock_text_sections(basis_sections, language), language)}"
        f"{stock_panel_section('Risk and evidence', '风险与证据', stock_text_sections(risk_sections, language), language)}"
        '<section class="stock-panel-section stock-next-section">'
        f'<h4 class="stock-panel-title">{next_title}</h4><ol class="stock-next-list">{next_body}</ol>'
        "</section>"
        "</div></div></section></div>"
    )


def stock_technical_panel(language: str) -> str:
    indicators = [
        ("Trend", "趋势", "technical-trend", "trend"),
        ("Momentum", "动量", "technical-momentum", "momentum"),
        ("MA5 / MA20", "MA5 / MA20", "technical-ma-spread", "ma"),
        ("RSI 14", "RSI 14", "technical-rsi", "rsi"),
        ("MACD hist", "MACD 柱", "technical-macd", "macd"),
        ("KDJ", "KDJ", "technical-kdj", "kdj"),
        ("BOLL position", "BOLL 位置", "technical-bollinger", "bollinger"),
        ("ATR 14", "ATR 14", "technical-atr", "atr"),
        ("Volatility 20D", "20日波动", "technical-volatility", "volatility"),
        ("Volume ratio", "量能比", "technical-volume-ratio", "volume"),
        ("20D range", "20日区间", "technical-range", "range"),
        ("20D drawdown", "20日回撤", "technical-drawdown", "drawdown"),
        (
            "Support / pressure",
            "支撑 / 压力",
            "technical-support-pressure",
            "support-pressure",
        ),
    ]
    summary = '<p class="stock-tech-summary" data-stock-field="technical-summary"></p>'
    cards = "".join(
        '<div class="stock-tech-card" data-stock-tech-card="'
        f'{card_key}"><span>{bilingual(en, zh, language)}</span>'
        f'<strong data-stock-field="{field_key}"></strong></div>'
        for en, zh, field_key, card_key in indicators
    )
    note = '<p class="stock-tech-note" data-stock-field="technical-data-quality"></p>'
    return f'{summary}<div class="stock-technical-grid">{cards}</div>{note}'


def stock_panel_section(en: str, zh: str, body: str, language: str) -> str:
    return (
        '<section class="stock-panel-section">'
        f'<h4 class="stock-panel-title">{bilingual(en, zh, language)}</h4>{body}'
        "</section>"
    )


def stock_text_sections(sections: list[tuple[str, str, str]], language: str) -> str:
    return "".join(
        f'<div class="stock-text-section {key}">'
        f'<span>{bilingual(en, zh, language)}</span><p data-stock-field="{key}"></p></div>'
        for en, zh, key in sections
    )


def stock_fact_grid(language: str) -> str:
    primary_facts = [
        ("Stock code", "股票代码", "symbol"),
        ("Stock name", "股票名称", "name"),
        ("Score", "综合评分", "score"),
        ("Level", "观察等级", "level"),
        ("Close", "参考收盘价", "close"),
        ("1Y change", "近一年涨跌幅", "one-year"),
    ]
    secondary_facts = [
        ("Market cap", "市值", "market-cap"),
        ("PE TTM", "PE TTM", "pe"),
        ("PB LF", "PB LF", "pb"),
    ]
    primary_body = "".join(
        f'<div><span>{bilingual(en, zh, language)}</span><strong data-stock-field="{key}"></strong></div>'
        for en, zh, key in primary_facts
    )
    secondary_body = "".join(
        f'<div><span>{bilingual(en, zh, language)}</span><strong data-stock-field="{key}"></strong></div>'
        for en, zh, key in secondary_facts
    )
    return (
        f'<div class="stock-fact-grid primary">{primary_body}</div>'
        f'<div class="stock-fact-grid secondary">{secondary_body}</div>'
    )


def candidate_candle_data_script(candle_rows: dict[str, list[list[Any]]]) -> str:
    data = json.dumps(candle_rows, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    return f'<script type="application/json" data-candidate-candles>{data}</script>'
