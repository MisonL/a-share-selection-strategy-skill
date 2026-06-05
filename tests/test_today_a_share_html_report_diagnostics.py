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
from html_report_helpers import minimal_summary  # noqa: E402


class TodayAShareHtmlReportDiagnosticsTests(unittest.TestCase):
    def test_diagnostic_reason_switches_between_zh_and_en(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            diagnostics = Path(tmpdir) / "diagnostics.csv"
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        "000003,High Price Reject,12.4413,0.5807958027683607,未通过阈值,价格高于上限,max_close,价格高于上限",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("价格高于上限", report)
        self.assertIn("Price is above the configured limit", report)
        self.assertNotIn(">失败门禁中文<", report)
        self.assertNotIn("title=\"{&quot;en&quot;", report)

    def test_diagnostic_reason_prefers_machine_threshold_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            diagnostics = Path(tmpdir) / "diagnostics.csv"
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        "000004,Amount Reject,7.0413,0.6047225485160466,未通过阈值,错误展示原因,min_amount,错误展示原因",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("成交额不足", report)
        self.assertIn("Trading amount is below the configured limit", report)
        self.assertNotIn("错误展示原因", report)

    def test_diagnostic_reason_translates_all_known_threshold_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            diagnostics = Path(tmpdir) / "diagnostics.csv"
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        (
                            "000005,Many Rejects,7.0413,0.6047225485160466,未通过阈值,错误展示原因,"
                            "min_total_score;min_momentum_score;min_rsi;max_rsi;max_volatility;"
                            "min_volume;min_amount;min_turn;min_close;max_close;exclude_st;"
                            "require_tradestatus;exclude_one_word_bar;min_prediction_score;min_trend_score,"
                            "错误展示原因"
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("综合评分不足；动量不足；RSI过低；RSI过热；波动率过高", report)
        self.assertIn("成交量不足；成交额不足；换手率不足；价格低于下限；价格高于上限", report)
        self.assertIn("ST标的；停牌或不可交易；一字板；预测分不足；趋势分不足", report)
        self.assertIn("Total score is below the configured limit", report)
        self.assertIn("Trend score is below the configured limit", report)
        self.assertNotIn("错误展示原因", report)

    def test_mixed_threshold_reason_keeps_known_machine_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            diagnostics = Path(tmpdir) / "diagnostics.csv"
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        "000008,Mixed Reject,7.0413,0.6047225485160466,未通过阈值,机器键不应展示,max_close;custom_gate,错误展示原因",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("价格高于上限", report)
        self.assertIn("Price is above the configured limit", report)
        self.assertNotIn("机器键不应展示", report)

    def test_diagnostic_reason_falls_back_to_zh_for_unknown_threshold_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            diagnostics = Path(tmpdir) / "diagnostics.csv"
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        "000006,Unknown Reject,7.0413,0.6047225485160466,未通过阈值,机器键不应展示,custom_gate,自定义门禁失败",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("自定义门禁失败", report)
        self.assertNotIn("custom_gate", report)
        self.assertNotIn("机器键不应展示", report)

    def test_capped_diagnostic_status_translates_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            diagnostics = Path(tmpdir) / "diagnostics.csv"
            diagnostics.write_text(
                "\n".join(
                    [
                        "symbol,name,close,total_score,selection_status,short_reason,failed_thresholds,failed_thresholds_zh",
                        "000007,Capped Pass,7.0413,0.7047225485160466,通过阈值但未入选,通过全部阈值但受候选数上限影响未入选,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            summary = minimal_summary(tmpdir, diagnostics)
            report = render_report(summary, {"steps": []}, language="en")

        self.assertIn("Passed gates but not selected", report)
        self.assertIn("通过阈值但未入选", report)
        self.assertNotIn(">通过阈值但未入选<", report)

    def test_auto_generic_reports_actual_missing_prediction_contract_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = minimal_summary(tmpdir, Path(tmpdir) / "diagnostics.csv")
            summary.update(
                {
                    "mode_decision_reason": "missing_prediction_columns:market,turnover",
                    "missing_prediction_column_groups": ["market", "turnover"],
                    "missing_prediction_requirement": "",
                }
            )
            report = render_report(summary, {"steps": []}, language="zh")

        self.assertIn("输入缺少预测评分契约字段组：market, turnover", report)
        self.assertIn("Input is missing required prediction contract groups: market, turnover", report)
        self.assertNotIn("输入没有预测列，auto 因此使用技术门禁。", report)
        self.assertNotIn("Input has no prediction column, so auto mode used technical gates.", report)


if __name__ == "__main__":
    unittest.main()
