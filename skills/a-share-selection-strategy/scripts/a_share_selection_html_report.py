"""HTML report rendering for the local A-share selection runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from a_share_selection_html_assets import CSS, JS
from a_share_selection_html_data import (
    HTML_DIAGNOSTIC_ROWS_LIMIT,
    HTML_REPORT_ROWS_LIMIT,
    candidate_candle_rows,
    candidate_rows,
    diagnostic_rows,
    full_candidate_rows,
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
    candidates_panel,
    collapsible_details,
    diagnostics_panel,
    evidence_list,
    empty_key_for,
    hero,
    insight_drawer,
    limited_table,
    report_overview,
    appendix_title,
    run_numbers_panel,
    scoring_fields_panel,
    section,
    steps_table,
    technical_details,
    zero_candidates_message,
)
from a_share_selection_html_modes import (
    report_status_key,
    report_title_key,
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
            '<link rel="icon" href="data:,">',
            title_tag(report_summary, initial_language),
            f'<meta name="description" content="{esc(report_description(report_summary, initial_language))}">',
            f"<style>{CSS}</style>",
            "</head>",
            "<body>",
            '<main class="page" data-report-content>',
            hero(report_summary, initial_language),
            *body_sections,
            "</main>",
            insight_drawer(initial_language),
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
    all_candidates, all_candidates_truncated = full_candidate_rows(summary)
    diagnostics, diagnostics_truncated = diagnostic_rows(summary)
    candle_rows = candidate_candle_rows(summary, all_candidates)
    return [
        section(
            "",
            report_overview(summary, language, candidates),
            section_id="result-section",
            extra_class="dashboard-section",
        ),
        section(
            "",
            candidates_panel(
                candidates,
                all_candidates,
                all_candidates_truncated,
                DISPLAY_CANDIDATE_COLUMNS,
                language,
                truncated=candidates_truncated,
                limit=HTML_REPORT_ROWS_LIMIT,
                csv_path=summary.get("candidates_output", ""),
                candle_rows=candle_rows,
                empty_key=empty_key_for(summary),
                empty_html=zero_candidates_message(summary, language),
            ),
            section_id="watchlist-section",
            extra_class="watchlist-section",
        ),
        section(
            "",
            boundary_panel(summary, language, candidates),
            section_id="confirmation-section",
            extra_class="notice-section",
        ),
        section(
            appendix_title(language),
            report_appendix(
                summary,
                manifest,
                candidates,
                all_candidates_truncated,
                candidates_truncated,
                diagnostics,
                diagnostics_truncated,
                language,
            ),
            section_id="appendix-section",
        ),
    ]


def report_appendix(
    summary: dict[str, Any],
    manifest: dict[str, Any],
    candidates: list[dict[str, Any]],
    all_candidates_truncated: bool,
    candidates_truncated: bool,
    diagnostics: list[dict[str, Any]],
    diagnostics_truncated: bool,
    language: str,
) -> str:
    return (
        run_numbers_panel(summary, language)
        + scoring_fields_panel(summary, language)
        + technical_details(summary, language)
        + candidate_detail_table(
            summary,
            candidates,
            all_candidates_truncated,
            candidates_truncated,
            language,
        )
        + diagnostics_panel(
            summary,
            diagnostics,
            DISPLAY_DIAGNOSTIC_COLUMNS,
            language,
            truncated=diagnostics_truncated,
            limit=HTML_DIAGNOSTIC_ROWS_LIMIT,
            csv_path=summary.get("diagnostics_output", ""),
        )
        + collapsible_details(
            i18n("pipeline_steps_hint", language),
            steps_table(manifest.get("steps", []), language),
            "pipeline-detail",
        )
        + collapsible_details(
            i18n("evidence_paths", language),
            evidence_list(summary, language),
            "evidence-detail",
        )
    )


def candidate_detail_table(
    summary: dict[str, Any],
    candidates: list[dict[str, Any]],
    candidates_truncated_full: bool,
    truncated: bool,
    language: str,
) -> str:
    title = "Detailed table" if language == "en" else "明细表"
    hint = (
        "Cards are for normal reading. This table keeps the original fields for reference."
        if language == "en"
        else "卡片用于普通阅读；这张表保留原始字段，供参考。"
    )
    label = "Show details" if language == "en" else "展开明细表"
    limit_hint = ""
    if candidates_truncated_full:
        limit_hint = (
            "<p>Only the first 25 rows are embedded here to keep the HTML usable. See the CSV for the full result.</p>"
            if language == "en"
            else "<p>这里仅嵌入前 25 行以保证 HTML 可用，完整结果请查看 CSV。</p>"
        )
    content = (
        f'<div class="detail-table-heading"><strong>{title}</strong><p>{hint}</p>{limit_hint}</div>'
        + limited_table(
            candidates,
            DISPLAY_CANDIDATE_COLUMNS,
            language,
            truncated=truncated or candidates_truncated_full,
            limit=HTML_REPORT_ROWS_LIMIT,
            csv_path=summary.get("candidates_output", ""),
            empty_key=empty_key_for(summary),
            empty_html=zero_candidates_message(summary, language),
        )
    )
    return collapsible_details(label, content, "candidate-detail-table")


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
    return f"{title} - {status_text}"


def report_description(summary: dict[str, Any], language: str) -> str:
    title = localized_text(report_title_key(summary), language)
    if language == "zh":
        return f"{title}，用于查看候选股票、筛选依据、风险提示和本地生成的静态报告。"
    return f"{title} for reviewing candidates, screening rationale, risk notes, and the locally generated static report."

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
