"""History selection fields for the local A-share HTML report."""

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


from typing import Any

from lib.report_html.a_share_selection_html_format import i18n


def history_selection_fields(
    summary: dict[str, Any],
    language: str,
) -> list[tuple[str, Any]]:
    selection = summary.get("history_selection", {})
    if not isinstance(selection, dict) or not selection:
        return []
    return [
        (i18n("raw_spot_rows", language), selection.get("raw_spot_rows", "")),
        (i18n("filtered_spot_rows", language), selection.get("filtered_spot_rows", "")),
        (
            i18n("selected_symbol_count", language),
            selection.get("selected_symbol_count", ""),
        ),
        (
            i18n("max_history_symbols", language),
            selection.get("max_history_symbols", ""),
        ),
        (
            i18n("allow_partial_history", language),
            selection.get("allow_partial_history", ""),
        ),
        ("history_partial_result", selection.get("history_partial_result", "")),
        ("history_output_written", selection.get("history_output_written", "")),
        ("history_token_configured", selection.get("history_token_configured", "")),
        ("history_fields", selection.get("history_fields", "")),
        (
            "history_request_interval_seconds",
            selection.get("history_request_interval_seconds", ""),
        ),
        ("history_limit", selection.get("history_limit", "")),
        ("history_max_pages", selection.get("history_max_pages", "")),
        ("history_adjust", selection.get("history_adjust", "")),
        ("history_adjustflag", selection.get("history_adjustflag", "")),
        (
            i18n("history_failed_symbols", language),
            selection.get("history_metadata_failed_symbol_count", ""),
        ),
        ("history_empty_symbol_count", selection.get("history_empty_symbol_count", "")),
        ("history_empty_symbols", selection.get("history_empty_symbols", "")),
        (
            "history_possibly_truncated_symbol_count",
            selection.get("history_possibly_truncated_symbol_count", ""),
        ),
        (
            "history_possibly_truncated_symbols",
            selection.get("history_possibly_truncated_symbols", ""),
        ),
        (
            "history_unprocessed_symbol_count",
            selection.get("history_unprocessed_symbol_count", ""),
        ),
        (
            "history_unprocessed_symbols",
            selection.get("history_unprocessed_symbols", ""),
        ),
        (
            "history_rate_limit_budget_exhausted",
            selection.get("history_rate_limit_budget_exhausted", ""),
        ),
        (
            "history_rate_limit_exhaustion_reason",
            selection.get("history_rate_limit_exhaustion_reason", ""),
        ),
        ("history_invalid_rows", selection.get("history_invalid_rows", "")),
        (
            "history_dropped_invalid_rows",
            selection.get("history_dropped_invalid_rows", ""),
        ),
        ("history_non_trading_rows", selection.get("history_non_trading_rows", "")),
        (
            "history_tradestatus_missing_rows",
            selection.get("history_tradestatus_missing_rows", ""),
        ),
        (
            i18n("history_requested_end_date", language),
            selection.get("requested_end_date", ""),
        ),
        (
            i18n("history_actual_date_max", language),
            selection.get("history_metadata_actual_date_max", ""),
        ),
        (
            "history_metadata_symbols_reached_end_date_count",
            selection.get("history_metadata_symbols_reached_end_date_count", ""),
        ),
        (
            "history_metadata_all_symbols_reached_end_date",
            selection.get("history_metadata_all_symbols_reached_end_date", ""),
        ),
        (
            i18n("history_end_date_has_rows", language),
            selection.get("history_metadata_end_date_has_rows", ""),
        ),
        (
            "history_metadata_fallback_error_count",
            selection.get("history_metadata_fallback_error_count", ""),
        ),
        (
            "history_metadata_fallback_errors",
            selection.get("history_metadata_fallback_errors", ""),
        ),
        (
            "history_metadata_symbol_providers",
            selection.get("history_metadata_symbol_providers", ""),
        ),
    ]
