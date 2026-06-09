"""Cell formatting helpers for the local A-share HTML report."""

from __future__ import annotations

import html
import json
import math
import re
from typing import Any

from a_share_selection_diagnostic_labels import THRESHOLD_LABELS_ZH
from a_share_selection_html_i18n import text_pair


NUMERIC_FORMATS = {
    "close": (4, ""),
    "spot_price": (4, ""),
    "spot_pct_chg": (2, "%"),
    "total_score": (3, ""),
    "cash_budget": (2, ""),
    "lot_size": (0, ""),
    "signal_close": (4, ""),
    "cash_slot": (2, ""),
    "quantity": (0, ""),
    "cash_reserved": (2, ""),
    "notional": (2, ""),
    "weight": (6, ""),
}
LONG_TEXT_COLUMNS = {"key_reasons", "risk_notes", "short_reason", "failure_reason", "stderr"}
LOCALIZED_COLUMNS = {
    "key_reasons",
    "risk_notes",
    "short_reason",
    "failure_reason",
    "selection_status",
}
KEY_DISCLOSURE_COLUMNS = {
    "requested_as_of_date",
    "actual_data_date",
    "as_of_date_observed",
    "prediction_source",
    "prediction_input_source",
    "prediction_model_quality_scope",
    "volume_unit_verification",
    "source_type",
    "real_market_data",
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
    "failure_reason",
}
MISSING_FIELD_MARKER = "__missing_field__"
REASON_TRANSLATIONS = {
    "prediction above threshold": {"en": "prediction above threshold", "zh": "预测高于阈值"},
    "positive momentum": {"en": "positive momentum", "zh": "动量为正"},
    "short-term activity": {"en": "short-term activity", "zh": "短线活跃"},
    "acceptable volatility": {"en": "acceptable volatility", "zh": "波动率可接受"},
    "rsi in range": {"en": "rsi in range", "zh": "RSI 处于合理区间"},
    "passed configured filters": {"en": "passed configured filters", "zh": "通过配置过滤器"},
    "high volatility": {"en": "high volatility", "zh": "高波动"},
    "rsi near overheated": {"en": "rsi near overheated", "zh": "RSI 接近过热"},
    "missing tradable volume": {"en": "missing tradable volume", "zh": "缺少可交易成交量"},
    "no major configured risk flag": {
        "en": "no major configured risk flag",
        "zh": "未触发主要配置风险",
    },
    "通过全部阈值并进入候选": {
        "en": "Passed all gates and entered candidates",
        "zh": "通过全部阈值并进入候选",
    },
    "通过阈值但受输出数量限制": {
        "en": "Passed gates but capped by output limit",
        "zh": "通过阈值但受输出数量限制",
    },
    "通过全部阈值但受候选数上限影响未入选": {
        "en": "Passed all gates but capped by candidate limit",
        "zh": "通过全部阈值但受候选数上限影响未入选",
    },
    "价格高于上限": {"en": "Price is above the configured limit", "zh": "价格高于上限"},
    "成交额不足": {"en": "Trading amount is below the configured limit", "zh": "成交额不足"},
    "换手率不足": {"en": "Turnover is below the configured limit", "zh": "换手率不足"},
    "ST标的": {"en": "ST stock", "zh": "ST标的"},
    "停牌或不可交易": {"en": "Suspended or not tradable", "zh": "停牌或不可交易"},
    "一字板": {"en": "One-word limit board", "zh": "一字板"},
}
THRESHOLD_LABELS_EN = {
    "exclude_one_word_bar": "One-word limit board",
    "exclude_st": "ST stock",
    "max_close": "Price is above the configured limit",
    "max_rsi": "RSI is above the configured limit",
    "max_volatility": "Volatility is above the configured limit",
    "min_amount": "Trading amount is below the configured limit",
    "min_close": "Price is below the configured limit",
    "min_momentum_score": "Momentum score is below the configured limit",
    "min_prediction_score": "Prediction score is below the configured limit",
    "min_rsi": "RSI is below the configured limit",
    "min_score": "Score is below the configured limit",
    "min_total_score": "Total score is below the configured limit",
    "min_trend_score": "Trend score is below the configured limit",
    "min_turn": "Turnover is below the configured limit",
    "min_volume": "Volume is below the configured limit",
    "require_tradestatus": "Suspended or not tradable",
}
THRESHOLD_TRANSLATIONS = {
    key: {"en": THRESHOLD_LABELS_EN.get(key, key), "zh": label}
    for key, label in THRESHOLD_LABELS_ZH.items()
}
THRESHOLD_TRANSLATIONS["min_score"] = {
    "en": THRESHOLD_LABELS_EN["min_score"],
    "zh": "总分不足",
}
STATUS_TRANSLATIONS = {
    "入选": {"en": "Selected", "zh": "入选"},
    "通过阈值但未入选": {"en": "Passed gates but not selected", "zh": "通过阈值但未入选"},
    "未通过阈值": {"en": "Rejected by gates", "zh": "未通过阈值"},
}


def table_cell(value: Any, column: str, language: str) -> str:
    css_class = ' class="text-cell"' if column in LONG_TEXT_COLUMNS else ""
    title = attr_text(cell_title(value, column, language))
    if missing_field(value):
        content = i18n("unknown_value", language)
    elif isinstance(value, dict) and {"display", "title"} <= value.keys():
        content = esc(value.get("display", ""))
    elif column in NUMERIC_FORMATS:
        content = esc(format_numeric(value, *NUMERIC_FORMATS[column]))
    elif column in LOCALIZED_COLUMNS:
        content = localized_cell(value, language)
    else:
        content = esc(value)
    return f'<td{css_class} title="{title}">{content}</td>'


def failure_reason(row: dict[str, Any]) -> dict[str, str] | str:
    thresholds_zh = str(row.get("failed_thresholds_zh", "")).strip()
    thresholds = str(row.get("failed_thresholds", "")).strip()
    if thresholds:
        return threshold_reason(thresholds, thresholds_zh)
    short_reason = str(row.get("short_reason", "")).strip()
    if short_reason:
        return localized_phrase(short_reason)
    if thresholds_zh:
        return localized_phrase(thresholds_zh)
    return ""


def threshold_reason(thresholds: str, thresholds_zh: str) -> dict[str, str]:
    keys = [item.strip() for item in thresholds.split(";") if item.strip()]
    fallback_parts = split_reason_parts(thresholds_zh)
    translated = [
        threshold_part_reason(key, fallback_parts[index] if index < len(fallback_parts) else "")
        for index, key in enumerate(keys)
    ]
    return {
        "en": "; ".join(pair["en"] for pair in translated),
        "zh": "；".join(pair["zh"] for pair in translated),
    }


def threshold_part_reason(key: str, fallback_zh: str) -> dict[str, str]:
    translated = THRESHOLD_TRANSLATIONS.get(key)
    if translated:
        return translated
    if fallback_zh:
        return localized_phrase(fallback_zh)
    return {"en": key, "zh": key}


def split_reason_parts(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;；]", value) if part.strip()]


def localized_cell(value: Any, language: str) -> str:
    if isinstance(value, dict):
        return bilingual(str(value.get("en", "")), str(value.get("zh", "")), language)
    return localized_phrase_html(str(value), language)


def localized_phrase_html(value: str, language: str) -> str:
    pair = localized_phrase(value)
    return bilingual(pair["en"], pair["zh"], language)


def localized_phrase(value: str) -> dict[str, str]:
    parts = [part.strip() for part in value.split(";") if part.strip()]
    if not parts:
        return {"en": value, "zh": value}
    en_parts = [phrase_translation(part, "en") for part in parts]
    zh_parts = [phrase_translation(part, "zh") for part in parts]
    return {"en": "; ".join(en_parts), "zh": "；".join(zh_parts)}


def phrase_translation(value: str, language: str) -> str:
    translated = REASON_TRANSLATIONS.get(value)
    if translated:
        return translated[language]
    for pair in THRESHOLD_TRANSLATIONS.values():
        if value in pair.values():
            return pair[language]
    status = STATUS_TRANSLATIONS.get(value)
    if status:
        return status[language]
    return value


def i18n(key: str, language: str, fallback: str | None = None) -> str:
    names = text_pair(key, fallback)
    return bilingual(names.get("en", key), names.get("zh", key), language)


def bilingual(en: str, zh: str, language: str = "zh") -> str:
    text = zh if language == "zh" else en
    return (
        f'<span data-i18n-en="{esc(en)}" data-i18n-zh="{esc(zh)}">'
        f"{esc(text)}</span>"
    )


def format_numeric(value: Any, digits: int, suffix: str) -> str:
    text = raw_text(value)
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    if not math.isfinite(number):
        return "-"
    if suffix.strip() == "%":
        return f"{number:.{digits}f}%"
    return f"{number:.{digits}f}"


def display_with_title(*, display: Any, title: Any) -> dict[str, str]:
    return {"display": raw_text(display), "title": raw_text(title)}


def cell_title(value: Any, column: str, language: str) -> str:
    if missing_field(value):
        return str(value.get("title", ""))
    if isinstance(value, dict) and {"display", "title"} <= value.keys():
        return str(value.get("title", ""))
    if column in NUMERIC_FORMATS:
        return raw_text(value)
    if column in LOCALIZED_COLUMNS:
        return localized_cell_text(value, language)
    return raw_text(value)


def localized_cell_text(value: Any, language: str) -> str:
    if isinstance(value, dict):
        if {"display", "title"} <= value.keys():
            return str(value.get("display", ""))
        return str(value.get(language, ""))
    return localized_phrase(value)[language]


def raw_text(value: Any) -> str:
    if missing_field(value):
        return ""
    if isinstance(value, dict) and {"display", "title"} <= value.keys():
        return str(value.get("display", ""))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def esc(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return html.escape(str(value), quote=True)


def attr_text(value: Any) -> str:
    return esc(value).replace("\n", "&#10;").replace("\r", "")


def missing_key_disclosure_value(column: str) -> dict[str, str]:
    return {MISSING_FIELD_MARKER: column, "title": f"missing field: {column}"}


def missing_field(value: Any) -> bool:
    return isinstance(value, dict) and value.get(MISSING_FIELD_MARKER) is not None

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
