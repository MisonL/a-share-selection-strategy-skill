from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_baostock_a_share as fetcher  # noqa: E402
from lib.selection_core.a_share_selection_tradability import tradability_stats  # noqa: E402


HAS_PARQUET_ENGINE = any(
    importlib.util.find_spec(name) for name in ("pyarrow", "fastparquet")
)


class FetchBaostockAShareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fetcher.ensure_runtime_dependencies()

    def test_parse_symbols_requires_six_digits(self) -> None:
        self.assertEqual(["000001", "600000"], fetcher.parse_symbols("000001,600000"))
        with self.assertRaisesRegex(ValueError, "six digits"):
            fetcher.parse_symbols("1")

    def test_parse_symbols_rejects_bj_prefix_instead_of_routing_to_sz(self) -> None:
        with self.assertRaisesRegex(ValueError, "bj.430047"):
            fetcher.parse_symbols("bj.430047")

    def test_help_discloses_csv_and_parquet_outputs(self) -> None:
        help_text = fetcher.build_parser().format_help()

        self.assertIn("Output CSV or Parquet path", help_text)
        self.assertIn("--symbols-file", help_text)

    def test_collect_rows_maps_ohlcv_amount_and_name(self) -> None:
        result = FakeResult(
            [
                [
                    "2026-05-20",
                    "sz.000001",
                    "10.0",
                    "10.2",
                    "9.9",
                    "10.1",
                    "10.0",
                    "1.0000",
                    "1000",
                    "10100",
                    "0.5",
                    "1",
                    "0",
                ]
            ]
        )
        rows = fetcher.collect_rows(result, "000001", "平安银行")
        self.assertEqual("000001", rows[0]["symbol"])
        self.assertEqual("平安银行", rows[0]["name"])
        self.assertEqual("A-share", rows[0]["market"])
        self.assertEqual("1000", rows[0]["volume"])
        self.assertEqual("10100", rows[0]["amount"])
        self.assertEqual("0.5", rows[0]["turn"])
        self.assertEqual("10.0", rows[0]["preclose"])
        self.assertEqual("1", rows[0]["tradestatus"])

    def test_fetch_symbol_names_uses_baostock_stock_basic(self) -> None:
        fake = FakeBaostockBasic(
            {
                "sz.000001": FakeBasicResult([["sz.000001", "平安银行"]]),
                "sh.600000": FakeBasicResult([["sh.600000", "浦发银行"]]),
            }
        )

        lookup = fetcher.fetch_symbol_names(fake, ["000001", "600000"])

        self.assertEqual(
            {"000001": "平安银行", "600000": "浦发银行"},
            lookup["names"],
        )
        self.assertEqual("baostock_query_stock_basic", lookup["source"])
        self.assertEqual([], lookup["failed_symbols"])
        self.assertEqual([], lookup["missing_symbols"])

    def test_fetch_symbol_names_reports_missing_and_failed_names(self) -> None:
        fake = FakeBaostockBasic(
            {
                "sz.000001": FakeBasicResult([]),
                "sh.600000": FakeBasicResult([], error_code="100", error_msg="offline"),
            }
        )

        lookup = fetcher.fetch_symbol_names(fake, ["000001", "600000"])

        self.assertEqual({}, lookup["names"])
        self.assertEqual(["000001"], lookup["missing_symbols"])
        self.assertEqual(
            [{"symbol": "600000", "error": "offline"}],
            lookup["failed_symbols"],
        )

    def test_names_input_avoids_stock_basic_queries_when_complete(self) -> None:
        fake = FakeBaostockBasic({})
        with tempfile.TemporaryDirectory() as tmpdir:
            names_input = Path(tmpdir) / "universe.csv"
            names_input.write_text(
                "symbol,name\n000001,平安银行\n600000,浦发银行\n",
                encoding="utf-8",
            )
            lookup = fetcher.resolve_symbol_names(
                fake,
                ["000001", "600000"],
                str(names_input),
                "query",
            )

        self.assertEqual(0, fake.query_count)
        self.assertEqual(2, lookup["input_name_count"])
        self.assertEqual(0, lookup["query_count"])
        self.assertEqual("names_input", lookup["source"])
        self.assertEqual([], lookup["missing_symbols"])

    def test_names_input_queries_only_missing_symbols(self) -> None:
        fake = FakeBaostockBasic(
            {"sh.600000": FakeBasicResult([["sh.600000", "浦发银行"]])}
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            names_input = Path(tmpdir) / "universe.csv"
            names_input.write_text(
                "symbol,name\n000001,平安银行\n", encoding="utf-8"
            )
            lookup = fetcher.resolve_symbol_names(
                fake,
                ["000001", "600000"],
                str(names_input),
                "query",
            )

        self.assertEqual(["sh.600000"], fake.queried_codes)
        self.assertEqual(1, lookup["query_count"])
        self.assertEqual(
            {"000001": "平安银行", "600000": "浦发银行"}, lookup["names"]
        )

    def test_missing_name_fail_policy_does_not_query(self) -> None:
        fake = FakeBaostockBasic({})
        lookup = fetcher.resolve_symbol_names(fake, ["000001"], "", "fail")
        metadata = metadata_for(
            ["000001"], fetcher.pd.DataFrame([valid_row("000001", "2026-05-20")])
        )
        metadata.update(
            {
                "missing_name_policy": "fail",
                "name_lookup_missing_symbols": lookup["missing_symbols"],
            }
        )

        self.assertEqual(0, fake.query_count)
        self.assertEqual(["000001"], lookup["missing_symbols"])
        self.assertIn(
            "name_lookup_missing_symbols=1",
            fetcher.strict_gate_errors(metadata, fail_on_fetch_error=False),
        )

    def test_missing_name_blank_policy_is_explicitly_accepted(self) -> None:
        fake = FakeBaostockBasic({})
        lookup = fetcher.resolve_symbol_names(fake, ["000001"], "", "blank")
        metadata = metadata_for(
            ["000001"], fetcher.pd.DataFrame([valid_row("000001", "2026-05-20")])
        )
        metadata.update(
            {
                "missing_name_policy": "blank",
                "name_lookup_missing_symbols": lookup["missing_symbols"],
            }
        )

        self.assertEqual(["000001"], lookup["missing_symbols"])
        self.assertNotIn(
            "name_lookup_missing_symbols=1",
            fetcher.strict_gate_errors(metadata, fail_on_fetch_error=True),
        )

    def test_collect_a_share_stock_symbols_excludes_funds_indices_and_b_shares(
        self,
    ) -> None:
        result = FakeAllStockResult(
            [
                ["sz.000001", "平安银行"],
                ["sz.001220", "源飞宠物"],
                ["sz.300750", "宁德时代"],
                ["sh.600000", "浦发银行"],
                ["sh.688981", "中芯国际"],
                ["sz.159915", "创业板ETF"],
                ["sh.588000", "科创50ETF"],
                ["sh.000001", "上证指数"],
                ["sz.399001", "深证成指"],
                ["sz.200001", "深物业B"],
                ["sh.900901", "云赛B股"],
                ["bj.430047", "诺思兰德"],
            ],
            fields=["code", "code_name"],
        )

        collected = fetcher.collect_a_share_stock_symbols(result)

        self.assertEqual(
            ["000001", "001220", "300750", "600000", "688981"],
            collected["symbols"],
        )
        self.assertEqual(5, collected["symbol_count"])
        self.assertEqual(12, collected["raw_row_count"])
        self.assertEqual("平安银行", collected["names"]["000001"])
        self.assertEqual("中芯国际", collected["names"]["688981"])
        self.assertEqual(7, collected["excluded_count"])
        self.assertTrue(fetcher.is_baostock_a_share_stock_code("sz.000001"))
        self.assertFalse(fetcher.is_baostock_a_share_stock_code("sz.159915"))
        self.assertFalse(fetcher.is_baostock_a_share_stock_code("sh.588000"))

    def test_collect_a_share_stock_symbols_accepts_row_dicts(self) -> None:
        rows = [
            {"code": "sz.000001", "code_name": "平安银行"},
            {"code": "sz.159915"},
            {"code": "sh.600000"},
            {"code": "bj.430047"},
        ]

        collected = fetcher.collect_a_share_stock_symbols(rows)

        self.assertEqual(["000001", "600000"], collected["symbols"])
        self.assertEqual({"000001": "平安银行"}, collected["names"])
        self.assertEqual(4, collected["raw_row_count"])
        self.assertEqual(2, collected["symbol_count"])
        self.assertEqual(2, collected["excluded_count"])

    def test_baostock_a_share_stock_code_filter_handles_boundaries(self) -> None:
        self.assertFalse(fetcher.is_baostock_a_share_stock_code(""))
        self.assertFalse(fetcher.is_baostock_a_share_stock_code("sz.12"))
        self.assertFalse(fetcher.is_baostock_a_share_stock_code("sh.600000X"))
        self.assertFalse(fetcher.is_baostock_a_share_stock_code("sz.600000"))
        self.assertFalse(fetcher.is_baostock_a_share_stock_code("sh.300001"))
        self.assertTrue(fetcher.is_baostock_a_share_stock_code("SZ.000001"))
        self.assertTrue(fetcher.is_baostock_a_share_stock_code("SH.688981"))

    def test_tradability_stats_handles_missing_symbol_column(self) -> None:
        frame = fetcher.pd.DataFrame([{"tradestatus": "0", "isST": "1"}])

        stats = tradability_stats(frame)

        self.assertEqual(1, stats["non_trading_rows"])
        self.assertEqual([], stats["non_trading_symbols"])
        self.assertEqual(1, stats["st_rows"])
        self.assertEqual([], stats["st_symbols"])

    def test_write_outputs_writes_metadata_json(self) -> None:
        metadata = {
            "source": "baostock",
            "rows": 1,
            "symbol_count": 1,
            "failed_symbols": [],
            "start_date": "2026-05-20",
            "end_date": "2026-05-20",
            "adjustflag": "3",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            meta = Path(tmpdir) / "metadata.json"
            frame = fetcher.pd.DataFrame([{"symbol": "000001"}])
            fetcher.write_outputs(
                frame,
                metadata,
                output,
                meta,
                output_format="csv",
            )
            self.assertTrue(output.exists())
            saved = json.loads(meta.read_text(encoding="utf-8"))
        self.assertEqual("baostock", saved["source"])

    @unittest.skipUnless(HAS_PARQUET_ENGINE, "parquet engine is required")
    def test_main_writes_parquet_with_explicit_format_metadata(self) -> None:
        for suffix in [".parquet", ".pq"]:
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / f"prices{suffix}"
                meta = Path(tmpdir) / "metadata.json"
                frame = fetcher.pd.DataFrame(
                    [valid_row("000001", "2026-05-20")]
                )
                metadata = metadata_for(["000001"], frame)

                with patch.object(
                    fetcher, "fetch_prices", return_value=(frame, metadata)
                ):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001",
                            "--start-date",
                            "2026-05-20",
                            "--end-date",
                            "2026-05-20",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(meta),
                        ]
                    )

                saved_frame = fetcher.pd.read_parquet(output)
                saved = json.loads(meta.read_text(encoding="utf-8"))

            self.assertEqual(0, code)
            self.assertEqual(["000001"], saved_frame["symbol"].astype(str).tolist())
            self.assertEqual("parquet", saved["output_format"])
            self.assertEqual(str(output), saved["output_path"])

    def test_main_rejects_missing_parquet_engine_before_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.parquet"
            meta = Path(tmpdir) / "metadata.json"
            output.write_text("stale\n", encoding="utf-8")
            meta.write_text('{"stale": true}\n', encoding="utf-8")
            stderr = StringIO()

            with patch.object(
                fetcher.importlib.util,
                "find_spec",
                return_value=None,
            ), patch.object(
                fetcher,
                "fetch_prices",
                side_effect=AssertionError("fetch must not run"),
            ), redirect_stderr(stderr):
                code = fetcher.main(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-20",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(meta),
                    ]
                )

            output_exists = output.exists()
            metadata_exists = meta.exists()

        self.assertEqual(2, code)
        self.assertFalse(output_exists)
        self.assertFalse(metadata_exists)
        self.assertIn("code=missing_dependency", stderr.getvalue())
        self.assertIn("pyarrow or fastparquet", stderr.getvalue())
        self.assertIn(
            f"source_claim_boundary={fetcher.CLAIM_BOUNDARY}", stderr.getvalue()
        )

    def test_main_rejects_unsupported_output_before_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.txt"
            meta = Path(tmpdir) / "metadata.json"
            output.write_text("stale\n", encoding="utf-8")
            meta.write_text('{"stale": true}\n', encoding="utf-8")
            stderr = StringIO()

            with patch.object(
                fetcher,
                "fetch_prices",
                side_effect=AssertionError("fetch must not run"),
            ), redirect_stderr(stderr):
                code = fetcher.main(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-20",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(meta),
                    ]
                )

            output_exists = output.exists()
            metadata_exists = meta.exists()

        self.assertEqual(2, code)
        self.assertFalse(output_exists)
        self.assertFalse(metadata_exists)
        self.assertIn("unsupported prices output format", stderr.getvalue())
        self.assertIn(
            f"source_claim_boundary={fetcher.CLAIM_BOUNDARY}", stderr.getvalue()
        )

    def test_main_rejects_same_prices_and_metadata_output_before_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            output.write_text("stale\n", encoding="utf-8")
            stderr = StringIO()

            with patch.object(
                fetcher,
                "fetch_prices",
                side_effect=AssertionError("fetch must not run"),
            ), redirect_stderr(stderr):
                code = fetcher.main(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-20",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(output),
                    ]
                )

            output_exists = output.exists()

        self.assertEqual(2, code)
        self.assertFalse(output_exists)
        self.assertIn("prices output and metadata output must differ", stderr.getvalue())
        self.assertIn(
            f"source_claim_boundary={fetcher.CLAIM_BOUNDARY}", stderr.getvalue()
        )

    def test_build_metadata_includes_standalone_source_boundary_fields(self) -> None:
        args = argparse_namespace("000001")
        frame = fetcher.pd.DataFrame([valid_row("000001", "2026-05-20")])
        metadata = fetcher.build_metadata(
            args,
            frame,
            [fetcher.symbol_metadata_for_frame("000001", frame)],
            [],
        )

        self.assertEqual("external_fetch", metadata["source_type"])
        self.assertEqual("baostock_history_fetch", metadata["source_scope"])
        self.assertTrue(metadata["real_market_data"])
        self.assertFalse(metadata["partial_result"])
        self.assertEqual(fetcher.CLAIM_BOUNDARY, metadata["source_claim_boundary"])
        self.assertIn("scope is requested symbols", metadata["data_source_note"])

    def test_strict_failure_removes_stale_output_and_keeps_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            meta = Path(tmpdir) / "metadata.json"
            output.write_text(
                "symbol,date,close\nSTALE,2026-01-01,1\n", encoding="utf-8"
            )
            meta.write_text('{"stale": true}\n', encoding="utf-8")
            old_main = fetcher.fetch_prices
            stdout = StringIO()
            stderr = StringIO()
            try:

                def fake_fetch_prices(_args):
                    frame = fetcher.pd.DataFrame([valid_row("000001", "2026-05-20")])
                    metadata = metadata_for(["000001"], frame)
                    metadata["failed_symbols"] = [
                        {"symbol": "000001", "error": "offline"}
                    ]
                    metadata["empty_symbols"] = ["000001"]
                    metadata["symbol_count"] = 0
                    return frame, metadata

                fetcher.fetch_prices = fake_fetch_prices  # type: ignore[assignment]
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001",
                            "--start-date",
                            "2026-05-20",
                            "--end-date",
                            "2026-05-20",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(meta),
                            "--fail-on-fetch-error",
                        ]
                    )
            finally:
                fetcher.fetch_prices = old_main  # type: ignore[assignment]

            saved = json.loads(meta.read_text(encoding="utf-8"))
            output_exists = output.exists()
            meta_exists = meta.exists()

        self.assertEqual(3, code)
        self.assertFalse(output_exists)
        self.assertTrue(meta_exists)
        self.assertEqual(
            [{"symbol": "000001", "error": "offline"}], saved["failed_symbols"]
        )
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertTrue(saved["partial_result"])
        self.assertEqual("csv", saved["output_format"])
        self.assertEqual("baostock_history_fetch", saved["source_scope"])
        self.assertEqual(fetcher.CLAIM_BOUNDARY, saved["source_claim_boundary"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn(
            "output_written=false metadata_output_written=true", stderr.getvalue()
        )
        self.assertIn(
            f"source_claim_boundary={fetcher.CLAIM_BOUNDARY}", stderr.getvalue()
        )

    def test_fetch_failure_removes_stale_output_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.parquet"
            meta = Path(tmpdir) / "metadata.json"
            output.write_text("stale\n", encoding="utf-8")
            meta.write_text('{"stale": true}\n', encoding="utf-8")
            stderr = StringIO()

            with patch.object(
                fetcher,
                "fetch_prices",
                side_effect=RuntimeError("offline"),
            ), redirect_stderr(stderr):
                code = fetcher.main(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-20",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(meta),
                    ]
                )

            output_exists = output.exists()
            metadata_exists = meta.exists()

        self.assertEqual(2, code)
        self.assertFalse(output_exists)
        self.assertFalse(metadata_exists)
        self.assertIn("code=fetch_failed", stderr.getvalue())
        self.assertIn(
            f"source_claim_boundary={fetcher.CLAIM_BOUNDARY}", stderr.getvalue()
        )

    def test_partial_default_stdout_discloses_partial_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            meta = Path(tmpdir) / "metadata.json"
            old_main = fetcher.fetch_prices
            stdout = StringIO()
            try:

                def fake_fetch_prices(_args):
                    frame = fetcher.pd.DataFrame([valid_row("000001", "2026-05-20")])
                    metadata = metadata_for(["000001", "600000"], frame)
                    metadata["empty_symbols"] = ["600000"]
                    metadata["symbol_count"] = 1
                    return frame, metadata

                fetcher.fetch_prices = fake_fetch_prices  # type: ignore[assignment]
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
                            "--start-date",
                            "2026-05-20",
                            "--end-date",
                            "2026-05-20",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(meta),
                        ]
                    )
            finally:
                fetcher.fetch_prices = old_main  # type: ignore[assignment]

            saved = json.loads(meta.read_text(encoding="utf-8"))
            output_exists = output.exists()

        self.assertEqual(0, code)
        self.assertTrue(output_exists)
        self.assertTrue(saved["output_written"])
        self.assertEqual(["600000"], saved["empty_symbols"])
        self.assertTrue(saved["partial_result"])
        self.assertEqual("baostock_history_fetch", saved["source_scope"])
        self.assertTrue(stdout.getvalue().startswith("PARTIAL:"))
        self.assertIn("empty_symbols=1", stdout.getvalue())

    def test_quality_policy_reports_invalid_rows_without_dropping(self) -> None:
        frame = fetcher.pd.DataFrame(
            [
                valid_row("000001", "2026-05-20"),
                {
                    **valid_row("688981", "2025-09-01"),
                    "volume": "",
                    "amount": "",
                    "turn": "",
                    "tradestatus": "0",
                },
            ]
        )
        metadata = metadata_for(["000001", "688981"], frame)
        result, updated = fetcher.apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=False,
        )
        self.assertEqual(2, len(result))
        self.assertEqual(1, updated["invalid_rows"])
        self.assertEqual(["688981"], updated["invalid_symbols"])
        self.assertEqual(
            ["volume", "amount", "turn"],
            updated["invalid_row_examples"][0]["invalid_columns"],
        )
        self.assertIn(
            "invalid_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )
        self.assertIn(
            "non_trading_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )

    def test_quality_policy_can_explicitly_drop_invalid_rows(self) -> None:
        frame = fetcher.pd.DataFrame(
            [
                valid_row("000001", "2026-05-20"),
                {**valid_row("688981", "2025-09-01"), "volume": "", "tradestatus": "0"},
            ]
        )
        metadata = metadata_for(["000001", "688981"], frame)
        result, updated = fetcher.apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=True,
        )
        self.assertEqual(["000001"], result["symbol"].tolist())
        self.assertEqual(1, updated["dropped_invalid_rows"])
        self.assertEqual(1, updated["raw_non_trading_rows"])
        self.assertEqual(1, updated["raw_invalid_non_trading_overlap_rows"])
        self.assertEqual(
            "raw_dimension_counts_not_additive",
            updated["raw_quality_counter_semantics"],
        )
        self.assertIn("688981", updated["empty_symbols"])
        self.assertEqual(["688981"], updated["non_trading_only_empty_symbols"])
        self.assertEqual(2, len(updated["raw_symbols"]))
        self.assertEqual("2025-09-01", updated["raw_symbols"][1]["date_max"])
        self.assertNotIn(
            "invalid_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )
        self.assertNotIn(
            "non_trading_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )
        self.assertIn(
            "empty_symbols=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )

    def test_strict_gate_rejects_non_trading_rows(self) -> None:
        frame = fetcher.pd.DataFrame(
            [{**valid_row("688981", "2025-09-01"), "tradestatus": "0"}]
        )
        metadata = metadata_for(["688981"], frame)
        _result, updated = fetcher.apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=False,
        )
        errors = fetcher.strict_gate_errors(updated, fail_on_fetch_error=True)
        self.assertIn("non_trading_rows=1", errors)
        self.assertEqual(["688981"], updated["non_trading_symbols"])

    def test_non_trading_drop_policy_removes_and_records_rows(self) -> None:
        frame = fetcher.pd.DataFrame(
            [
                valid_row("000001", "2026-05-20"),
                {**valid_row("000001", "2026-05-19"), "tradestatus": "0"},
            ]
        )
        result, updated = fetcher.apply_quality_policy(
            frame,
            metadata_for(["000001"], frame),
            drop_invalid_rows=False,
            non_trading_policy="drop",
        )

        self.assertEqual(["2026-05-20"], result["date"].tolist())
        self.assertEqual(1, updated["raw_non_trading_rows"])
        self.assertEqual(0, updated["non_trading_rows"])
        self.assertEqual(1, updated["dropped_non_trading_rows"])
        self.assertNotIn(
            "non_trading_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )

    def test_non_trading_keep_policy_retains_rows_without_rejection(self) -> None:
        frame = fetcher.pd.DataFrame(
            [{**valid_row("000001", "2026-05-20"), "tradestatus": "0"}]
        )
        result, updated = fetcher.apply_quality_policy(
            frame,
            metadata_for(["000001"], frame),
            drop_invalid_rows=False,
            non_trading_policy="keep",
        )

        self.assertEqual(1, len(result))
        self.assertEqual(1, updated["non_trading_rows"])
        self.assertEqual(0, updated["dropped_non_trading_rows"])
        self.assertNotIn(
            "non_trading_rows=1",
            fetcher.strict_gate_errors(updated, fail_on_fetch_error=True),
        )

    def test_strict_gate_rejects_empty_symbol(self) -> None:
        metadata = {
            "requested_symbols": ["000001", "600000"],
            "symbol_count": 1,
            "failed_symbols": [],
            "empty_symbols": ["600000"],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
        }
        errors = fetcher.strict_gate_errors(metadata, fail_on_fetch_error=True)
        self.assertIn("empty_symbols=1", errors)
        self.assertIn("symbol_count=1 requested_symbols=2", errors)

    def test_strict_gate_rejects_missing_stock_names(self) -> None:
        metadata = {
            "requested_symbols": ["000001", "600000"],
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "name_lookup_failed_symbols": [{"symbol": "000001", "error": "offline"}],
            "name_lookup_missing_symbols": ["600000"],
        }

        errors = fetcher.strict_gate_errors(metadata, fail_on_fetch_error=True)

        self.assertIn("name_lookup_failed_symbols=1", errors)
        self.assertIn("name_lookup_missing_symbols=1", errors)


class FakeResult:
    fields = [
        "date",
        "code",
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "pctChg",
        "volume",
        "amount",
        "turn",
        "tradestatus",
        "isST",
    ]

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = rows
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBasicResult:
    fields = ["code", "code_name"]

    def __init__(
        self,
        rows: list[list[str]],
        *,
        error_code: str = "0",
        error_msg: str = "",
    ) -> None:
        self.rows = rows
        self.error_code = error_code
        self.error_msg = error_msg
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeAllStockResult:
    def __init__(
        self,
        rows: list[list[str]],
        *,
        fields: list[str] | None = None,
    ) -> None:
        self.rows = rows
        self.fields = fields or ["code"]
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


class FakeBaostockBasic:
    def __init__(self, results: dict[str, FakeBasicResult]) -> None:
        self.results = results
        self.queried_codes: list[str] = []

    @property
    def query_count(self) -> int:
        return len(self.queried_codes)

    def query_stock_basic(self, *, code: str) -> FakeBasicResult:
        self.queried_codes.append(code)
        return self.results[code]


def valid_row(symbol: str, date: str) -> dict[str, str]:
    return {
        "symbol": symbol,
        "name": symbol,
        "market": "A-share",
        "date": date,
        "open": "10.0",
        "high": "10.2",
        "low": "9.9",
        "close": "10.1",
        "preclose": "10.0",
        "pctChg": "1.0",
        "volume": "1000",
        "amount": "10100",
        "turn": "0.5",
        "tradestatus": "1",
        "isST": "0",
    }


def metadata_for(symbols: list[str], frame: fetcher.pd.DataFrame) -> dict:
    return {
        "source": "baostock",
        "source_type": "external_fetch",
        "source_scope": "baostock_history_fetch",
        "real_market_data": True,
        "partial_result": False,
        "source_claim_boundary": fetcher.CLAIM_BOUNDARY,
        "data_source_note": fetcher.DATA_SOURCE_NOTE,
        "requested_symbols": symbols,
        "start_date": "2025-01-01",
        "end_date": "2026-05-29",
        "adjustflag": "3",
        "rows": len(frame),
        "raw_rows": len(frame),
        "symbol_count": frame["symbol"].nunique(),
        "symbols": [
            fetcher.symbol_metadata_for_frame(symbol, frame) for symbol in symbols
        ],
        "failed_symbols": [],
        "empty_symbols": [],
        "invalid_rows": 0,
        "invalid_symbols": [],
        "invalid_row_examples": [],
        "dropped_invalid_rows": 0,
        "non_trading_policy": "reject",
        "dropped_non_trading_rows": 0,
    }


def argparse_namespace(symbols: str):
    return type(
        "Args",
        (),
        {
            "symbols": symbols,
            "start_date": "2026-05-01",
            "end_date": "2026-05-29",
            "adjust": "3",
        },
    )()


if __name__ == "__main__":
    unittest.main()
