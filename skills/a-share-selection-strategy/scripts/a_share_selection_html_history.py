"""History selection fields for the local A-share HTML report."""

from __future__ import annotations

from typing import Any

from a_share_selection_html_format import i18n


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
        (i18n("selected_symbol_count", language), selection.get("selected_symbol_count", "")),
        (i18n("max_history_symbols", language), selection.get("max_history_symbols", "")),
        (i18n("allow_partial_history", language), selection.get("allow_partial_history", "")),
        (
            i18n("history_failed_symbols", language),
            selection.get("history_metadata_failed_symbol_count", ""),
        ),
        (i18n("history_requested_end_date", language), selection.get("requested_end_date", "")),
        (
            i18n("history_actual_date_max", language),
            selection.get("history_metadata_actual_date_max", ""),
        ),
        (
            i18n("history_end_date_has_rows", language),
            selection.get("history_metadata_end_date_has_rows", ""),
        ),
    ]
