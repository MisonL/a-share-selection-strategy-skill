"""HTML report rendering for the local A-share selection runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from a_share_selection_html_assets import CSS, JS
from a_share_selection_html_data import (
    HTML_DIAGNOSTIC_ROWS_LIMIT,
    HTML_REPORT_ROWS_LIMIT,
    candidate_rows,
    diagnostic_rows,
)
from a_share_selection_html_format import esc, i18n
from a_share_selection_html_i18n import (
    html_document_lang,
    initial_report_language,
    localized_text,
)
from a_share_selection_html_sections import (
    DISPLAY_CANDIDATE_COLUMNS,
    DISPLAY_DIAGNOSTIC_COLUMNS,
    boundary_panel,
    collapsible_details,
    evidence_list,
    hero,
    limited_table,
    metric_grid,
    section,
    steps_table,
)
from a_share_selection_html_modes import (
    candidate_section_key,
    report_status_key,
    report_title_key,
    scoring_method_key,
)


def write_html_report(
    *,
    summary: dict[str, Any],
    manifest: dict[str, Any],
    output_path: Path,
    language: str = "auto",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    remove_stale_report_path(output_path)
    output_path.write_text(render_report(summary, manifest, language=language), encoding="utf-8")


def remove_stale_report_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        raise IsADirectoryError(f"stale report path is a directory: {path}")
    path.unlink()


def render_report(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    language: str = "auto",
) -> str:
    initial_language = initial_report_language(language)
    report_summary = dict(summary)
    report_summary["_html_steps"] = manifest.get("steps", [])
    body_sections = report_sections(report_summary, manifest, initial_language)
    return "\n".join(
        [
            "<!doctype html>",
            html_tag(language, initial_language),
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            title_tag(report_summary, initial_language),
            f"<style>{CSS}</style>",
            "</head>",
            "<body>",
            '<main class="page">',
            hero(report_summary, initial_language),
            *body_sections,
            "</main>",
            f"<script>{JS}</script>",
            "</body>",
            "</html>",
            "",
        ]
    )


def report_sections(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    language: str,
) -> list[str]:
    candidates, candidates_truncated = candidate_rows(summary)
    diagnostics, diagnostics_truncated = diagnostic_rows(summary)
    return [
        section(i18n("run_summary", language), metric_grid(summary, language)),
        section(i18n("mode_boundary", language), boundary_panel(summary, language)),
        section(
            i18n(candidate_section_key(summary), language),
            limited_table(
                candidates,
                DISPLAY_CANDIDATE_COLUMNS,
                language,
                truncated=candidates_truncated,
                limit=HTML_REPORT_ROWS_LIMIT,
                csv_path=summary.get("candidates_output", ""),
            ),
        ),
        section(
            i18n("diagnostics", language),
            limited_table(
                diagnostics,
                DISPLAY_DIAGNOSTIC_COLUMNS,
                language,
                truncated=diagnostics_truncated,
                limit=HTML_DIAGNOSTIC_ROWS_LIMIT,
                csv_path=summary.get("diagnostics_output", ""),
            ),
        ),
        section(
            i18n("pipeline_steps", language),
            collapsible_details(
                i18n("pipeline_steps_hint", language),
                steps_table(manifest.get("steps", []), language),
            ),
        ),
        section(i18n("evidence_paths", language), evidence_list(summary, language)),
    ]


def html_tag(requested_language: str, initial_language: str) -> str:
    return (
        f'<html lang="{html_document_lang(initial_language)}" '
        f'data-lang="{initial_language}" data-lang-mode="{esc(requested_language)}">'
    )


def title_tag(summary: dict[str, Any], language: str) -> str:
    en_title = report_title(summary, "en")
    zh_title = report_title(summary, "zh")
    return (
        f'<title data-i18n-title-en="{esc(en_title)}" '
        f'data-i18n-title-zh="{esc(zh_title)}">'
        f"{esc(zh_title if language == 'zh' else en_title)}</title>"
    )


def report_title(summary: dict[str, Any], language: str) -> str:
    status = summary.get("status", "unknown")
    title = localized_text(report_title_key(summary), language)
    status_text = localized_text(report_status_key(summary, str(status)), language)
    mode = localized_text(scoring_method_key(summary), language)
    return f"{title} - {status_text} - {mode}"
