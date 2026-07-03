"""Candidate preview rendering for the local A-share HTML report."""

from __future__ import annotations

from typing import Any

from a_share_selection_candidate_fields import candidate_field_value_present
from a_share_selection_html_candidate_helpers import (
    candidate_industry,
    candidate_listing_board,
    candidate_uses_ticker_as_name,
    plain_bilingual,
)
from a_share_selection_html_format import (
    bilingual,
    esc,
    format_numeric,
    localized_phrase_html,
    raw_text,
)


MASTER_DETAIL_PREVIEW_LIMIT = 5
STRATEGY_MATCH_HIGH = 0.75
STRATEGY_MATCH_MEDIUM = 0.55


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
    display_name = stock_name_or_missing(row, name, symbol, language)
    missing_class = " missing" if stock_name_missing(row, name, symbol) else ""
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
    display_name = stock_name_or_missing(row, name, symbol, language)
    missing_class = " missing" if stock_name_missing(row, name, symbol) else ""
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


def stock_name_or_missing(
    row: dict[str, Any],
    name: str,
    symbol: str,
    language: str,
) -> str:
    if stock_name_missing(row, name, symbol):
        return plain_bilingual("Name not provided", "名称未提供", language)
    return name


def stock_name_missing(row: dict[str, Any], name: str, symbol: str) -> bool:
    normalized_name = str(name).strip()
    normalized_symbol = str(symbol).strip()
    if not normalized_name:
        return True
    return normalized_name == normalized_symbol and not candidate_uses_ticker_as_name(row)


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


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
