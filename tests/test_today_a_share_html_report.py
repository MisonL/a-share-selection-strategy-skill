from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


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
        self.assertIn("A 股选股策略", report)
        self.assertIn("A 股选股报告 - 已完成 - 通用技术评分", report)
        self.assertIn("评分方式", report)
        self.assertIn("评分说明", report)
        self.assertIn("通用技术评分", report)
        self.assertIn("为什么用这个模式", report)
        self.assertIn("这份报告能说明什么", report)
        self.assertIn("输入没有预测列，auto 因此使用技术门禁。", report)
        self.assertIn("不能证明模型预测质量、实时全市场覆盖、未来收益或真实可交易性。", report)
        self.assertIn("技术细节", report)
        self.assertIn("机器边界", report)
        self.assertIn("details.technical-details", report)
        self.assertIn("查看命令级执行细节", report)
        self.assertIn("原因", report)
        self.assertIn("动量为正；波动率可接受；RSI 处于合理区间", report)
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
        self.assertIn("A-Share Selection Strategy", report)
        self.assertIn("A-Share Selection Report - Completed - Generic technical scoring", report)
        self.assertIn("Scoring Method", report)
        self.assertIn("Scoring Notes", report)
        self.assertIn("Generic technical scoring", report)
        self.assertIn("Why this mode", report)
        self.assertIn("What this report can and cannot prove", report)
        self.assertIn("Input has no prediction column, so auto mode used technical gates.", report)
        self.assertIn("filtered available A-share price data", report)
        self.assertIn("It cannot prove model prediction quality, live full-market coverage, future returns, or real tradability.", report)
        self.assertIn("el.open=false", report)
        self.assertIn("const initial=mode==='auto'?(saved||generated):mode", report)
        self.assertIn("aShareSelectionReportLang", report)
        self.assertIn('data-i18n-zh="A 股选股策略"', report)
        self.assertIn("Show command-level execution details", report)
        self.assertIn("Reason", report)
        self.assertIn("positive momentum; acceptable volatility; rsi in range", report)
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
        self.assertIn("const generated=root.dataset.lang||'en'", report)
        self.assertIn("const initial=mode==='auto'?(saved||generated):mode", report)
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
        self.assertNotIn("Name 26", report)

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

        self.assertIn('class="executive-summary"', report)
        self.assertIn("一眼结论", report)
        self.assertIn("找到 2 条候选", report)
        self.assertIn("不是买卖指令", report)
        self.assertLess(report.index('class="executive-summary"'), report.index('class="table-wrap"'))
        self.assertLess(
            report.index('class="executive-summary"'),
            report.index('<details class="technical-details">'),
        )

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
        self.assertIn("数据来源边界", visible)
        self.assertIn("合成 demo 数据（low-price-ultra-short）；不是真实行情。", visible)
        self.assertIn("real_market_data=false", visible)
        self.assertLess(
            report.index("数据来源边界"),
            report.index("首位候选"),
        )

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
        self.assertEqual(2, report.count('class="candidate-card"'))
        self.assertIn("Why it passed", report)
        self.assertIn("Risk notes", report)
        self.assertIn("Cash reserved", report)
        self.assertIn("Not a broker order", report)
        self.assertLess(report.index('class="candidate-cards"'), report.index('class="table-wrap"'))

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
        self.assertIn('class="signal-bars"', report)
        self.assertIn(".executive-summary", report)
        self.assertIn(".candidate-card", report)

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
        self.assertNotIn("Name 26", report)

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


def write_consumer_candidate_rows(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                (
                    "rank,symbol,name,date,close,total_score,cash_budget,lot_size,"
                    "quantity,cash_reserved,notional,weight,unallocated,"
                    "sizing_claim_boundary,key_reasons,risk_notes"
                ),
                (
                    "1,000001,Alpha Tech,2026-06-05,10.0,0.82,10000,100,"
                    "400,4000,4000,0.4,False,local_sizing_not_broker_order,"
                    "positive momentum; short-term activity,high volatility"
                ),
                (
                    "2,600000,Beta Bank,2026-06-05,20.0,0.71,10000,100,"
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
