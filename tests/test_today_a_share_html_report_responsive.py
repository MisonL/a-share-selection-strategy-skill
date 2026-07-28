from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

from html_report_helpers import minimal_summary  # noqa: E402
from lib.report_html.a_share_selection_html_report import render_report  # noqa: E402


class ResponsiveHtmlReportTests(unittest.TestCase):
    def render_optional_field_report(
        self, *, field_coverage: dict[str, object] | None = None
    ) -> str:
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
            if field_coverage is not None:
                summary["candidate_field_coverage"] = field_coverage
            return render_report(summary, {"steps": []}, language="zh")

    def test_complete_table_precedes_field_coverage_and_marks_mobile_columns(self) -> None:
        report = self.render_optional_field_report(
            field_coverage={
                "rows_evaluated": 1,
                "fields": {
                    "industry": {"present_rows": 1, "missing_rows": 0, "coverage_ratio": 1.0},
                    "one_year_pct_chg": {
                        "present_rows": 1,
                        "missing_rows": 0,
                        "coverage_ratio": 1.0,
                    },
                    "market_cap": {
                        "present_rows": 1,
                        "missing_rows": 0,
                        "coverage_ratio": 1.0,
                    },
                    "pe_ttm": {"present_rows": 1, "missing_rows": 0, "coverage_ratio": 1.0},
                    "pb_lf": {"present_rows": 1, "missing_rows": 0, "coverage_ratio": 1.0},
                },
            }
        )
        complete = report.split('<section id="complete-candidates"', 1)[1]
        table = '<div class="master-table has-wide-table">'
        coverage = '<section class="field-coverage-card">'

        self.assertLess(complete.index(table), complete.index(coverage))
        self.assertLess(complete.index("<thead><tr>"), complete.index(coverage))
        self.assertLess(complete.index("data-candidate-row"), complete.index(coverage))
        for column in (
            "rank",
            "symbol",
            "name",
            "board",
            "industry",
            "score",
            "level",
            "one_year_pct_chg",
            "market_cap",
            "pe_ttm",
            "pb_lf",
        ):
            self.assertIn(f'<th data-master-column="{column}">', complete)
            self.assertIn(f'data-master-column="{column}"', complete)

    def test_compact_overview_and_table_contracts_keep_the_entry_and_core_columns_visible(self) -> None:
        report = self.render_optional_field_report()

        self.assertIn(
            '.overview-shell{grid-template-areas:"lead" "preview" "open" "facts" "flow"}',
            report,
        )
        self.assertIn(
            '.overview-shell{grid-template-areas:"lead" "open" "preview" "facts" "flow"}',
            report,
        )
        self.assertIn("stacked: ['lead', 'preview', 'open', 'facts', 'flow']", report)
        self.assertIn("compact: ['lead', 'open', 'preview', 'facts', 'flow']", report)
        metrics = report.split('<section class="pipeline-metrics"', 1)[1].split(
            "</section>",
            1,
        )[0]
        watch_card = metrics.split('class="pipeline-card watch"', 1)[1].split(
            "</button>",
            1,
        )[0]
        self.assertIn(
            'data-i18n-en="Watchlist" data-i18n-zh="观察名单">观察名单</span>',
            watch_card,
        )
        self.assertIn("<strong>1</strong>", watch_card)
        self.assertNotIn("min-width:860px", report)
        self.assertIn(
            ".master-table table,.master-table.has-wide-table table{min-width:100%;table-layout:fixed;white-space:normal}",
            report,
        )
        self.assertIn(
            '.master-table [data-master-column="board"],.master-table [data-master-column="industry"],.master-table [data-master-column="one_year_pct_chg"],.master-table [data-master-column="market_cap"],.master-table [data-master-column="pe_ttm"],.master-table [data-master-column="pb_lf"]{display:none}',
            report,
        )
        self.assertIn(
            ".field-coverage-grid{grid-template-columns:repeat(2,minmax(0,1fr))}",
            report,
        )


if __name__ == "__main__":
    unittest.main()
