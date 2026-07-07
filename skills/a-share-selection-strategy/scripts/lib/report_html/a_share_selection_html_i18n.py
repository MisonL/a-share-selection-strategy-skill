"""Language helpers for the local A-share HTML report."""

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


from collections.abc import Mapping
import os


SUPPORTED_HTML_REPORT_LANGUAGES = ("auto", "zh", "en")
HTML_LANG = {"zh": "zh-CN", "en": "en"}
TEXT = {
    "brand": {"en": "A-Share Selection Strategy", "zh": "A 股选股策略"},
    "report_title": {"en": "A-Share Selection Report", "zh": "A 股选股报告"},
    "demo_report_title": {
        "en": "A-Share Selection Demo Report",
        "zh": "A 股选股 Demo 报告",
    },
    "completed_report": {"en": "Completed report", "zh": "已完成报告"},
    "failed_report": {"en": "Failed report", "zh": "失败报告"},
    "unknown_report": {"en": "Run report", "zh": "运行报告"},
    "completed_demo_report": {"en": "Completed demo report", "zh": "已完成 demo 报告"},
    "failed_demo_report": {"en": "Failed demo report", "zh": "失败 demo 报告"},
    "unknown_demo_report": {"en": "Demo report", "zh": "Demo 报告"},
    "status_completed": {"en": "Completed", "zh": "已完成"},
    "status_failed": {"en": "Failed", "zh": "失败"},
    "status_unknown": {"en": "Unknown", "zh": "未知"},
    "mode": {"en": "Mode", "zh": "模式"},
    "candidates_count": {"en": "Candidates", "zh": "候选数"},
    "demo_candidates_count": {"en": "Demo candidates", "zh": "合成 demo 候选"},
    "run_summary": {"en": "Run Summary", "zh": "运行摘要"},
    "mode_boundary": {"en": "Scoring Notes", "zh": "评分说明"},
    "candidates": {"en": "Candidates", "zh": "候选结果"},
    "demo_candidates": {"en": "Demo candidates", "zh": "合成 demo 候选"},
    "diagnostics": {"en": "Diagnostics", "zh": "诊断明细"},
    "pipeline_steps": {"en": "Pipeline Steps", "zh": "执行步骤"},
    "pipeline_steps_hint": {
        "en": "Show command-level execution details",
        "zh": "查看命令级执行细节",
    },
    "evidence_paths": {"en": "Evidence Paths", "zh": "证据路径"},
    "prices_rows": {"en": "Prices Rows", "zh": "行情行数"},
    "candidate_rows": {"en": "Candidate Rows", "zh": "候选行数"},
    "diagnostic_rows": {"en": "Diagnostic Rows", "zh": "诊断行数"},
    "spot_rows": {"en": "Spot Rows", "zh": "实时快照行数"},
    "spot_matches": {"en": "Spot Matches", "zh": "快照匹配数"},
    "history_symbols": {"en": "History Symbols", "zh": "历史评分标的数"},
    "failed_steps": {"en": "Failed Steps", "zh": "失败步骤数"},
    "requested_mode": {"en": "Requested mode", "zh": "请求模式"},
    "mode_decision": {"en": "Mode decision", "zh": "模式决策"},
    "consumes_prediction_columns": {
        "en": "Consumed prediction columns",
        "zh": "是否已消费预测列",
    },
    "prediction_input_source": {"en": "Prediction input source", "zh": "预测输入来源"},
    "requested_prediction_input_source": {
        "en": "Requested prediction input source",
        "zh": "请求的预测输入来源",
    },
    "prediction_model_executed_by_runner": {
        "en": "Prediction model executed by runner",
        "zh": "总控是否执行预测模型",
    },
    "source_scope": {"en": "Source scope", "zh": "数据来源范围"},
    "source_type": {"en": "Source type", "zh": "来源类型"},
    "real_market_data": {"en": "Real market data", "zh": "真实行情数据"},
    "scenario": {"en": "Scenario", "zh": "场景"},
    "raw_spot_rows": {"en": "Raw spot rows", "zh": "原始快照行数"},
    "filtered_spot_rows": {"en": "Filtered spot rows", "zh": "过滤后快照行数"},
    "selected_symbol_count": {"en": "Selected history symbols", "zh": "历史评分样本数"},
    "max_history_symbols": {"en": "Max history symbols", "zh": "历史取数上限"},
    "allow_partial_history": {"en": "Allow partial history", "zh": "允许历史部分成功"},
    "history_failed_symbols": {
        "en": "History failed symbols",
        "zh": "历史取数失败标的",
    },
    "history_requested_end_date": {
        "en": "Requested history end date",
        "zh": "请求历史截止日",
    },
    "history_actual_date_max": {
        "en": "History actual latest date",
        "zh": "历史实际最新日期",
    },
    "history_end_date_has_rows": {
        "en": "History end date has rows",
        "zh": "截止日是否有行情行",
    },
    "requested_as_of_date": {"en": "Requested as-of date", "zh": "请求 as-of 日期"},
    "actual_data_date": {"en": "Actual data date", "zh": "实际数据日期"},
    "as_of_date_observed": {"en": "As-of date observed", "zh": "as-of 日期是否有行情"},
    "prediction_source": {"en": "Prediction source", "zh": "预测来源"},
    "prediction_input_source": {"en": "Prediction input source", "zh": "预测输入来源"},
    "prediction_model_quality_scope": {
        "en": "Prediction model quality scope",
        "zh": "预测模型质量边界",
    },
    "volume_unit_verification": {
        "en": "Volume unit verification",
        "zh": "成交量单位校验",
    },
    "cash_budget": {"en": "Cash budget", "zh": "现金预算"},
    "lot_size": {"en": "Lot size", "zh": "每手股数"},
    "capital_model": {"en": "Capital model", "zh": "资金模型"},
    "signal_close": {"en": "Signal close", "zh": "信号收盘价"},
    "cash_slot": {"en": "Cash slot", "zh": "分配现金槽"},
    "quantity": {"en": "Quantity", "zh": "数量"},
    "cash_reserved": {"en": "Cash reserved", "zh": "预留现金"},
    "notional": {"en": "Notional", "zh": "名义金额"},
    "weight": {"en": "Weight", "zh": "权重"},
    "unallocated": {"en": "Unallocated", "zh": "未分配"},
    "sizing_claim_boundary": {"en": "Sizing claim boundary", "zh": "资金分配声明边界"},
    "unknown_value": {"en": "Unknown", "zh": "未知"},
    "machine_boundary": {"en": "Machine boundary", "zh": "机器边界"},
    "scoring_method": {"en": "Scoring Method", "zh": "评分方式"},
    "why_this_mode": {"en": "Why this mode", "zh": "为什么用这个模式"},
    "prediction_status": {"en": "External Prediction Data", "zh": "外部预测数据"},
    "data_scope": {"en": "Data Scope", "zh": "数据范围"},
    "limits": {
        "en": "What this report can and cannot prove",
        "zh": "这份报告能说明什么",
    },
    "technical_details": {"en": "Technical details", "zh": "技术细节"},
    "technical_details_hint": {
        "en": "Show raw machine fields used by automation and reviews.",
        "zh": "查看自动化和审查使用的原始机器字段。",
    },
    "generic_method_value": {
        "en": "Generic technical scoring",
        "zh": "通用技术评分",
    },
    "generic_not_completed_method_value": {
        "en": "Generic scoring not completed",
        "zh": "通用评分未完成",
    },
    "unresolved_method_value": {
        "en": "Mode unresolved",
        "zh": "模式未解析",
    },
    "prediction_method_value": {
        "en": "External prediction-column scoring",
        "zh": "外部预测列评分",
    },
    "prediction_not_run_value": {
        "en": "Not executed in this run",
        "zh": "本次未执行",
    },
    "prediction_input_value": {
        "en": "Read from input columns",
        "zh": "读取输入列",
    },
    "prediction_missing_input_value": {
        "en": "Missing required prediction columns",
        "zh": "缺少必需预测列",
    },
    "prediction_not_consumed_input_value": {
        "en": "Not consumed because scoring did not complete",
        "zh": "评分未完成，未消费预测列",
    },
    "why_generic_missing_prediction_value": {
        "en": "Input has no prediction column, so auto mode used technical gates.",
        "zh": "输入没有预测列，auto 因此使用技术门禁。",
    },
    "why_generic_history_fetch_value": {
        "en": "Fetched price history does not include prediction columns.",
        "zh": "历史行情取数不包含预测列。",
    },
    "why_generic_requested_value": {
        "en": "Generic mode was requested explicitly.",
        "zh": "本次明确请求通用模式。",
    },
    "why_generic_auto_value": {
        "en": "Auto mode selected the generic technical path.",
        "zh": "auto 选择了通用技术路径。",
    },
    "why_generic_not_scored_value": {
        "en": "Generic mode was selected, but validation or scoring did not complete.",
        "zh": "本次已选择通用模式，但校验或评分未完成。",
    },
    "why_generic_strict_failed_value": {
        "en": "Generic scoring reached a strict-gate failure.",
        "zh": "通用评分已执行，但 strict gate 失败。",
    },
    "why_unresolved_value": {
        "en": "The run failed before mode resolution or scoring completed.",
        "zh": "运行在模式解析或评分完成前失败。",
    },
    "why_prediction_ready_value": {
        "en": "Input includes the required external prediction columns.",
        "zh": "输入包含所需的外部预测列。",
    },
    "why_prediction_missing_columns_value": {
        "en": "Prediction mode was requested, but required prediction columns are missing.",
        "zh": "本次请求外部预测列评分，但输入缺少必需预测列。",
    },
    "why_prediction_not_scored_value": {
        "en": "Prediction mode was requested, but validation or scoring did not complete.",
        "zh": "本次请求外部预测列评分，但校验或评分未完成。",
    },
    "why_prediction_strict_failed_value": {
        "en": "Input includes the required external prediction columns; scoring reached a strict-gate failure.",
        "zh": "输入包含所需外部预测列；评分已执行，但 strict gate 失败。",
    },
    "generic_scope_value": {
        "en": "Local price file only",
        "zh": "仅本地行情文件",
    },
    "unresolved_scope_value": {
        "en": "Source scope unresolved",
        "zh": "数据来源范围未解析",
    },
    "external_scope_value": {
        "en": "Local file plus external snapshot or fetch",
        "zh": "本地文件加外部快照或取数",
    },
    "generic_boundary_summary": {
        "en": "The run filtered available A-share price data with deterministic short-term technical gates and ranked the rows that passed.",
        "zh": "本次使用确定性的短线技术门禁筛选可用的 A 股行情，并对通过门禁的行排序。",
    },
    "generic_not_scored_boundary_summary": {
        "en": "Generic mode was selected, but the failed run did not complete scoring, filtering, or ranking.",
        "zh": "本次已选择通用模式，但失败运行没有完成评分、筛选或排序。",
    },
    "generic_strict_failed_boundary_summary": {
        "en": "Generic scoring reached the score step and applied configured technical gates, but strict gate failed before a completed candidate output.",
        "zh": "通用评分已到达 score 步骤并应用配置的技术门禁，但 strict gate 失败，候选输出未完成。",
    },
    "unresolved_boundary_summary": {
        "en": "The run failed before a scoring mode was resolved, so the report cannot claim generic or prediction-derived scoring.",
        "zh": "运行在评分模式解析前失败，因此报告不能声称已执行通用或外部预测列评分。",
    },
    "prediction_boundary_summary": {
        "en": "The run ranked candidates from prediction columns that were already present in the input data.",
        "zh": "本次使用输入数据中已经存在的预测列对候选结果排序。",
    },
    "prediction_missing_boundary_summary": {
        "en": "Prediction mode was requested, but validation failed before scoring because required prediction columns were missing.",
        "zh": "本次请求外部预测列评分，但因缺少必需预测列，校验在评分前失败。",
    },
    "prediction_not_scored_boundary_summary": {
        "en": "Prediction mode was requested, but the run did not reach a successful scoring step.",
        "zh": "本次请求外部预测列评分，但运行没有到达成功的评分步骤。",
    },
    "prediction_strict_failed_boundary_summary": {
        "en": "Prediction mode reached scoring and consumed supplied prediction columns, but strict gates failed before a completed candidate output.",
        "zh": "本次已进入外部预测列评分并消费输入预测列，但 strict gate 失败，候选输出未完成。",
    },
    "generic_limits": {
        "en": "It can explain which rows passed the configured gates. It cannot prove model prediction quality, live full-market coverage, future returns, or real tradability.",
        "zh": "它能说明哪些行通过了已配置门禁；不能证明模型预测质量、实时全市场覆盖、未来收益或真实可交易性。",
    },
    "generic_not_scored_limits": {
        "en": "It can explain only the failed run and written evidence paths. It cannot prove that technical scoring, filtering, ranking, or candidate selection completed.",
        "zh": "它只能说明本次失败运行和已写出的证据路径；不能证明技术评分、筛选、排序或候选选择已完成。",
    },
    "generic_strict_failed_limits": {
        "en": "It can explain that configured technical gates were applied and why the strict gate failed. It cannot prove candidate output completion, future returns, or real tradability.",
        "zh": "它能说明配置的技术门禁已被应用以及 strict gate 失败原因；不能证明候选输出已完成、未来收益或真实可交易性。",
    },
    "unresolved_limits": {
        "en": "It can explain only the early failure and written evidence paths. It cannot prove that scoring, filtering, ranking, or prediction consumption happened.",
        "zh": "它只能说明早期失败和已写出的证据路径；不能证明已发生评分、筛选、排序或预测列消费。",
    },
    "prediction_limits": {
        "en": "It can explain how supplied prediction columns were consumed. It cannot prove the upstream model quality or that this runner trained or executed a model.",
        "zh": "它能说明已提供的预测列如何被消费；不能证明上游模型质量，也不能说明本总控训练或执行了模型。",
    },
    "prediction_missing_limits": {
        "en": "It can explain the validation failure only. It did not consume prediction columns, rank candidates, or prove upstream model quality.",
        "zh": "它只能说明校验失败原因；本次没有消费预测列、没有候选排序，也不能证明上游模型质量。",
    },
    "prediction_not_scored_limits": {
        "en": "It can explain the failed run only. It did not consume prediction columns or rank candidates.",
        "zh": "它只能说明本次运行失败；本次没有消费预测列，也没有候选排序。",
    },
    "prediction_strict_failed_limits": {
        "en": "It can explain that supplied prediction columns were consumed and why the strict gate failed. It cannot prove upstream model quality or that this runner trained or executed a model.",
        "zh": "它能说明已提供的预测列被消费以及 strict gate 失败原因；不能证明上游模型质量，也不能说明本总控训练或执行了模型。",
    },
    "summary_json": {"en": "Summary JSON", "zh": "摘要 JSON"},
    "manifest_json": {"en": "Manifest JSON", "zh": "Manifest JSON"},
    "candidates_csv": {"en": "Candidates CSV", "zh": "候选 CSV"},
    "diagnostics_csv": {"en": "Diagnostics CSV", "zh": "诊断 CSV"},
    "prices": {"en": "Prices", "zh": "行情文件"},
    "spot_csv": {"en": "Spot CSV", "zh": "实时快照 CSV"},
    "spot_metadata_json": {"en": "Spot Metadata JSON", "zh": "实时快照元数据 JSON"},
    "selected_symbols_json": {"en": "Selected Symbols JSON", "zh": "历史样本 JSON"},
    "history_metadata_json": {"en": "History Metadata JSON", "zh": "历史元数据 JSON"},
    "empty": {"en": "No rows written for this run.", "zh": "本次运行未写出相关行。"},
    "written_empty": {
        "en": "Output file was written, but it contains zero rows.",
        "zh": "输出文件已写出，但包含 0 行。",
    },
    "no_table_rows": {
        "en": "No rows to display for this completed run.",
        "zh": "本次完成运行没有可展示行。",
    },
    "empty_steps": {
        "en": "No pipeline steps recorded for this report.",
        "zh": "本报告没有记录执行步骤。",
    },
    "rank": {"en": "Rank", "zh": "排名"},
    "symbol": {"en": "Symbol", "zh": "代码"},
    "name": {"en": "Name", "zh": "名称"},
    "date": {"en": "Date", "zh": "日期"},
    "close": {"en": "Close", "zh": "收盘价"},
    "spot_price": {"en": "Spot Price", "zh": "实时价"},
    "spot_pct_chg": {"en": "Spot Change", "zh": "实时涨跌幅"},
    "total_score": {"en": "Total Score", "zh": "总分"},
    "key_reasons": {"en": "Key Reasons", "zh": "核心理由"},
    "risk_notes": {"en": "Risk Notes", "zh": "风险提示"},
    "selection_status": {"en": "Selection Status", "zh": "入选状态"},
    "short_reason": {"en": "Short Reason", "zh": "简要原因"},
    "failure_reason": {"en": "Reason", "zh": "原因"},
    "failed_thresholds": {"en": "Failed Thresholds", "zh": "失败门禁"},
    "failed_thresholds_zh": {"en": "Failed Thresholds ZH", "zh": "失败门禁中文"},
    "step": {"en": "Step", "zh": "步骤"},
    "returncode": {"en": "Return Code", "zh": "退出码"},
    "allowed": {"en": "Allowed Codes", "zh": "允许退出码"},
    "stderr": {"en": "stderr", "zh": "标准错误"},
}


def initial_report_language(
    requested: str,
    environ: Mapping[str, str] | None = None,
) -> str:
    if requested not in SUPPORTED_HTML_REPORT_LANGUAGES:
        raise ValueError(f"unsupported html report language: {requested}")
    if requested == "auto":
        return environment_language(environ)
    return requested


def environment_language(environ: Mapping[str, str] | None = None) -> str:
    values = environ if environ is not None else os.environ
    for name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        lang = language_from_value(values.get(name, ""))
        if lang:
            return lang
    return "en"


def language_from_value(value: str) -> str:
    for token in value.replace("_", "-").split(":"):
        lowered = token.strip().lower()
        if lowered.startswith("zh"):
            return "zh"
        if lowered.startswith("en"):
            return "en"
    return ""


def html_document_lang(language: str) -> str:
    return HTML_LANG[language]


def localized_text(key: str, language: str, fallback: str | None = None) -> str:
    pair = text_pair(key, fallback)
    return pair.get(language, key)


def text_pair(key: str, fallback: str | None = None) -> dict[str, str]:
    names = TEXT.get(key) or TEXT.get(fallback or "")
    if not names:
        return {"en": key, "zh": key}
    return {"en": names.get("en", key), "zh": names.get("zh", key)}
