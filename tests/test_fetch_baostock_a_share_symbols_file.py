from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
sys.path.insert(0, str(TESTS))

import test_fetch_baostock_a_share as baostock_suite  # noqa: E402


class FetchBaostockAShareSymbolsFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        baostock_suite.fetcher.ensure_runtime_dependencies()

    def test_main_accepts_utf8_bom_symbols_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            symbols_file = root / "symbols.txt"
            output = root / "prices.csv"
            metadata_output = root / "metadata.json"
            symbols_file.write_text(
                "\ufeffsz.000001\r\n000001,600000.SH\n600000\n",
                encoding="utf-8",
            )
            frame = baostock_suite.fetcher.pd.DataFrame(
                [baostock_suite.valid_row("000001", "2026-05-20")]
            )
            metadata = baostock_suite.metadata_for(["000001", "600000"], frame)

            with patch.object(
                baostock_suite.fetcher,
                "fetch_prices",
                return_value=(frame, metadata),
            ) as fetch_prices:
                code = baostock_suite.fetcher.main(
                    [
                        "--symbols-file",
                        str(symbols_file),
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-20",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata_output),
                    ]
                )

            passed_args = fetch_prices.call_args.args[0]
            saved = json.loads(metadata_output.read_text(encoding="utf-8"))
            output_exists = output.exists()

        self.assertEqual(0, code)
        self.assertEqual("000001,600000", passed_args.symbols)
        self.assertEqual(["000001", "600000"], saved["requested_symbols"])
        self.assertTrue(output_exists)

    def test_symbols_file_stably_deduplicates_before_baostock_fetch(self) -> None:
        class FakeBaostock:
            def __init__(self) -> None:
                self.queried_codes: list[str] = []
                self.logout_count = 0

            def login(self) -> SimpleNamespace:
                return SimpleNamespace(error_code="0", error_msg="")

            def logout(self) -> None:
                self.logout_count += 1

            def query_history_k_data_plus(
                self,
                code: str,
                _fields: str,
                **_kwargs: object,
            ) -> baostock_suite.FakeResult:
                self.queried_codes.append(code)
                result = baostock_suite.FakeResult(
                    [
                        [
                            "2026-05-20",
                            code,
                            "10.0",
                            "10.2",
                            "9.9",
                            "10.1",
                            "10.0",
                            "1.0",
                            "1000",
                            "10100",
                            "0.5",
                            "1",
                            "0",
                        ]
                    ]
                )
                result.error_code = "0"
                result.error_msg = ""
                return result

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            symbols_file = root / "symbols.txt"
            symbols_file.write_text(
                "sz.000001\n000001.SZ,600000\n600000.SH\n",
                encoding="utf-8",
            )
            args = baostock_suite.fetcher.build_parser().parse_args(
                [
                    "--symbols-file",
                    str(symbols_file),
                    "--start-date",
                    "2026-05-20",
                    "--end-date",
                    "2026-05-20",
                    "--output",
                    str(root / "prices.csv"),
                    "--metadata-output",
                    str(root / "metadata.json"),
                    "--missing-name-policy",
                    "blank",
                ]
            )
            fake = FakeBaostock()

            baostock_suite.fetcher.normalize_symbol_arguments(args)
            with patch.dict(sys.modules, {"baostock": fake}):
                frame, metadata = baostock_suite.fetcher.fetch_prices(args)

        self.assertEqual("000001,600000", args.symbols)
        self.assertEqual(["sz.000001", "sh.600000"], fake.queried_codes)
        self.assertEqual(1, fake.logout_count)
        self.assertEqual(["000001", "600000"], frame["symbol"].tolist())
        self.assertEqual(["000001", "600000"], metadata["requested_symbols"])

    def test_main_rejects_symbols_and_symbols_file_before_fetch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            symbols_file = root / "symbols.txt"
            output = root / "prices.csv"
            metadata_output = root / "metadata.json"
            symbols_file.write_text("000001\n", encoding="utf-8")
            output.write_text("stale\n", encoding="utf-8")
            metadata_output.write_text('{"stale": true}\n', encoding="utf-8")
            stderr = StringIO()

            with patch.object(
                baostock_suite.fetcher,
                "fetch_prices",
                side_effect=AssertionError("fetch must not run"),
            ), redirect_stderr(stderr):
                code = baostock_suite.fetcher.main(
                    [
                        "--symbols",
                        "000001",
                        "--symbols-file",
                        str(symbols_file),
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-20",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata_output),
                    ]
                )

        self.assertEqual(2, code)
        self.assertFalse(output.exists())
        self.assertFalse(metadata_output.exists())
        self.assertIn("code=invalid_argument", stderr.getvalue())
        self.assertIn("use either --symbols or --symbols-file", stderr.getvalue())
        self.assertIn(
            f"source_claim_boundary={baostock_suite.fetcher.CLAIM_BOUNDARY}",
            stderr.getvalue(),
        )

    def test_main_rejects_invalid_symbols_file_before_fetch(self) -> None:
        cases = (
            ("missing", "symbols file not found"),
            ("directory", "symbols file is a directory"),
            ("empty", "symbols file is empty"),
            ("invalid_encoding", "not valid UTF-8"),
        )
        for case, message in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                symbols_file = root / "symbols.txt"
                output = root / "prices.csv"
                metadata_output = root / "metadata.json"
                if case == "directory":
                    symbols_file.mkdir()
                elif case == "empty":
                    symbols_file.write_text(" \n,\n\t\n", encoding="utf-8")
                elif case == "invalid_encoding":
                    symbols_file.write_text("000001\n", encoding="utf-16")
                elif case == "missing":
                    symbols_file = root / "missing.txt"
                stderr = StringIO()

                with patch.object(
                    baostock_suite.fetcher,
                    "fetch_prices",
                    side_effect=AssertionError("fetch must not run"),
                ), redirect_stderr(stderr):
                    code = baostock_suite.fetcher.main(
                        [
                            "--symbols-file",
                            str(symbols_file),
                            "--start-date",
                            "2026-05-20",
                            "--end-date",
                            "2026-05-20",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata_output),
                        ]
                    )

                self.assertEqual(2, code)
                self.assertFalse(output.exists())
                self.assertFalse(metadata_output.exists())
                self.assertIn("code=invalid_argument", stderr.getvalue())
                self.assertIn(message, stderr.getvalue())
                self.assertIn(
                    f"source_claim_boundary={baostock_suite.fetcher.CLAIM_BOUNDARY}",
                    stderr.getvalue(),
                )
