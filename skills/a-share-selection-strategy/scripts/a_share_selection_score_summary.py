"""Console summary helpers for A-share selection scoring."""

from __future__ import annotations

import sys
from typing import Any


def print_summary(summary: dict[str, Any], output: str, prefix: str = "OK") -> None:
    parts = [
        f"raw_symbols={summary['raw_symbols']}",
        f"input_symbols={summary['input_symbols']}",
        f"invalid_or_dropped_symbols={summary['invalid_or_dropped_symbols']}",
        f"universe_filtered_symbols={summary['universe_filtered_symbols']}",
        f"market_filtered_symbols={summary['market_filtered_symbols']}",
        f"prefix_allow_filtered_symbols={summary['prefix_allow_filtered_symbols']}",
        f"prefix_excluded_symbols={summary['prefix_excluded_symbols']}",
        f"insufficient_history_symbols={summary['insufficient_history_symbols']}",
        f"scored_symbols={summary['scored_symbols']}",
        f"failed_symbols={summary.get('failed_symbols', 0)}",
        f"threshold_failed_symbols={summary['threshold_failed_symbols']}",
        f"candidates={summary['candidates']}",
    ]
    for key in prediction_disclosure_keys():
        if key in summary:
            parts.append(f"{key}={format_value(summary[key])}")
    if summary.get("effective_empty_result") is not None:
        parts.append(f"effective_empty_result={str(summary['effective_empty_result']).lower()}")
    if summary.get("empty_result_reason"):
        parts.append(f"empty_result_reason={summary['empty_result_reason']}")
    if summary.get("input"):
        parts.append(f"input={summary['input']}")
    if summary.get("turnover_assumption"):
        parts.append(f"turnover_assumption={summary['turnover_assumption']}")
    if summary.get("spot_rows", 0):
        parts.append(f"spot_rows={summary['spot_rows']}")
        parts.append(f"spot_matched_symbols={summary['spot_matched_symbols']}")
    parts.append(f"output={output}")
    print(f"{prefix}: " + " ".join(parts))
    print_detail_lines(summary)


def print_detail_lines(summary: dict[str, Any]) -> None:
    if summary.get("threshold_failures"):
        print(f"INFO: threshold_failures={format_counts(summary['threshold_failures'])}")
    if summary.get("failed_symbol_examples"):
        print(
            "INFO: failed_symbol_examples="
            f"{','.join(summary['failed_symbol_examples'])}"
        )
    if summary.get("insufficient_history_symbol_examples"):
        print(
            "INFO: insufficient_history_symbol_examples="
            f"{','.join(summary['insufficient_history_symbol_examples'])}"
        )
    if summary.get("turnover_assumption"):
        print(
            "WARNING: generic mode: turn/turnover missing; turnover_ratio "
            "component uses a neutral series and no prediction-derived turnover gate is applied",
            file=sys.stderr,
        )
    if summary.get("prediction_source") == "external_unverified":
        print(
            f"INFO: prediction_source={summary['prediction_source']} "
            f"prediction_input_source={summary.get('prediction_input_source', 'unknown')} "
            "prediction_model_executed_by_score_script=false "
            "lightgbm_not_executed_by_this_script=true"
        )


def print_skipped_history_warning(short_symbols: list[str], min_history: int) -> None:
    examples = ", ".join(short_symbols[:10])
    print(
        "WARNING: skipped symbols with insufficient history "
        f"rows (< {min_history}): {examples}",
        file=sys.stderr,
    )


def no_scored_symbols_message(summary: dict[str, Any]) -> str:
    short_examples = ",".join(summary.get("insufficient_history_symbol_examples", []))
    failed_examples = ",".join(summary.get("failed_symbol_examples", []))
    return (
        "no symbols could be scored; "
        f"insufficient_history_symbols={summary.get('insufficient_history_symbols', 0)} "
        f"failed_symbols={summary.get('failed_symbols', 0)} "
        f"insufficient_history_symbol_examples={short_examples} "
        f"failed_symbol_examples={failed_examples}"
    )


def format_counts(counts: dict[str, int]) -> str:
    return ",".join(f"{name}:{count}" for name, count in sorted(counts.items()))


def prediction_disclosure_keys() -> list[str]:
    return [
        "prediction_source",
        "prediction_input_source",
        "prediction_model_executed_by_score_script",
        "lightgbm_not_executed_by_this_script",
    ]


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
