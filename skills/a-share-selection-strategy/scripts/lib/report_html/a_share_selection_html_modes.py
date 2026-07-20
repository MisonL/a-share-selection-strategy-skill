"""Mode explanation helpers for the local A-share HTML report."""

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

from lib.a_share_selection_run_state import is_synthetic_demo, step_executed
from lib.report_html.a_share_selection_html_format import bilingual, i18n


def is_demo_summary(summary: dict[str, Any]) -> bool:
    metadata = summary.get("input_metadata", {})
    return isinstance(metadata, dict) and is_synthetic_demo(metadata)


def report_title_key(summary: dict[str, Any]) -> str:
    return "demo_report_title" if is_demo_summary(summary) else "report_title"


def report_heading_key(summary: dict[str, Any], status: str) -> str:
    if not is_demo_summary(summary):
        return f"{status}_report"
    return f"{status}_demo_report"


def report_status_key(summary: dict[str, Any], status: str) -> str:
    if status not in {"completed", "failed"}:
        return "unknown_demo_report" if is_demo_summary(summary) else "status_unknown"
    if is_demo_summary(summary):
        return f"{status}_demo_report"
    return f"status_{status}"


def candidate_count_key(summary: dict[str, Any]) -> str:
    return "demo_candidates_count" if is_demo_summary(summary) else "candidates_count"


def candidate_section_key(summary: dict[str, Any]) -> str:
    return "demo_candidates" if is_demo_summary(summary) else "candidates"


def scoring_method_key(summary: dict[str, Any]) -> str:
    if mode_unresolved(summary):
        return "unresolved_method_value"
    if generic_mode_not_ready(summary):
        return "generic_not_completed_method_value"
    return (
        "prediction_method_value"
        if summary.get("prediction_mode")
        else "generic_method_value"
    )


def prediction_status_key(summary: dict[str, Any]) -> str:
    if not summary.get("prediction_mode"):
        return "prediction_not_run_value"
    if prediction_columns_missing(summary):
        return "prediction_missing_input_value"
    if prediction_scoring_consumed_input(summary) or prediction_scoring_completed(
        summary
    ):
        return "prediction_input_value"
    return "prediction_not_consumed_input_value"


def boundary_summary(summary: dict[str, Any], language: str) -> str:
    if mode_unresolved(summary):
        key = "unresolved_boundary_summary"
    elif generic_mode_not_ready(summary):
        key = "generic_not_scored_boundary_summary"
    elif generic_scoring_failed_at_strict_gate(summary):
        key = "generic_strict_failed_boundary_summary"
    elif not summary.get("prediction_mode"):
        key = "generic_boundary_summary"
    elif prediction_columns_missing(summary):
        key = "prediction_missing_boundary_summary"
    elif prediction_scoring_failed_after_consumption(summary):
        key = "prediction_strict_failed_boundary_summary"
    elif prediction_mode_not_ready(summary):
        key = "prediction_not_scored_boundary_summary"
    else:
        key = "prediction_boundary_summary"
    return i18n(key, language)


def mode_reason(summary: dict[str, Any], language: str) -> str:
    if mode_unresolved(summary):
        return i18n("why_unresolved_value", language)
    if generic_mode_not_ready(summary):
        return i18n("why_generic_not_scored_value", language)
    if generic_scoring_failed_at_strict_gate(summary):
        return i18n("why_generic_strict_failed_value", language)
    if summary.get("prediction_mode"):
        if prediction_columns_missing(summary):
            return i18n("why_prediction_missing_columns_value", language)
        if prediction_scoring_failed_after_consumption(summary):
            return i18n("why_prediction_strict_failed_value", language)
        if prediction_mode_not_ready(summary):
            return i18n("why_prediction_not_scored_value", language)
        return i18n("why_prediction_ready_value", language)
    reason = str(summary.get("mode_decision_reason", ""))
    requested_mode = str(summary.get("requested_mode", ""))
    if "missing_prediction_columns" in reason:
        groups = missing_prediction_groups(summary)
        if groups == ["prediction"]:
            return i18n("why_generic_missing_prediction_value", language)
        return missing_prediction_groups_reason(groups, language)
    if "history_fetch_inputs_do_not_include_prediction" in reason:
        return i18n("why_generic_history_fetch_value", language)
    if requested_mode == "generic":
        return i18n("why_generic_requested_value", language)
    return i18n("why_generic_auto_value", language)


def missing_prediction_groups_reason(groups: list[str], language: str) -> str:
    if not groups:
        return i18n("why_generic_auto_value", language)
    group_text = ", ".join(groups)
    en = (
        "Input is missing required prediction contract groups: "
        f"{group_text}. Auto mode used technical gates."
    )
    zh = f"输入缺少预测评分契约字段组：{group_text}；auto 因此使用技术门禁。"
    return bilingual(en, zh, language)


def limit_key(summary: dict[str, Any]) -> str:
    if mode_unresolved(summary):
        return "unresolved_limits"
    if generic_mode_not_ready(summary):
        return "generic_not_scored_limits"
    if generic_scoring_failed_at_strict_gate(summary):
        return "generic_strict_failed_limits"
    if not summary.get("prediction_mode"):
        return "generic_limits"
    if prediction_columns_missing(summary):
        return "prediction_missing_limits"
    if prediction_scoring_failed_after_consumption(summary):
        return "prediction_strict_failed_limits"
    if prediction_mode_not_ready(summary):
        return "prediction_not_scored_limits"
    return "prediction_limits"


def prediction_columns_missing(summary: dict[str, Any]) -> bool:
    return bool(
        missing_prediction_groups(summary)
        or summary.get("missing_prediction_requirement")
    )


def mode_unresolved(summary: dict[str, Any]) -> bool:
    return str(summary.get("mode", "")) == "unresolved" or (
        str(summary.get("mode_decision", "")) == "unresolved"
    )


def generic_mode_not_ready(summary: dict[str, Any]) -> bool:
    return (
        not bool(summary.get("prediction_mode"))
        and run_failed(summary)
        and not generic_scoring_failed_at_strict_gate(summary)
    )


def generic_scoring_failed_at_strict_gate(summary: dict[str, Any]) -> bool:
    return (
        not bool(summary.get("prediction_mode"))
        and scoring_step_failed(summary)
        and scoring_emitted_summary(summary)
    )


def run_failed(summary: dict[str, Any]) -> bool:
    return str(summary.get("status", "")) == "failed" or bool(
        summary.get("failed_steps", [])
    )


def scoring_step_failed(summary: dict[str, Any]) -> bool:
    for step in summary.get("_html_steps", []):
        if step.get("step") != "score":
            continue
        if not step_executed(step):
            return False
        allowed = step.get("allowed_returncodes", [])
        return step.get("returncode") not in allowed
    return False


def scoring_emitted_summary(summary: dict[str, Any]) -> bool:
    for step in summary.get("_html_steps", []):
        if step.get("step") != "score":
            continue
        return "ERROR_SUMMARY:" in str(step.get("stdout", ""))
    return False


def prediction_mode_not_ready(summary: dict[str, Any]) -> bool:
    return bool(summary.get("prediction_mode")) and (
        prediction_columns_missing(summary)
        or not (
            prediction_scoring_completed(summary)
            or prediction_scoring_consumed_input(summary)
        )
    )


def prediction_scoring_failed_after_consumption(summary: dict[str, Any]) -> bool:
    return bool(summary.get("prediction_mode")) and (
        prediction_scoring_consumed_input(summary)
        and not prediction_scoring_completed(summary)
    )


def prediction_scoring_completed(summary: dict[str, Any]) -> bool:
    for step in summary.get("_html_steps", []):
        if step.get("step") != "score":
            continue
        if not step_executed(step):
            return False
        allowed = step.get("allowed_returncodes", [])
        return step.get("returncode") in allowed
    return False


def prediction_scoring_consumed_input(summary: dict[str, Any]) -> bool:
    for step in summary.get("_html_steps", []):
        if step.get("step") != "score":
            continue
        stdout = str(step.get("stdout", ""))
        return (
            "prediction_input_source=external_input" in stdout
            or "prediction_source=external_unverified" in stdout
        )
    return False


def missing_prediction_groups(summary: dict[str, Any]) -> list[str]:
    groups = summary.get("missing_prediction_column_groups")
    if isinstance(groups, list):
        return [str(group) for group in groups if str(group)]
    reason = str(summary.get("mode_decision_reason", ""))
    prefix = "missing_prediction_columns:"
    if prefix not in reason:
        return []
    group_text = reason.split(prefix, 1)[1].split(";", 1)[0]
    return [group.strip() for group in group_text.split(",") if group.strip()]
