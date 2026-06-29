"""Candidate row helpers for the local A-share HTML report."""

from __future__ import annotations

import re
from typing import Any

from a_share_selection_html_format import (
    esc,
    format_numeric,
    localized_phrase,
    raw_text,
)
from a_share_selection_symbols import listing_board


STRATEGY_MATCH_HIGH = 0.75
STRATEGY_MATCH_MEDIUM = 0.55


def candidate_level(row: dict[str, Any], language: str) -> str:
    try:
        score = float(raw_text(score_value(row)))
    except ValueError:
        return plain_bilingual("Needs check", "待确认", language)
    if score >= STRATEGY_MATCH_HIGH:
        return plain_bilingual("High", "高", language)
    if score >= STRATEGY_MATCH_MEDIUM:
        return plain_bilingual("Medium", "中等", language)
    return plain_bilingual("Low", "偏低", language)


def score_value(row: dict[str, Any]) -> str:
    return format_numeric(row.get("total_score", ""), 3, "")


def candidate_reason(row: dict[str, Any], language: str) -> str:
    text = raw_text(row.get("key_reasons")).strip()
    if not text:
        return plain_bilingual(
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
        pair = localized_phrase(text)
        return plain_bilingual(pair["en"], pair["zh"], language)
    en = "; ".join(label[0] for label in labels)
    zh = "；".join(label[1] for label in labels)
    return plain_bilingual(en, zh, language)


def candidate_data_note(row: dict[str, Any], language: str) -> str:
    if not display_value(raw_text(row.get("actual_data_date"))):
        return plain_bilingual("Data date or live quote is not included.", "未包含数据日期或实时行情。", language)
    if not display_value(raw_text(row.get("cash_budget"))):
        return plain_bilingual("Quote, news, and liquidity are outside this static report.", "行情、公告和流动性不在本静态报告内。", language)
    return plain_bilingual("Sizing fields are local report data, not broker orders.", "资金字段是本地报告数据，不是券商订单。", language)


def candidate_evidence(row: dict[str, Any], language: str) -> str:
    parts = []
    date = raw_text(row.get("date"))
    if display_value(date):
        parts.append(f"{plain_bilingual('Signal date', '信号日期', language)}: {date}")
    close = format_numeric(row.get("close", ""), 4, "")
    if display_value(close):
        parts.append(f"{plain_bilingual('Reference close', '参考收盘价', language)}: {close}")
    source = raw_text(row.get("source_type"))
    if display_value(source):
        parts.append(f"{plain_bilingual('Source type', '来源类型', language)}: {source}")
    fallback = plain_bilingual("See CSV fields for row evidence.", "查看 CSV 字段获得行级证据。", language)
    return "\n".join(parts) if parts else fallback


def candidate_risk_level(row: dict[str, Any], language: str) -> tuple[str, str]:
    risk = raw_text(row.get("risk_notes")).lower()
    if any(token in risk for token in ("high volatility", "rsi near overheated", "missing tradable volume", "高波动")):
        return plain_bilingual("High risk", "高风险", language), "high"
    if risk and "no major configured risk flag" not in risk:
        return plain_bilingual("Attention", "注意", language), "attention"
    return plain_bilingual("Notice", "提示", language), "notice"


def display_value(value: Any) -> bool:
    text = raw_text(value).strip().lower()
    return text not in {"", "-", "nan", "none", "unknown", "not_used", "not_verified"}


def plain_bilingual(en: str, zh: str, language: str) -> str:
    return zh if language == "zh" else en


def level_badge(label: str, attrs: str = "", css_class: str = "") -> str:
    classes = "level-badge"
    if css_class:
        classes = f"{classes} {css_class}"
    return f'<span class="{classes}"{attrs}>{esc(label)}</span>'


def risk_badge(label: str, css_class: str, attrs: str = "") -> str:
    return f'<span class="risk-badge {esc(css_class)}"{attrs}>{esc(label)}</span>'


def level_css_class(row: dict[str, Any]) -> str:
    try:
        score = float(raw_text(score_value(row)))
    except ValueError:
        return "low"
    if score >= STRATEGY_MATCH_HIGH:
        return "high"
    if score >= STRATEGY_MATCH_MEDIUM:
        return "medium"
    return "low"


def candidate_industry(row: dict[str, Any]) -> str:
    for key in ("spot_industry", "industry", "sector", "sw_industry", "申万行业"):
        value = raw_text(row.get(key)).strip()
        if display_value(value):
            return value
    return "-"


def candidate_listing_board(row: dict[str, Any]) -> str:
    value = raw_text(row.get("listing_board")).strip()
    if display_value(value):
        return value
    return listing_board(row.get("symbol"), row.get("market", ""))


def candidate_field(row: dict[str, Any], keys: tuple[str, ...], *, percent: bool = False) -> str:
    for key in keys:
        value = raw_text(row.get(key)).strip()
        if not display_value(value):
            continue
        if percent:
            formatted = format_numeric(value, 2, "%")
            return formatted or "-"
        formatted = format_numeric(value, 2, "")
        return formatted or value
    return "-"


def candidate_field_notice_needed(rows: list[dict[str, Any]]) -> bool:
    keys = (
        "spot_industry",
        "industry",
        "sector",
        "sw_industry",
        "pct_chg_1y",
        "one_year_pct_chg",
        "market_cap_billion",
        "market_cap_cny_billion",
        "pe_ttm",
        "peTTM",
        "pb_lf",
        "pbLF",
    )
    return any(not any(raw_text(row.get(key)).strip() for key in keys) for row in rows)


def candidate_entry_button_text(row_count: int, language: str) -> str:
    if row_count <= 5:
        return plain_bilingual("View table below", "查看下方完整表", language)
    return plain_bilingual("Open complete candidate table", "打开完整候选表", language)


def candidate_entry_body(row_count: int, language: str) -> str:
    if row_count <= 5:
        return plain_bilingual(
            "All current watchlist rows are shown below with sorting, filters, and row details.",
            "当前观察名单数量不多，下方已经展示完整候选表，并支持排序、筛选和行详情。",
            language,
        )
    return plain_bilingual(
        "The preview shows the watchlist Top 5. Open the full table below to browse all rows with sorting and filters.",
        "当前展示为观察池预览（Top 5），完整候选表包含全部筛选结果。可在下方查看完整数据，支持排序与筛选。",
        language,
    )


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
