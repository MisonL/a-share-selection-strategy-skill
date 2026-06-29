from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

from a_share_selection_html_report import render_report  # noqa: E402
from html_report_helpers import minimal_summary, read_report, read_summary, report_run  # noqa: E402


class TodayAShareHtmlReportTests(unittest.TestCase):
    def test_auto_language_follows_process_locale(self) -> None:
        with report_run(
            env={"LC_ALL": "", "LC_MESSAGES": "", "LANGUAGE": "", "LANG": "zh_CN.UTF-8"}
        ) as result:
            summary = read_summary(result.output)
            report = read_report(result.output)

        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual("auto", summary["html_report_language"])
        self.assertEqual("zh", summary["html_report_initial_language"])
        self.assertIn('<html lang="zh-CN" data-lang="zh" data-lang-mode="auto">', report)
        self.assertIn("A 股策略选股报告", report)
        self.assertIn("A 股选股报告 - 已完成", report)
        self.assertIn("流程指标", report)
        self.assertIn("观察池 Top 5 预览", report)
        self.assertIn("使用边界 / 风险提示", report)
        self.assertIn("免责声明", report)
        self.assertIn("报告附录", report)
        self.assertIn("策略和评分字段", report)
        self.assertIn("通用技术评分", report)
        self.assertIn("输入没有预测列，auto 因此使用技术门禁。", report)
        self.assertIn("技术细节", report)
        self.assertIn("机器边界", report)
        self.assertIn("details.technical-details", report)
        self.assertIn("查看命令级执行细节", report)
        self.assertIn("原因", report)
        self.assertIn("近期走势表现符合筛选要求；风险检查没有触发明显拦截", report)
        self.assertIn(">0.613<", report)
        self.assertNotIn(">0.6132124346769261<", report)
        self.assertNotIn(">失败门禁中文<", report)
        self.assertNotIn(">failed_thresholds_zh<", report)
        self.assertIn("<code title=", report)
        self.assertIn(">./summary.json</code>", report)
        self.assertIn(">./run_manifest.json</code>", report)

    def test_can_force_english_initial_language(self) -> None:
        with report_run(
            extra_args=["--html-report-language", "en"],
            env={"LC_ALL": "", "LC_MESSAGES": "", "LANGUAGE": "", "LANG": "zh_CN.UTF-8"},
        ) as result:
            summary = read_summary(result.output)
            report = read_report(result.output)

        self.assertEqual(0, result.code, result.stderr)
        self.assertEqual("en", summary["html_report_language"])
        self.assertEqual("en", summary["html_report_initial_language"])
        self.assertIn('<html lang="en" data-lang="en" data-lang-mode="en">', report)
        self.assertIn("A-share Strategy Selection Report", report)
        self.assertIn("A-Share Selection Report - Completed", report)
        self.assertIn("Pipeline counts", report)
        self.assertIn("Watchlist Top 5 Preview", report)
        self.assertIn("Use boundary / risk reminder", report)
        self.assertIn("Disclaimer", report)
        self.assertIn("Report Appendix", report)
        self.assertIn("Strategy and scoring fields", report)
        self.assertIn("Scoring Method", report)
        self.assertIn("Generic technical scoring", report)
        self.assertIn("Why this mode", report)
        self.assertIn("Input has no prediction column, so auto mode used technical gates.", report)
        self.assertIn("el.open = false", report)
        self.assertIn("const initial = mode === 'auto' ? (saved || generated) : mode", report)
        self.assertIn("aShareSelectionReportLang", report)
        self.assertIn('data-i18n-zh="A 股策略选股报告"', report)
        self.assertIn("Show command-level execution details", report)
        self.assertIn("Reason", report)
        self.assertIn("recent price action looks acceptable; risk checks did not show an obvious rule breach", report)
        self.assertIn(">0.613<", report)
        self.assertNotIn(">0.6132124346769261<", report)
        self.assertIn(">./summary.json</code>", report)

    def test_auto_report_preserves_generated_language_on_first_browser_load(self) -> None:
        with report_run(
            env={"LC_ALL": "", "LC_MESSAGES": "", "LANGUAGE": "", "LANG": "zh_CN.UTF-8"}
        ) as result:
            report = read_report(result.output)

        self.assertEqual(0, result.code, result.stderr)
        self.assertIn('data-lang="zh" data-lang-mode="auto"', report)
        self.assertIn("const generated = root.dataset.lang || 'en'", report)
        self.assertIn("const initial = mode === 'auto' ? (saved || generated) : mode", report)
        self.assertNotIn("browserLang", report)

    def test_can_disable_html_report(self) -> None:
        with report_run(extra_args=["--no-html-report"]) as result:
            summary = read_summary(result.output)
            report_exists = (result.output / "report.html").exists()

        self.assertEqual(0, result.code, result.stderr)
        self.assertFalse(report_exists)
        self.assertTrue(summary["html_report"].endswith("report.html"))
        self.assertFalse(summary["html_report_written"])
        self.assertEqual("auto", summary["html_report_language"])

    def test_steps_keep_full_stderr_in_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "missing.csv")
            report = render_report(
                summary,
                {
                    "steps": [
                        {
                            "step": "score",
                            "returncode": 1,
                            "allowed_returncodes": [0],
                            "stderr": "first error line\nsecond traceback line",
                        }
                    ]
                },
                language="en",
            )

        self.assertIn(">first error line<", report)
        self.assertIn('title="first error line&#10;second traceback line"', report)

    def test_table_truncation_notice_points_to_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            candidates = Path(tmpdir) / "candidates.csv"
            rows = [
                "rank,symbol,name,date,close,spot_price,spot_pct_chg,total_score,key_reasons,risk_notes"
            ]
            rows.extend(
                f"{index},000{index:03d},Name {index},2025-01-01,7.1,,,0.5,positive momentum,"
                for index in range(1, 27)
            )
            candidates.write_text("\n".join(rows) + "\n", encoding="utf-8")
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["candidate_rows"] = 26
            summary["candidates_output"] = str(candidates)
            summary["candidates_output_written"] = True
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("仅展示前 25 行", report)
        self.assertIn("完整结果：./candidates.csv", report)
        self.assertIn("Name 25", report)
        self.assertIn("Name 26", report)
        preview = report.split('<section id="complete-candidates"', 1)[0]
        complete = report.split('<section id="complete-candidates"', 1)[1]
        complete_section = complete.split("</section>", 1)[0]
        self.assertNotIn("Name 26", preview)
        self.assertIn("Name 26", complete)
        self.assertIn("完整候选表", report)
        self.assertIn("data-candidate-master-detail", report)
        self.assertIn("data-candidate-search", report)
        master_table = complete.split('<div class="master-table">', 1)[1]
        rank_10_row = master_table.split('data-rank="10"', 1)[1].split("</tr>", 1)[0]
        rank_11_row = master_table.split('data-rank="11"', 1)[1].split("</tr>", 1)[0]
        self.assertNotIn(" hidden", rank_10_row)
        self.assertIn(" hidden", rank_11_row)
        head = master_table.split("<thead><tr>", 1)[1].split("</tr></thead>", 1)[0]
        self.assertIn("已隐藏本次源数据未提供或整列为空的字段", complete_section)
        self.assertIn("CSV 原始字段仍可下载核查", complete_section)
        toolbar = complete_section.split('<div class="master-table">', 1)[0]
        self.assertNotIn("data-candidate-industry", toolbar)
        self.assertNotIn("行业", head)
        self.assertNotIn("近一年涨跌幅", head)
        self.assertNotIn("市值（亿元）", head)
        self.assertNotIn("PE（TTM）", head)
        self.assertNotIn("PB（LF）", head)

    def test_complete_candidate_table_is_capped_at_one_thousand_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            candidates = Path(tmpdir) / "candidates.csv"
            rows = [
                "rank,symbol,name,date,close,spot_price,spot_pct_chg,total_score,key_reasons,risk_notes"
            ]
            rows.extend(
                f"{index},000{index:03d},Name {index},2025-01-01,7.1,,,0.5,positive momentum,"
                for index in range(1, 1003)
            )
            candidates.write_text("\n".join(rows) + "\n", encoding="utf-8")
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["candidate_rows"] = 1002
            summary["candidates_output"] = str(candidates)
            summary["candidates_output_written"] = True
            report = render_report(summary, {"steps": []}, language="zh")

        complete = report.split('<section id="complete-candidates"', 1)[1]
        audit = report.split("展开明细表", 1)[1]
        self.assertIn("这里仅嵌入前 1000 行", report)
        self.assertIn("这里仅嵌入前 25 行以保证 HTML 可用", audit)
        self.assertNotIn("这里仅嵌入前 1000 行", audit)
        self.assertIn("Name 1000", complete)
        self.assertNotIn("Name 1001", complete)
        self.assertNotIn("Name 1002", complete)
        self.assertIn("完整候选表", report)
        self.assertIn("CSV 备用文件", report)

    def test_complete_candidate_table_shows_available_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "\n".join(
                    [
                        (
                            "rank,symbol,name,listing_board,spot_industry,one_year_pct_chg,"
                            "market_cap_billion,pe_ttm,pb_lf,date,close,total_score,"
                            "key_reasons,risk_notes"
                        ),
                        (
                            "1,000001,Alpha,主板,软件服务,12.345,123.4,18.6,2.1,"
                            "2026-06-17,10.0,0.82,positive momentum,"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 1,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        complete = report.split('<section id="complete-candidates"', 1)[1]
        master_table = complete.split('<div class="master-table has-wide-table">', 1)[1]
        head = master_table.split("<thead><tr>", 1)[1].split("</tr></thead>", 1)[0]
        self.assertIn("data-candidate-industry", complete)
        self.assertIn("行业", head)
        self.assertIn("近一年涨跌幅", head)
        self.assertIn("市值（亿元）", head)
        self.assertIn("PE（TTM）", head)
        self.assertIn("PB（LF）", head)
        self.assertIn(">软件服务</td>", complete)
        self.assertIn(">12.35%</td>", complete)
        self.assertIn(">123.40</td>", complete)
        self.assertIn(">18.60</td>", complete)
        self.assertIn(">2.10</td>", complete)
        self.assertNotIn("已隐藏本次源数据未提供或整列为空的字段", complete)

    def test_report_ignores_stale_csvs_when_outputs_were_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            diagnostics = output / "diagnostics.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,date,close,total_score,key_reasons,risk_notes",
                        "1,000001,Stale Candidate,2025-01-01,7.1,0.8,positive momentum,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        "000002,Stale Diagnostic,7.2,0.2,未通过阈值,价格高于上限,max_close,价格高于上限",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            summary.update(
                {
                    "candidate_rows": 0,
                    "diagnostic_rows": 0,
                    "candidates_output": str(candidates),
                    "diagnostics_output": str(diagnostics),
                    "candidates_output_written": False,
                    "diagnostics_output_written": False,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertNotIn("Stale Candidate", report)
        self.assertNotIn("Stale Diagnostic", report)
        self.assertNotIn("Price is above the configured limit", report)

    def test_report_distinguishes_written_empty_candidates_from_missing_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "rank,symbol,name,date,close,total_score,key_reasons,risk_notes\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 0,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                    "score": {
                        "effective_empty_result": True,
                        "empty_result_reason": "threshold_filtered_all",
                    },
                }
            )

            en_report = render_report(summary, {"steps": []}, language="en")
            zh_report = render_report(summary, {"steps": []}, language="zh")

        self.assertNotIn("No rows written for this run.", en_report)
        self.assertIn("Completed run with zero candidates", en_report)
        self.assertIn("effective_empty_result=true", en_report)
        self.assertNotIn("本次运行未写出相关行。", zh_report)
        self.assertIn("本次成功运行但没有候选", zh_report)

    def test_failed_missing_candidate_output_does_not_claim_successful_empty_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "status": "failed",
                    "candidate_rows": 0,
                    "candidates_output": str(output / "candidates.csv"),
                    "candidates_output_written": False,
                    "score": {
                        "effective_empty_result": True,
                        "empty_result_reason": "threshold_filtered_all",
                    },
                }
            )

            en_report = render_report(summary, {"steps": []}, language="en")
            zh_report = render_report(summary, {"steps": []}, language="zh")

        self.assertNotIn("Completed run with zero candidates", en_report)
        self.assertNotIn("本次成功运行但没有候选", zh_report)
        self.assertIn("No rows written for this run.", en_report)

    def test_report_shows_history_selection_evidence_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            selected = output / "selected_symbols.json"
            history = output / "history_metadata.json"
            selected.write_text('{"selected_symbols":["000001"]}\n', encoding="utf-8")
            history.write_text('{"failed_symbols":[]}\n', encoding="utf-8")
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "history_symbol_count": 1,
                    "history_selection": {
                        "raw_spot_rows": 4,
                        "filtered_spot_rows": 1,
                        "selected_symbol_count": 1,
                        "max_history_symbols": 1,
                        "allow_partial_history": False,
                        "history_metadata_failed_symbol_count": 0,
                    },
                    "selected_symbols_output": str(selected),
                    "selected_symbols_output_written": True,
                    "history_metadata_output": str(history),
                    "history_metadata_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("History Symbols", report)
        self.assertIn("Raw spot rows", report)
        self.assertIn(">4<", report)
        self.assertIn("Selected history symbols", report)
        self.assertIn(">./selected_symbols.json</code>", report)
        self.assertIn(">./history_metadata.json</code>", report)

    def test_report_shows_spot_evidence_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            spot = output / "spot.csv"
            metadata = output / "spot_metadata.json"
            spot.write_text("symbol,spot_price\n000001,8.1\n", encoding="utf-8")
            metadata.write_text('{"partial_result": true}\n', encoding="utf-8")
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "spot_output": str(spot),
                    "spot_output_written": True,
                    "spot_metadata_output": str(metadata),
                    "spot_metadata_output_written": True,
                }
            )

            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn(">./spot.csv</code>", report)
        self.assertIn(">./spot_metadata.json</code>", report)

    def test_report_shows_score_symbol_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["score"] = {
                "failed_symbol_examples": ["000003", "000004"],
                "insufficient_history_symbol_examples": ["300001"],
            }

            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("failed_symbol_examples", report)
        self.assertIn("000003", report)
        self.assertIn("insufficient_history_symbol_examples", report)
        self.assertIn("300001", report)

    def test_report_discloses_advice_boundary_before_technical_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["advice_boundary"] = (
                "not_investment_advice_not_trade_instruction_not_real_fill_not_return_proof"
            )
            en_report = render_report(summary, {"steps": []}, language="en")
            zh_report = render_report(summary, {"steps": []}, language="zh")

        en_visible = visible_before_technical_details(en_report)
        zh_visible = visible_before_technical_details(zh_report)
        self.assertIn("Not investment advice", en_visible)
        self.assertIn("not a trade instruction", en_visible)
        self.assertIn("not proof of real fills or returns", en_visible)
        self.assertIn("不是投资建议", zh_visible)
        self.assertIn("不是交易指令", zh_visible)
        self.assertIn("不是真实成交或收益证明", zh_visible)

    def test_report_discloses_unknown_local_input_before_technical_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["input_metadata"] = {
                "source_type": "unknown",
                "real_market_data": "unknown",
            }
            en_report = render_report(summary, {"steps": []}, language="en")
            zh_report = render_report(summary, {"steps": []}, language="zh")

        en_visible = visible_before_technical_details(en_report)
        zh_visible = visible_before_technical_details(zh_report)
        self.assertIn("Real market data is unknown", en_visible)
        self.assertIn("local file is not proof of real A-share market data", en_visible)
        self.assertIn("真实行情未知", zh_visible)
        self.assertIn("本地文件不能证明是真实 A 股行情", zh_visible)

    def test_report_discloses_market_label_only_before_technical_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["input_metadata"] = {
                "source": "yfinance",
                "market": "A-share",
                "market_label_only": True,
                "source_claim_boundary": (
                    "market_label_not_source_exchange_or_calendar_proof"
                ),
                "real_market_data": "unknown",
            }
            en_report = render_report(summary, {"steps": []}, language="en")
            zh_report = render_report(summary, {"steps": []}, language="zh")

        en_visible = visible_before_technical_details(en_report)
        zh_visible = visible_before_technical_details(zh_report)
        self.assertIn("market is a label only", en_visible)
        self.assertIn("not exchange or calendar proof", en_visible)
        self.assertIn("market 只是输出标签", zh_visible)
        self.assertIn("不是交易所或交易日历证明", zh_visible)

    def test_report_discloses_input_csv_provenance_in_visible_and_technical_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["input_metadata"] = {
                "source_type": "unknown",
                "real_market_data": "unknown",
            }
            summary["input_csv_provenance"] = {
                "source_type": "csv_embedded_probe",
                "source_scope": "local_prices_input",
                "real_market_data": False,
                "source_claim_boundary": "csv_internal_fields_not_real_market_gate",
            }
            report = render_report(summary, {"steps": []}, language="en")

        visible = visible_before_technical_details(report)
        technical = report.split('<details class="technical-details">', 1)[1]
        self.assertIn("CSV embedded provenance says real_market_data=false", visible)
        self.assertIn("csv_internal_fields_not_real_market_gate", visible)
        self.assertIn("input_csv_source_type", technical)
        self.assertIn("csv_embedded_probe", technical)
        self.assertIn("input_csv_source_scope", technical)
        self.assertIn("local_prices_input", technical)
        self.assertIn("input_csv_real_market_data", technical)
        self.assertIn("False", technical)
        self.assertIn("input_csv_source_claim_boundary", technical)
        self.assertIn("csv_internal_fields_not_real_market_gate", technical)

    def test_sized_candidates_disclose_local_sizing_boundary_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "\n".join(
                    [
                        (
                            "rank,symbol,name,date,close,total_score,cash_budget,"
                            "lot_size,capital_model,quantity,cash_reserved,notional,"
                            "weight,unallocated,sizing_claim_boundary,key_reasons,risk_notes"
                        ),
                        (
                            "1,000001,Sized,2026-06-05,7.1,0.8,10000,100,"
                            "equal_cash_budget_lot_floor,700,4970,4970,0.497,"
                            "False,local_sizing_not_broker_order,positive momentum,"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 1,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        visible = visible_before_technical_details(report)
        self.assertIn("Local sizing only", visible)
        self.assertIn("not a broker order", visible)
        self.assertIn("Sizing claim boundary", report)
        self.assertIn("local_sizing_not_broker_order", report)

    def test_report_opens_with_plain_language_summary_before_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            write_consumer_candidate_rows(candidates)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 2,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                    "advice_boundary": (
                        "not_investment_advice_not_trade_instruction_not_real_fill_not_return_proof"
                    ),
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn('class="report-overview-grid"', report)
        self.assertIn('class="pipeline-metrics"', report)
        self.assertIn('class="selection-flow-card"', report)
        self.assertIn('class="selection-flow"', report)
        self.assertNotIn('class="reader-guide"', report)
        self.assertIn("2 只股票符合当前策略规则，进入观察清单", report)
        self.assertIn("选股流程", report)
        self.assertIn("观察名单", report)
        self.assertIn("风险提示", report)
        self.assertIn("完整候选表", report)
        self.assertIn("使用边界 / 风险提示", report)
        self.assertIn("把它当作报告中的观察清单", report)
        self.assertIn('<details class="report-details run-metrics">', report)
        self.assertIn('<details class="report-details candidate-detail-table">', report)
        self.assertIn('<details class="report-details diagnostics-detail">', report)
        self.assertIn("运行数字", report)
        self.assertIn("展开明细表", report)
        self.assertIn("门禁诊断", report)
        self.assertLess(report.index('class="selection-flow"'), report.index('class="table-wrap"'))
        self.assertLess(
            report.index('class="candidate-cards"'),
            report.index('<details class="report-details candidate-detail-table">'),
        )
        self.assertLess(
            report.index('class="report-overview-grid"'),
            report.index('<details class="technical-details">'),
        )

    def test_zero_candidate_report_explains_how_to_read_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "rank,symbol,name,date,close,total_score,key_reasons,risk_notes\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 0,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                    "score": {
                        "effective_empty_result": True,
                        "empty_result_reason": "threshold_filtered_all",
                    },
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("无候选 / 数据不完整", report)
        self.assertIn("没有股票符合当前策略规则", report)
        self.assertIn("先确认数据来源和策略范围是不是你想要的", report)
        self.assertIn("本次运行已完成，但没有股票进入观察清单", report)
        self.assertIn('<details class="report-details zero-candidate-details">', report)
        self.assertIn('<details class="report-details diagnostics-detail">', report)

    def test_failed_report_warns_not_to_use_stale_candidate_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "status": "failed",
                    "candidate_rows": 0,
                    "diagnostic_rows": 0,
                    "failed_steps": ["validate"],
                    "candidates_output_written": False,
                    "diagnostics_output_written": False,
                }
            )
            report = render_report(
                summary,
                {
                    "steps": [
                        {
                            "step": "validate",
                            "returncode": 1,
                            "allowed_returncodes": [0],
                            "stderr": "missing close column",
                        }
                    ]
                },
                language="zh",
            )

        self.assertIn("AI Agent 在生成可用观察清单前停止了", report)
        self.assertIn("未完成 / 无可用结果", report)
        self.assertIn("本次失败运行没有可用观察清单", report)
        visible = visible_before_technical_details(report)
        self.assertIn("AI Agent 在生成可用观察清单前停止了", visible)
        self.assertNotIn("&lt;span data-i18n-en=", visible)

    def test_synthetic_demo_boundary_appears_before_top_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            write_consumer_candidate_rows(candidates)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 2,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                    "input_metadata": {
                        "source_type": "synthetic_demo",
                        "scenario": "low-price-ultra-short",
                        "real_market_data": False,
                    },
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        visible = visible_before_technical_details(report)
        self.assertIn("合成 demo 数据；不是真实行情。", visible)
        self.assertNotIn("low-price-ultra-short", visible)
        self.assertIn("使用边界 / 风险提示", visible)
        self.assertLess(report.index("合成 demo 数据；不是真实行情。"), report.index("观察池 Top 5 预览"))

    def test_report_renders_candidate_cards_before_full_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            write_consumer_candidate_rows(candidates)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 2,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn('class="candidate-cards"', report)
        self.assertIn("data-preview-table", report)
        self.assertIn("Watchlist Top 5 Preview", report)
        self.assertIn('class="candidate-open-banner"', report)
        self.assertIn('id="complete-candidates"', report)
        self.assertIn('class="candidate-master-detail"', report)
        self.assertIn("View table below", report)
        self.assertIn("Summary", report)
        self.assertIn("Risk", report)
        self.assertIn("Top 5 are shown first", report)
        self.assertIn(
            '<strong class="stock-anchor">Alpha Tech</strong><span class="stock-code">300001</span>',
            report,
        )
        self.assertNotIn("Cash reserved", report.split('<details class="report-details candidate-detail-table">', 1)[0])
        self.assertLess(report.index('class="candidate-cards"'), report.index('class="table-wrap"'))

    def test_complete_candidate_table_is_viewable_inside_static_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            write_consumer_candidate_rows(candidates)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 2,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        complete = report.split('<section id="complete-candidates"', 1)[1]
        self.assertIn("完整候选表", complete)
        self.assertIn("数据已随 HTML 生成", complete)
        self.assertIn("搜索、筛选、排序", complete)
        self.assertIn("CSV 备用文件", complete)
        self.assertIn('class="candidate-download-link"', complete)
        self.assertIn('href="./candidates.csv" download', complete)
        self.assertIn("下载 CSV", complete)
        self.assertIn("data-candidate-search", complete)
        self.assertIn('id="candidate-search" name="candidate_search"', complete)
        self.assertIn("data-candidate-board", complete)
        self.assertIn('id="candidate-filter-board" name="candidate_filter_board"', complete)
        self.assertIn("data-candidate-industry", complete)
        self.assertIn('id="candidate-filter-industry" name="candidate_filter_industry"', complete)
        self.assertIn("data-candidate-level", complete)
        self.assertIn('id="candidate-filter-level" name="candidate_filter_level"', complete)
        self.assertIn("data-candidate-sort", complete)
        self.assertIn('id="candidate-sort" name="candidate_sort"', complete)
        self.assertIn('id="candidate-page-size" name="candidate_page_size"', complete)
        self.assertIn("data-candidate-row", complete)
        self.assertIn('class="candidate-toolbar has-industry"', complete)
        self.assertIn('role="button" tabindex="0" aria-haspopup="dialog" aria-expanded="false"', complete)
        self.assertIn("data-candidate-detail", complete)
        self.assertIn('class="master-table"', complete)
        self.assertNotIn('class="master-table has-wide-table"', complete)
        self.assertIn("data-row-title", complete)
        self.assertIn('data-row-symbol="300001"', complete)
        self.assertIn('data-row-name="Alpha Tech"', complete)
        self.assertIn('data-row-close="10.00"', complete)
        self.assertIn('<span class="symbol-cell">300001</span>', complete)
        self.assertIn('<strong class="name-cell">Alpha Tech</strong>', complete)
        self.assertIn('class="stock-detail-drawer"', complete)
        self.assertIn("data-stock-detail-drawer", complete)
        self.assertIn('class="stock-dialog-close" data-stock-detail-close', complete)
        self.assertNotIn('class="stock-dialog-close" aria-label=', complete)
        self.assertIn("data-stock-chart", complete)
        self.assertIn("data-candidate-candles", complete)
        self.assertIn("K 线图", complete)
        self.assertIn("常用操作", complete)
        self.assertIn("data-stock-copy", complete)
        self.assertIn("data-stock-filter-board", complete)
        self.assertIn("data-stock-filter-level", complete)
        self.assertIn("data-stock-locate-row", complete)
        self.assertIn("data-stock-action-status", complete)
        self.assertIn("技术指标", complete)
        self.assertIn('class="stock-technical-grid"', complete)
        self.assertIn('data-stock-field="technical-summary"', complete)
        self.assertIn('data-stock-field="technical-trend"', complete)
        self.assertIn('data-stock-field="technical-rsi"', complete)
        self.assertIn('data-stock-field="technical-macd"', complete)
        self.assertIn('data-stock-field="technical-kdj"', complete)
        self.assertIn('data-stock-field="technical-bollinger"', complete)
        self.assertIn('data-stock-field="technical-atr"', complete)
        self.assertIn('data-stock-field="technical-volume-ratio"', complete)
        self.assertIn('data-stock-field="technical-support-pressure"', complete)
        self.assertIn('data-stock-field="technical-data-quality"', complete)
        self.assertIn("报告提示", complete)
        self.assertIn("静态报告不包含实时行情或可交易状态检查。", complete)
        self.assertIn('class="stock-panel-section"', complete)
        self.assertIn('class="stock-panel-title"', complete)
        self.assertIn("关键指标", complete)
        self.assertIn("筛选依据", complete)
        self.assertIn("字段可用性", complete)
        self.assertIn("已提供：行业。未提供：近一年涨跌幅、市值、PE TTM、PB LF。", complete)
        self.assertIn("风险与证据", complete)
        self.assertIn('class="stock-fact-grid primary"', complete)
        self.assertIn('class="stock-fact-grid secondary"', complete)
        self.assertIn('class="stock-text-section summary"', complete)
        self.assertIn('class="stock-text-section reason"', complete)
        self.assertIn('class="stock-text-section field-availability"', complete)
        self.assertIn('class="stock-text-section risk"', complete)
        self.assertIn('class="stock-text-section action"', complete)
        self.assertIn('class="stock-text-section evidence"', complete)
        self.assertEqual(complete.count("data-detail-title"), 1)
        detail = complete.split('data-candidate-detail', 1)[1].split("</aside>", 1)[0]
        self.assertEqual(detail.count("data-detail-level"), 2)
        self.assertIn("data-detail-risk", detail)
        self.assertNotIn("data-detail-level-copy", detail)
        self.assertIn("data-detail-summary", complete)
        self.assertIn('placeholder="代码 / 名称 / 板块 / 行业 / 关键词"', complete)
        self.assertIn('data-i18n-zh="板块">板块</span></th>', complete)
        self.assertIn(">创业板</td>", complete)
        self.assertIn('data-board="创业板"', complete)
        self.assertIn("aShareSelectionReportLang", report)
        self.assertIn("initCandidateMasterDetail", report)
        self.assertIn("function runAfterFirstPaint(callback)", report)
        self.assertIn("window.requestIdleCallback(callback, { timeout: 350 })", report)
        self.assertIn("setLang(initial, { forceText: initial !== generated, silent: true })", report)
        self.assertIn("root.dataset.uiReady = 'true'", report)
        self.assertIn("addEventListener('click'", report)
        self.assertIn("tbody.addEventListener('click'", report)
        self.assertIn("let selectedRow = null", report)
        self.assertIn("requestAnimationFrame", report)
        self.assertIn("let mountedRows = []", report)
        self.assertIn("tbody.replaceChildren(fragment)", report)
        self.assertIn("mountedRows = shownRows", report)
        self.assertNotIn("renderNow({ skipDomMount: true })", report)
        self.assertIn("renderNow();", report)
        self.assertIn("openStockDrawer", report)
        self.assertIn("drawStockCandles", report)
        self.assertIn("stockChart.getContext('2d')", report)
        self.assertIn("tbody.addEventListener('keydown'", report)
        self.assertIn("trapStockFocus", report)
        self.assertIn("copyCurrentStockSummary", report)
        self.assertIn("Clipboard access is often blocked for local file reports", report)
        self.assertIn("calculateTechnicalIndicators", report)
        self.assertIn("calculateKdj", report)
        self.assertIn("calculateBollinger", report)
        self.assertIn("calculateAtr", report)
        self.assertIn("const technicalCache = new Map()", report)
        self.assertIn("function indicatorsForRows(rows)", report)
        self.assertIn("technicalCache.set(key, calculateTechnicalIndicators(rows));", report)
        self.assertNotIn("const window = candles.slice", report)
        self.assertNotIn("const window = closes.slice", report)
        self.assertIn("originalIndex", report)
        self.assertIn("const width = Math.max(1, Math.floor(rect.width || 0));", report)
        self.assertIn("const nextHoverIndex = rows.length > 1", report)
        self.assertIn("if (chartHoverIndex === nextHoverIndex)", report)
        self.assertIn("const tooltipWidth = Math.min(210, width - 20);", report)
        self.assertNotIn("stockChartTooltip.offsetWidth", report)
        self.assertIn("const terms = query.split(/\\s+/).filter(Boolean)", report)
        self.assertIn("terms.every(term => haystack.includes(term))", report)
        self.assertIn("detailRisk.textContent = dataset.rowRisk", report)
        self.assertIn("addEventListener('change', applyFilters)", report)
        self.assertIn("addEventListener('change', applySort)", report)
        self.assertIn("setStockField('field-availability'", report)
        self.assertIn("Report note", report)
        self.assertIn("].join(", report)
        self.assertIn("navigator.clipboard.writeText(summary)", report)
        self.assertIn("activeStockRow.setAttribute('aria-expanded', 'true')", report)
        self.assertIn("activeStockRow.setAttribute('aria-expanded', 'false')", report)
        self.assertIn("document.removeEventListener('keydown', handleStockKeydown)", report)
        self.assertIn("document.addEventListener('keydown', handleStockKeydown)", report)
        self.assertIn("setModalContentHidden(true, stockDrawer)", report)
        self.assertIn("setModalContentHidden(false, null)", report)
        self.assertIn('data-report-content', report)
        self.assertIn('data-report-modal-root', report)
        self.assertIn("stockDrawer.dataset.selectedSymbol", report)
        self.assertIn("stockDrawer.dataset.selectedName", report)
        self.assertIn("width < 520 ? rawDate.slice(5) : rawDate", report)
        self.assertIn("const labelTarget = width < 420 ? 3", report)
        self.assertNotIn("rows.forEach(row => row.addEventListener('click'", report)

    def test_complete_candidate_detail_embeds_local_kline_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            prices = output / "prices.csv"
            write_consumer_candidate_rows(candidates)
            prices.write_text(
                "\n".join(
                    [
                        "symbol,date,open,high,low,close,volume",
                        "sz.300001,20260604,9.8,10.6,9.7,10.1,1200",
                        "300001.SZ,2026-06-05,10.1,10.8,10.0,10.6,1500",
                        "600000,2026-06-05,19.8,20.2,19.5,20.0,2100",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 2,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                    "prices_output": str(prices),
                    "prices_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        complete = report.split('<section id="complete-candidates"', 1)[1]
        payload = complete.split('data-candidate-candles>', 1)[1].split("</script>", 1)[0]
        candles = json.loads(payload)
        self.assertEqual(["2026-06-04", 9.8, 10.6, 9.7, 10.1, 1200.0], candles["300001"][0])
        self.assertEqual(["2026-06-05", 10.1, 10.8, 10.0, 10.6, 1500.0], candles["300001"][1])
        self.assertEqual(["2026-06-05", 19.8, 20.2, 19.5, 20.0, 2100.0], candles["600000"][0])

    def test_embedded_kline_data_is_limited_for_large_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            prices = output / "prices.csv"
            rows = [
                "rank,symbol,name,listing_board,date,close,total_score,key_reasons,risk_notes"
            ]
            price_rows = ["symbol,date,open,high,low,close,volume"]
            for index in range(105):
                symbol = f"{index + 1:06d}"
                rows.append(
                    f"{index + 1},{symbol},Stock {index + 1},主板,2026-06-17,10,0.6,reason,"
                )
                price_rows.append(
                    f"{symbol},2026-06-17,9,11,8,10,{1000 + index}"
                )
            candidates.write_text("\n".join(rows) + "\n", encoding="utf-8")
            prices.write_text("\n".join(price_rows) + "\n", encoding="utf-8")
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 105,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                    "prices_output": str(prices),
                    "prices_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        payload = report.split("data-candidate-candles>", 1)[1].split("</script>", 1)[0]
        candles = json.loads(payload)
        self.assertEqual(100, len(candles))
        self.assertIn("000100", candles)
        self.assertNotIn("000101", candles)

    def test_candidate_form_fields_have_id_or_name_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,listing_board,date,close,total_score,key_reasons,risk_notes",
                        "1,000100,Alpha,主板,2026-06-17,5.12,0.73,positive momentum,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 1,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        complete = report.split('<section id="complete-candidates"', 1)[1]
        controls = (
            '<input id="candidate-search" name="candidate_search"',
            '<select id="candidate-filter-board" name="candidate_filter_board"',
            '<select id="candidate-filter-level" name="candidate_filter_level"',
            '<select id="candidate-sort" name="candidate_sort"',
            '<select id="candidate-page-size" name="candidate_page_size"',
        )
        for control in controls:
            self.assertIn(control, complete)
        toolbar = complete.split('<div class="master-table">', 1)[0]
        self.assertNotIn("data-candidate-industry", toolbar)

    def test_candidate_tables_mark_missing_stock_name_without_reusing_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,listing_board,date,close,total_score,key_reasons,risk_notes",
                        "1,000100,000100,主板,2026-06-17,5.12,0.73,positive momentum,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 1,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        preview = report.split('<section id="complete-candidates"', 1)[0]
        complete = report.split('<section id="complete-candidates"', 1)[1]
        self.assertIn('<strong class="stock-anchor missing">名称未提供</strong>', preview)
        self.assertIn('<span class="stock-code">000100</span>', preview)
        self.assertIn('<span class="symbol-cell">000100</span>', complete)
        self.assertIn('<strong class="name-cell missing">名称未提供</strong>', complete)
        self.assertNotIn('<strong class="name-cell">000100</strong>', complete)
        self.assertNotIn("&lt;span data-i18n-en=", report)

    def test_report_time_falls_back_when_candidate_stat_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            write_consumer_candidate_rows(candidates)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 2,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            with patch(
                "a_share_selection_html_sections.path_mtime",
                side_effect=PermissionError("denied"),
            ):
                report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("Generated when this report was written", report)
        self.assertIn("Complete Candidate Table", report)

    def test_candidate_detail_panel_escapes_source_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,listing_board,date,close,total_score,key_reasons,risk_notes",
                        '1,000001,Unsafe,主板,2026-06-05,10.0,0.82,"<script>alert(1)</script>",',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 1,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        complete = report.split('<section id="complete-candidates"', 1)[1]
        detail = complete.split('data-detail-reason', 1)[1].split("</aside>", 1)[0]
        self.assertNotIn("<script>alert(1)</script>", detail)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", detail)
        self.assertIn('data-row-reason="&lt;script&gt;alert(1)&lt;/script&gt;"', complete)

    def test_candidate_detail_discloses_missing_optional_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,listing_board,date,close,total_score,key_reasons,risk_notes",
                        "1,000001,Ping An,主板,2026-06-05,10.0,0.82,passed configured filters,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 1,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        complete = report.split('<section id="complete-candidates"', 1)[1]
        self.assertIn("字段可用性", complete)
        self.assertIn("本次源数据未提供行业、近一年涨跌幅、市值、PE TTM、PB LF。", complete)
        self.assertIn("data-row-field-availability", complete)

    def test_report_tables_and_paths_are_folded_for_consumer_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            diagnostics = output / "diagnostics.csv"
            write_consumer_candidate_rows(candidates)
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason",
                        "000003,Gamma,8.1,0.2,未通过阈值,价格高于上限",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            summary.update(
                {
                    "candidate_rows": 2,
                    "diagnostic_rows": 1,
                    "candidates_output": str(candidates),
                    "diagnostics_output": str(diagnostics),
                    "candidates_output_written": True,
                    "diagnostics_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        candidate_detail = details_block(report, "candidate-detail-table")
        diagnostics_detail = details_block(report, "diagnostics-detail")
        evidence_detail = details_block(report, "evidence-detail")
        self.assertIn('class="candidate-cards"', report)
        self.assertIn('class="table-wrap"', candidate_detail)
        self.assertIn("明细表", candidate_detail)
        self.assertIn('class="table-wrap"', diagnostics_detail)
        self.assertIn("Gamma", diagnostics_detail)
        self.assertIn(">./summary.json</code>", evidence_detail)
        self.assertLess(report.index("观察池 Top 5 预览"), report.index(candidate_detail))
        self.assertLess(report.index("这里保留每只股票的规则结果"), report.index(diagnostics_detail))

    def test_report_uses_productized_visual_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            write_consumer_candidate_rows(candidates)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "candidate_rows": 2,
                    "candidates_output": str(candidates),
                    "candidates_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn('class="hero executive-hero"', report)
        self.assertIn('class="hero-badges"', report)
        self.assertIn('class="pipeline-metrics"', report)
        self.assertIn('<button type="button" class="pipeline-card input"', report)
        self.assertIn('class="pipeline-copy"', report)
        self.assertIn('data-insight-trigger=""', report)
        self.assertIn('data-insight-node="input"', report)
        self.assertIn('data-insight-kind-en="Input data"', report)
        self.assertIn('data-insight-title-en="Input data scope"', report)
        self.assertIn('data-insight-facts-en="Sample stocks::', report)
        self.assertIn('|Price rows::', report)
        self.assertIn('class="insight-drawer"', report)
        self.assertIn('role="dialog"', report)
        self.assertIn('class="watchlist-dashboard"', report)
        self.assertIn('class="candidate-open-slot"', report)
        self.assertIn('class="final-notice-grid"', report)
        self.assertIn('class="selection-flow"', report)
        self.assertIn('<button type="button" class="flow-step input"', report)
        self.assertIn("Clickable details", report)
        self.assertIn(".report-overview-grid", report)
        self.assertIn("button.pipeline-card,button.flow-step{font:inherit;color:inherit;cursor:pointer}", report)
        self.assertIn(".pipeline-card:hover,.pipeline-card:focus-visible", report)
        self.assertIn(".flow-step:hover,.flow-step:focus-visible", report)
        self.assertIn(".insight-drawer[hidden]{display:none}", report)
        self.assertIn(".insight-facts{display:grid;grid-template-columns:minmax(140px,190px)", report)
        self.assertIn(".insight-drawer{place-items:end center;padding:12px}", report)
        self.assertIn(".insight-close{min-width:44px;min-height:44px}", report)
        self.assertIn(".candidate-cards[data-preview-table]", report)
        self.assertIn(".candidate-cards[data-preview-table] th:nth-last-child(2),.candidate-cards[data-preview-table] td:nth-last-child(2){width:88px}", report)
        self.assertIn("@media(max-width:1500px)", report)
        self.assertIn(
            ".watchlist-dashboard{display:grid;grid-template-columns:minmax(0,1.12fr) minmax(320px,.88fr);gap:12px;align-items:stretch}",
            report,
        )
        self.assertIn(
            ".candidate-open-slot{display:grid;align-items:stretch;justify-items:stretch;min-width:0;min-height:100%}",
            report,
        )
        self.assertIn(
            ".master-detail-grid{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(480px,.92fr);gap:12px;align-items:start}",
            report,
        )
        self.assertNotIn("candidate-entry-card", report)
        self.assertIn("justify-content:center", report)
        self.assertIn(".candidate-file-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}", report)
        self.assertIn(".candidate-download-link{display:inline-flex;align-items:center;justify-content:center;min-height:34px", report)
        self.assertIn(".candidate-file-actions{display:grid;grid-template-columns:1fr;justify-content:stretch;width:100%}", report)
        self.assertIn(".candidate-download-link{min-height:44px}", report)
        self.assertIn(".stock-code{display:block;margin-top:3px;color:#334155;font-size:13px", report)
        self.assertIn(".name-cell.missing,.stock-anchor.missing{color:#64748b}", report)
        self.assertIn(".stock-dialog{width:min(1120px,100%);max-height:min(92vh,920px);overflow:auto", report)
        self.assertIn(".stock-dialog-grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(360px,.95fr);gap:14px;padding:14px;align-items:start}", report)
        self.assertIn(".stock-tech-summary{border:1px solid #bfdbfe;border-radius:8px;background:#f8fbff;padding:10px 12px", report)
        self.assertIn(".stock-tech-card[data-status=\"positive\"]", report)
        self.assertIn(".stock-tech-card[data-status=\"attention\"]", report)
        self.assertIn(".stock-tech-card[data-status=\"negative\"]", report)
        self.assertIn(".stock-tech-card[data-status=\"attention\"] strong{color:#854d0e}", report)
        self.assertIn(".stock-tech-card[data-status=\"negative\"] strong{color:#991b1b}", report)
        self.assertIn(".stock-dialog-close:hover,.stock-dialog-close:focus-visible{outline:2px solid #1b75d0;outline-offset:2px", report)
        self.assertIn(".stock-action-grid button:hover,.stock-action-grid button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px", report)
        self.assertIn(".stock-chart-wrap canvas{display:block;width:100%;height:100%;touch-action:none}", report)
        self.assertIn(".candidate-toolbar button:focus-visible{outline:2px solid #1b75d0;outline-offset:2px", report)
        self.assertIn(".candidate-pager button:not(:disabled):hover,.candidate-pager button:not(:disabled):focus-visible{outline:2px solid #1b75d0;outline-offset:2px", report)
        self.assertIn(".stock-technical-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}", report)
        self.assertIn("@media(max-width:1100px)", report)
        self.assertIn("@media(max-width:640px)", report)
        self.assertIn("@media(max-width:520px)", report)
        self.assertIn("overflow-x:auto", report)
        self.assertIn("flex-wrap:wrap", report)
        self.assertIn("min-height:44px", report)
        self.assertIn("white-space:normal", report)
        self.assertIn(".candidate-page-numbers{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-width:0}", report)
        self.assertIn(".candidate-page-number{min-width:44px;min-height:44px", report)
        self.assertIn("grid-template-columns:repeat(2,minmax(0,1fr))", report)
        self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr))", report)
        self.assertIn(".flow-arrow{display:none}", report)
        self.assertIn(".hero-fact-card{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))", report)
        self.assertIn(".pipeline-card:nth-child(2n){border-right:0}", report)
        self.assertIn(".hero-fact-card,.pipeline-metrics{grid-template-columns:1fr}", report)
        self.assertIn(".selection-flow{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}", report)
        self.assertNotIn(".hero-badge{flex-basis:100%}", report)
        self.assertIn(".pipeline-icon::before,.pipeline-icon::after{content:\"\";position:absolute;left:50%;top:50%;background:#fff;transform:translate(-50%,-50%)}", report)
        self.assertIn(".pipeline-icon.circle::before{width:10px;height:10px;border-radius:50%;box-shadow:-11px 0 0 #fff,11px 0 0 #fff,0 15px 0 5px #fff;clip-path:none;transform:translate(-50%,-72%)}", report)
        self.assertIn(".pipeline-icon.eye::before{width:30px;height:20px;border:4px solid #fff;border-radius:50%;background:transparent;clip-path:none}", report)
        self.assertIn(".pipeline-icon.circle::before{width:8px;height:8px;box-shadow:-9px 0 0 #fff,9px 0 0 #fff,0 12px 0 4px #fff}", report)
        self.assertIn(".pipeline-copy{display:grid;grid-template-columns:minmax(0,max-content) minmax(0,max-content) minmax(0,1fr);align-items:center;column-gap:10px;min-width:0}", report)
        self.assertIn(".pipeline-card strong{display:block;color:#111827;font-size:30px;line-height:1;letter-spacing:0;font-variant-numeric:tabular-nums}", report)
        self.assertIn(".pipeline-card small{display:block;min-width:0;color:#475569;font-size:13px;line-height:1.1;white-space:normal;overflow-wrap:anywhere}", report)
        self.assertIn(".pipeline-copy{grid-template-columns:max-content max-content;grid-template-areas:\"label value\" \"note note\";align-items:center;column-gap:6px;row-gap:3px}", report)
        self.assertIn(".pipeline-card small{grid-area:note;font-size:12px;line-height:1.2}", report)
        self.assertIn(".detail-evidence-card{border-left:0;border-top:1px solid #e7edf4}", report)
        self.assertIn(".master-table{max-height:420px;overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff;contain:content}", report)
        self.assertIn(".candidate-master-detail{margin-top:8px;max-width:100%;overflow:hidden", report)
        self.assertIn(".master-list-panel{min-width:0;max-width:100%;overflow:clip}", report)
        self.assertIn(".master-table:not(.has-wide-table) th:nth-child(1),.master-table:not(.has-wide-table) td:nth-child(1){width:62px}", report)
        self.assertIn(".master-table tbody tr[hidden]{display:none}", report)
        self.assertIn(".candidate-detail-panel{align-self:stretch;height:100%;max-height:560px;border:1px solid var(--line);border-radius:8px;background:#fff;min-width:0;overflow:auto;box-shadow:0 8px 18px rgba(15,23,42,.04);contain:content;scrollbar-gutter:stable}", report)
        self.assertIn(".master-table tr[data-selected=\"true\"]{background:#eaf4ff;box-shadow:inset 0 0 0 2px #6daff0}", report)
        self.assertIn(".candidate-page-numbers{grid-column:1/-1;grid-row:2;justify-content:center}", report)
        self.assertIn(".candidate-pager label{grid-column:2;grid-row:3;display:flex;align-items:center;justify-content:flex-end;gap:6px}", report)
        self.assertNotIn("scroll-behavior:smooth", report)
        self.assertNotIn("scrollIntoView", report)
        self.assertIn("function initInsightDrawer()", report)
        self.assertIn("document.querySelectorAll('[data-insight-trigger]')", report)
        self.assertIn('aria-describedby="insight-summary"', report)
        self.assertIn('id="insight-summary" class="insight-summary"', report)
        self.assertIn("let bodyLockCount = 0", report)
        self.assertIn("setBodyLocked(true);", report)
        self.assertIn("setBodyLocked(false);", report)
        self.assertIn("event.key === 'Escape'", report)
        self.assertIn("event.key === 'Tab'", report)
        self.assertIn("function trapFocus(event)", report)
        self.assertIn("!elements.includes(document.activeElement)", report)
        self.assertIn("document.addEventListener('keydown', handleKeydown)", report)
        self.assertIn("document.removeEventListener('keydown', handleKeydown)", report)
        self.assertIn("kind.textContent = localizedDataset(trigger, 'insightKind');", report)
        self.assertIn("report-language-change", report)
        self.assertIn("renderFacts(localizedDataset(trigger, 'insightFacts'))", report)
        self.assertIn("updateTechnicalIndicators(candles);", report)
        self.assertIn("const technical = indicatorsForRows(rows);", report)
        self.assertIn(".flow-step small{display:none}", report)
        self.assertIn("min-width:0;border:1px solid var(--line);border-radius:8px;background:#fff;padding:11px", report)

    def test_pipeline_input_metric_uses_stock_count_not_price_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            summary = minimal_summary(tmpdir, output / "diagnostics.csv")
            summary.update(
                {
                    "prices_rows": 24184,
                    "history_symbol_count": 69,
                    "diagnostic_rows": 69,
                    "score": {"input_symbols": 69},
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        metrics = report.split('<section class="pipeline-metrics"', 1)[1].split(
            "</section>",
            1,
        )[0]
        input_card = metrics.split('<button type="button" class="pipeline-card input"', 1)[
            1
        ].split("</button>", 1)[0]
        input_card_visible = input_card.split('class="pipeline-copy"', 1)[1]
        flow = report.split('<section class="selection-flow"', 1)[1].split(
            "</section>",
            1,
        )[0]
        input_step = flow.split('<button type="button" class="flow-step input"', 1)[1].split(
            "</button>",
            1,
        )[0]
        input_step_visible = input_step.split('class="flow-index"', 1)[1]

        self.assertIn("样本股票", input_card_visible)
        self.assertIn("<strong>69</strong>", input_card_visible)
        self.assertNotIn("24184", input_card_visible)
        self.assertIn("样本股票", input_step_visible)
        self.assertIn("<strong>69</strong>", input_step_visible)
        self.assertNotIn("24184", input_step_visible)
        self.assertIn('data-insight-facts-zh="样本股票::69|行情行数::24184', report)

    def test_non_finite_numeric_values_render_as_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            candidates = Path(tmpdir) / "candidates.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,date,close,spot_price,spot_pct_chg,total_score,key_reasons,risk_notes",
                        "1,000001,NaN Case,2025-01-01,nan,inf,-inf,NaN,positive momentum,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary["candidate_rows"] = 1
            summary["candidates_output"] = str(candidates)
            summary["candidates_output_written"] = True
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn(">NaN Case<", report)
        self.assertGreaterEqual(report.count(">-<"), 4)
        self.assertNotIn(">nan<", report.lower())
        self.assertNotIn(">inf<", report.lower())

    def test_report_localizes_emitted_candidate_and_cap_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            diagnostics = output / "diagnostics.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,date,close,total_score,key_reasons,risk_notes",
                        (
                            "1,000001,Localized,2025-01-01,7.1,0.8,"
                            "prediction above threshold; short-term activity,"
                            "high volatility"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        "000002,Capped,7.2,0.7,通过阈值但未入选,通过阈值但受输出数量限制,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            summary.update(
                {
                    "candidate_rows": 1,
                    "diagnostic_rows": 1,
                    "candidates_output": str(candidates),
                    "diagnostics_output": str(diagnostics),
                    "candidates_output_written": True,
                    "diagnostics_output_written": True,
                }
            )
            zh_report = render_report(summary, {"steps": []}, language="zh")
            en_report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("预测高于阈值；短线活跃", zh_report)
        self.assertIn("高波动", zh_report)
        self.assertIn("通过阈值但受输出数量限制", zh_report)
        self.assertIn("prediction above threshold; short-term activity", en_report)
        self.assertIn("high volatility", en_report)
        self.assertIn("Passed gates but capped by output limit", en_report)
        self.assertNotIn(">通过阈值但受输出数量限制<", en_report)

    def test_report_displays_as_of_metadata_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            diagnostics = output / "diagnostics.csv"
            candidates.write_text(
                "\n".join(
                    [
                        (
                            "rank,symbol,name,date,close,requested_as_of_date,"
                            "actual_data_date,as_of_date_observed,total_score,key_reasons,risk_notes"
                        ),
                        "1,000001,AsOf Case,2026-06-05,7.1,2026-06-06,2026-06-05,False,0.8,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            diagnostics.write_text(
                "\n".join(
                    [
                        (
                            "symbol,name,close,requested_as_of_date,actual_data_date,"
                            "as_of_date_observed,total_score,selection_status,short_reason"
                        ),
                        "000002,AsOf Diagnostic,7.2,2026-06-06,2026-06-05,False,0.7,未通过阈值,实际信号日不同",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            summary.update(
                {
                    "candidate_rows": 1,
                    "diagnostic_rows": 1,
                    "candidates_output": str(candidates),
                    "diagnostics_output": str(diagnostics),
                    "candidates_output_written": True,
                    "diagnostics_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("Requested as-of date", report)
        self.assertIn("Actual data date", report)
        self.assertIn("As-of date observed", report)
        self.assertIn(">2026-06-06<", report)
        self.assertIn(">2026-06-05<", report)
        self.assertIn(">False<", report)

    def test_truncated_report_keeps_row_level_source_and_capital_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            diagnostics = output / "diagnostics.csv"
            header = (
                "rank,symbol,name,date,close,requested_as_of_date,actual_data_date,"
                "as_of_date_observed,prediction_source,prediction_input_source,"
                "source_type,real_market_data,total_score,cash_budget,lot_size,"
                "capital_model,signal_close,cash_slot,quantity,cash_reserved,"
                "notional,weight,unallocated,key_reasons,risk_notes"
            )
            rows = [header]
            for index in range(1, 27):
                rows.append(
                    (
                        f"{index},000{index:03d},Name {index},2026-06-05,7.1,"
                        "2026-06-06,2026-06-05,False,external_unverified,"
                        "external_input,unknown,unknown,0.8,10000,100,"
                        "equal_cash_budget_lot_floor,7.1,5000,700,4970,"
                        "4970,0.497,False,positive momentum,"
                    )
                )
            candidates.write_text("\n".join(rows) + "\n", encoding="utf-8")
            diagnostics.write_text(
                "\n".join(
                    [
                        (
                            "symbol,name,date,close,requested_as_of_date,actual_data_date,"
                            "as_of_date_observed,prediction_source,prediction_input_source,"
                            "source_type,real_market_data,total_score,selection_status,short_reason"
                        ),
                        (
                            "000002,Diag,2026-06-05,7.2,2026-06-06,2026-06-05,"
                            "False,external_unverified,external_input,unknown,unknown,"
                            "0.6,未通过阈值,价格高于上限"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            summary.update(
                {
                    "candidate_rows": 26,
                    "diagnostic_rows": 1,
                    "candidates_output": str(candidates),
                    "diagnostics_output": str(diagnostics),
                    "candidates_output_written": True,
                    "diagnostics_output_written": True,
                }
            )
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("Prediction source", report)
        self.assertIn("Prediction input source", report)
        self.assertIn("Source type", report)
        self.assertIn("Real market data", report)
        self.assertIn("Cash budget", report)
        self.assertIn("Capital model", report)
        self.assertIn("external_unverified", report)
        self.assertIn("external_input", report)
        self.assertIn("equal_cash_budget_lot_floor", report)
        self.assertIn("Showing the first 25 rows only", report)
        preview = report.split('<section id="complete-candidates"', 1)[0]
        complete = report.split('<section id="complete-candidates"', 1)[1]
        self.assertNotIn("Name 26", preview)
        self.assertIn("Name 26", complete)

    def test_missing_key_disclosure_fields_render_as_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            candidates = output / "candidates.csv"
            diagnostics = output / "diagnostics.csv"
            candidates.write_text(
                "\n".join(
                    [
                        "rank,symbol,name,date,close,total_score,key_reasons,risk_notes",
                        "1,000001,Missing Fields,2026-06-05,7.1,0.7,positive momentum,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason",
                        "000002,Diag Missing,8.1,0.2,未通过阈值,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            summary.update(
                {
                    "candidate_rows": 1,
                    "diagnostic_rows": 1,
                    "candidates_output": str(candidates),
                    "diagnostics_output": str(diagnostics),
                    "candidates_output_written": True,
                    "diagnostics_output_written": True,
                }
            )
            en_report = render_report(summary, {"steps": []}, language="en")
            zh_report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn(">Unknown<", en_report)
        self.assertIn(">未知<", zh_report)
        self.assertIn("missing field: requested_as_of_date", en_report)
        self.assertIn("missing field: prediction_source", en_report)
        self.assertIn("missing field: failure_reason", en_report)


def visible_before_technical_details(report: str) -> str:
    return report.split('<details class="technical-details">', 1)[0]


def details_block(report: str, class_name: str) -> str:
    marker = f'<details class="report-details {class_name}">'
    return marker + report.split(marker, 1)[1].split("</details>", 1)[0] + "</details>"


def write_consumer_candidate_rows(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                (
                    "rank,symbol,name,listing_board,spot_industry,date,close,total_score,cash_budget,lot_size,"
                    "quantity,cash_reserved,notional,weight,unallocated,"
                    "sizing_claim_boundary,key_reasons,risk_notes"
                ),
                (
                    "1,300001,Alpha Tech,创业板,软件服务,2026-06-05,10.0,0.82,10000,100,"
                    "400,4000,4000,0.4,False,local_sizing_not_broker_order,"
                    "positive momentum; short-term activity,high volatility"
                ),
                (
                    "2,600000,Beta Bank,主板,银行,2026-06-05,20.0,0.71,10000,100,"
                    "200,4000,4000,0.4,False,local_sizing_not_broker_order,"
                    "acceptable volatility; rsi in range,no major configured risk flag"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
