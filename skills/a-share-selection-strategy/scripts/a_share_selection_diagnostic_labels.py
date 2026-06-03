"""Presentation labels for A-share selection diagnostics."""

from __future__ import annotations


THRESHOLD_LABELS_ZH = {
    "min_total_score": "综合评分不足",
    "min_momentum_score": "动量不足",
    "min_rsi": "RSI过低",
    "max_rsi": "RSI过热",
    "max_volatility": "波动率过高",
    "min_volume": "成交量不足",
    "min_amount": "成交额不足",
    "min_turn": "换手率不足",
    "min_close": "价格低于下限",
    "max_close": "价格高于上限",
    "exclude_st": "ST标的",
    "require_tradestatus": "停牌或不可交易",
    "exclude_one_word_bar": "一字板",
    "min_prediction_score": "预测分不足",
    "min_trend_score": "趋势分不足",
}


def failed_thresholds_zh(failed_thresholds: list[str]) -> str:
    return ";".join(THRESHOLD_LABELS_ZH.get(name, name) for name in failed_thresholds)


def selection_status(selected: bool, passed_thresholds: bool) -> str:
    if selected:
        return "入选"
    if passed_thresholds:
        return "通过阈值但未入选"
    return "未通过阈值"


def short_reason(selected: bool, failed_thresholds: list[str]) -> str:
    if selected:
        return "通过全部阈值并进入候选"
    if not failed_thresholds:
        return "通过阈值但受输出数量限制"
    first = THRESHOLD_LABELS_ZH.get(failed_thresholds[0], failed_thresholds[0])
    if len(failed_thresholds) == 1:
        return first
    return f"{first}等{len(failed_thresholds)}项未通过"
