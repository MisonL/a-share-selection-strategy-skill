from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import fetch_zzshare_a_share as fetcher  # noqa: E402
from zzshare_fetch_fakes import FakeDataApi, restore_module, valid_daily  # noqa: E402


class FetchZzshareCliArgTests(unittest.TestCase):
    def test_cli_invalid_date_returns_argument_error_without_outputs(self) -> None:
        stderr = self.assert_invalid_date_arguments("2026/05/20", "2026-05-21")
        self.assertIn("date must be YYYY-MM-DD or YYYYMMDD", stderr)

    def test_cli_impossible_calendar_date_returns_argument_error(self) -> None:
        stderr = self.assert_invalid_date_arguments("2026-99-99", "2026-05-21")
        self.assertIn("date must be a real calendar date", stderr)

    def test_cli_reversed_date_range_returns_argument_error(self) -> None:
        stderr = self.assert_invalid_date_arguments("2026-05-22", "2026-05-21")
        self.assertIn("start-date must be earlier than or equal to end-date", stderr)

    def test_cli_non_positive_timeout_returns_argument_error_without_outputs(self) -> None:
        stderr = self.assert_invalid_arguments(
            [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-20",
                "--end-date",
                "2026-05-21",
                "--timeout-seconds",
                "0",
            ]
        )
        self.assertIn("timeout-seconds must be positive", stderr)

    def test_cli_non_finite_timeout_returns_argument_error_without_outputs(self) -> None:
        for value in ["nan", "inf"]:
            with self.subTest(value=value):
                stderr = self.assert_invalid_arguments(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-21",
                        "--timeout-seconds",
                        value,
                    ]
                )
                self.assertIn("timeout-seconds must be finite", stderr)

    def test_cli_non_positive_limit_returns_argument_error_without_outputs(self) -> None:
        stderr = self.assert_invalid_arguments(
            [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-20",
                "--end-date",
                "2026-05-21",
                "--limit",
                "0",
            ]
        )
        self.assertIn("limit must be positive", stderr)

    def test_cli_non_positive_max_pages_returns_argument_error_without_outputs(self) -> None:
        stderr = self.assert_invalid_arguments(
            [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-20",
                "--end-date",
                "2026-05-21",
                "--max-pages",
                "0",
            ]
        )
        self.assertIn("max-pages must be positive", stderr)

    def test_cli_rejects_invalid_rate_limit_budgets(self) -> None:
        cases = [
            ("--max-429-events", "0", "max-429-events must be positive"),
            (
                "--max-rate-limit-sleep-seconds",
                "nan",
                "max-rate-limit-sleep-seconds must be finite",
            ),
            ("--max-runtime-seconds", "0", "max-runtime-seconds must be positive"),
        ]
        for option, value, message in cases:
            with self.subTest(option=option, value=value):
                stderr = self.assert_invalid_arguments(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-21",
                        option,
                        value,
                    ]
                )
                self.assertIn(message, stderr)

    def test_cli_negative_request_interval_returns_argument_error_without_outputs(self) -> None:
        stderr = self.assert_invalid_arguments(
            [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-20",
                "--end-date",
                "2026-05-21",
                "--request-interval-seconds",
                "-1",
            ]
        )
        self.assertIn("request-interval-seconds must be non-negative", stderr)

    def test_cli_non_positive_max_concurrent_requests_returns_argument_error_without_outputs(
        self,
    ) -> None:
        stderr = self.assert_invalid_arguments(
            [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-20",
                "--end-date",
                "2026-05-21",
                "--max-concurrent-symbol-requests",
                "0",
            ]
        )
        self.assertIn("max-concurrent-symbol-requests must be positive", stderr)

    def test_cli_non_finite_request_interval_returns_argument_error_without_outputs(
        self,
    ) -> None:
        for value in ["nan", "inf"]:
            with self.subTest(value=value):
                stderr = self.assert_invalid_arguments(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-21",
                        "--request-interval-seconds",
                        value,
                    ]
                )
                self.assertIn("request-interval-seconds must be finite", stderr)

    def test_cli_invalid_symbol_returns_argument_error_without_outputs(self) -> None:
        stderr = self.assert_invalid_arguments(
            [
                "--symbols",
                "BAD001",
                "--start-date",
                "2026-05-20",
                "--end-date",
                "2026-05-21",
            ]
        )
        self.assertIn("symbols must be six digits: BAD001", stderr)

    def test_cli_accepts_symbols_file_for_argument_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            symbols_file = Path(tmpdir) / "symbols.txt"
            symbols_file.write_text("000001\n600000\n", encoding="utf-8")
            fake_api = FakeDataApi(
                {
                    "000001.SZ": valid_daily(),
                    "600000.SH": valid_daily(ts_code="600000.SH"),
                }
            )
            old_module = sys.modules.get("zzshare.client")
            sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
            try:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                        "--symbols-file",
                        str(symbols_file),
                        "--start-date",
                        "2026-05-20",
                        "--end-date",
                        "2026-05-21",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata),
                        "--request-interval-seconds",
                        "0",
                    ]
                    )
                data = json.loads(metadata.read_text(encoding="utf-8"))
            finally:
                restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertIn("OK:", stdout.getvalue())
        self.assertEqual(["000001", "600000"], data["requested_symbols"])

    def test_cli_rejects_symbols_and_symbols_file_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            symbols_file = Path(tmpdir) / "symbols.txt"
            symbols_file.write_text("000001\n", encoding="utf-8")
            stderr = self.assert_invalid_arguments(
                [
                    "--symbols",
                    "000001",
                    "--symbols-file",
                    str(symbols_file),
                    "--start-date",
                    "2026-05-20",
                    "--end-date",
                    "2026-05-21",
                ]
            )

        self.assertIn("use either --symbols or --symbols-file", stderr)

    def test_cli_missing_symbols_file_returns_invalid_argument(self) -> None:
        stderr = self.assert_invalid_arguments(
            [
                "--symbols-file",
                "/tmp/zzshare-symbols-file-does-not-exist.txt",
                "--start-date",
                "2026-05-20",
                "--end-date",
                "2026-05-21",
            ]
        )

        self.assertIn("symbols file not found", stderr)

    def test_cli_directory_symbols_file_returns_invalid_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stderr = self.assert_invalid_arguments(
                [
                    "--symbols-file",
                    tmpdir,
                    "--start-date",
                    "2026-05-20",
                    "--end-date",
                    "2026-05-21",
                ]
            )

        self.assertIn("symbols file is a directory", stderr)

    def test_cli_missing_dependency_removes_stale_metadata(self) -> None:
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = None
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                output.write_text("stale\n", encoding="utf-8")
                metadata.write_text('{"stale": true}\n', encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()

                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001",
                            "--start-date",
                            "2026-05-20",
                            "--end-date",
                            "2026-05-21",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                        ]
                    )
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(2, code)
        self.assertEqual("", stdout.getvalue())
        self.assertFalse(output.exists())
        self.assertFalse(metadata.exists())
        self.assertIn("code=fetch_failed", stderr.getvalue())
        self.assertIn("output_written=false", stderr.getvalue())
        self.assertIn("metadata_output_written=false", stderr.getvalue())

    def assert_invalid_date_arguments(self, start_date: str, end_date: str) -> str:
        return self.assert_invalid_arguments(
            [
                "--symbols",
                "000001",
                "--start-date",
                start_date,
                "--end-date",
                end_date,
            ]
        )

    def assert_invalid_arguments(self, arguments: list[str]) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "prices.csv"
            metadata = Path(tmpdir) / "metadata.json"
            output.write_text("stale\n", encoding="utf-8")
            metadata.write_text('{"stale": true}\n', encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = fetcher.main(
                    [
                        *arguments,
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata),
                    ]
                )

            self.assertEqual(2, code)
            self.assertEqual("", stdout.getvalue())
            self.assertFalse(output.exists())
            self.assertFalse(metadata.exists())
            self.assertIn("code=invalid_argument", stderr.getvalue())
            return stderr.getvalue()

    def test_cli_page_failure_metadata_keeps_page_context_and_prior_rows(self) -> None:
        fake_api = PagedFailureApi()
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()

                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--request-interval-seconds",
                            "0",
                            "--limit",
                            "1",
                            "--max-pages",
                            "2",
                        ]
                    )

                saved = json.loads(metadata.read_text(encoding="utf-8"))
                prices = pd.read_csv(output, dtype={"symbol": str})
        finally:
            restore_module("zzshare.client", old_module)

        failure = saved["failed_symbols"][0]
        self.assertEqual(0, code)
        self.assertTrue(stdout.getvalue().startswith("PARTIAL:"))
        self.assertEqual(1, len(prices))
        self.assertEqual(1, saved["symbols"][0]["pages_used"])
        self.assertEqual("000001", failure["symbol"])
        self.assertEqual("000001.SZ", failure["ts_code"])
        self.assertEqual(2, failure["page"])
        self.assertEqual(1, failure["offset"])
        self.assertEqual(1, failure["limit"])
        self.assertEqual("20260501", failure["start_date"])
        self.assertEqual("20260529", failure["end_date"])
        self.assertEqual("timeout from provider", failure["error"])


class PagedFailureApi:
    def factory(self, token: str = "", timeout: int = 10, http_url: str = ""):
        def daily(**kwargs):
            if int(kwargs["offset"]) == 0:
                return valid_daily()
            raise TimeoutError("timeout from provider")

        return types.SimpleNamespace(
            token=token,
            timeout=timeout,
            http_url=http_url,
            daily=daily,
        )


if __name__ == "__main__":
    unittest.main()
