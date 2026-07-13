from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import csv
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_baostock_a_share_universe as fetcher  # noqa: E402


class FetchBaostockAShareUniverseTests(unittest.TestCase):
    def test_cli_writes_symbol_only_spot_compatible_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "spot_metadata.json"
            stdout = StringIO()
            with patched_baostock(
                FakeBaostock(
                    all_stock=FakeAllStockResult(
                        [
                            ["sz.000001", "平安银行"],
                            ["sh.600000", "浦发银行"],
                            ["sz.159915", "创业板ETF"],
                            ["bj.430047", "诺思兰德"],
                        ],
                        fields=["code", "code_name"],
                    )
                )
            ):
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-partial",
                        ]
                    )

            rows = csv_rows(output)
            saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual(["000001", "600000"], [row["symbol"] for row in rows])
        self.assertEqual(["平安银行", "浦发银行"], [row["name"] for row in rows])
        self.assertTrue(all(row["spot_price"] == "" for row in rows))
        self.assertEqual("baostock", saved["source"])
        self.assertEqual("baostock_universe_snapshot", saved["source_scope"])
        self.assertTrue(saved["real_market_data"])
        self.assertFalse(saved["partial_result"])
        self.assertEqual(2, saved["raw_items"])
        self.assertEqual(4, saved["raw_row_count"])
        self.assertEqual(2, saved["filtered_items"])
        self.assertEqual(2, saved["symbol_count"])
        self.assertEqual(2, saved["excluded_count"])
        self.assertEqual(
            "symbol_universe_snapshot_not_realtime_spot_proof",
            saved["coverage_claim"],
        )
        self.assertEqual(fetcher.CLAIM_BOUNDARY, saved["source_claim_boundary"])
        self.assertIn("not a realtime quote", saved["data_source_note"])
        self.assertTrue(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertEqual(2, saved["max_attempts"])
        self.assertEqual(1, saved["fetch_attempts"])
        self.assertEqual(0, saved["fetch_error_count"])
        self.assertIn("source_scope=baostock_universe_snapshot", stdout.getvalue())

    def test_cli_lookback_resolves_previous_nonempty_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "spot_metadata.json"
            stdout = StringIO()
            fake = FakeBaostock(
                all_stock_by_day={
                    "2026-07-09": FakeAllStockResult([]),
                    "2026-07-08": FakeAllStockResult(
                        [["sz.000001", "平安银行"]],
                        fields=["code", "code_name"],
                    ),
                }
            )
            with patched_baostock(fake):
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--snapshot-date",
                            "2026-07-09",
                            "--lookback-days",
                            "2",
                            "--fail-on-partial",
                        ]
                    )

            rows = csv_rows(output)
            saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual(["000001"], [row["symbol"] for row in rows])
        self.assertEqual(["平安银行"], [row["name"] for row in rows])
        self.assertEqual("2026-07-09", saved["requested_snapshot_date"])
        self.assertEqual("2026-07-08", saved["resolved_snapshot_date"])
        self.assertEqual(2, saved["lookback_days"])
        self.assertTrue(saved["date_fallback_used"])
        self.assertEqual(["2026-07-09", "2026-07-08"], fake.query_days)
        self.assertEqual(
            ["2026-07-09", "2026-07-08"],
            [attempt["date"] for attempt in saved["attempted_dates"]],
        )
        self.assertEqual(1, saved["raw_row_count"])
        self.assertIn("date_fallback_used=true", stdout.getvalue())

    def test_cli_empty_universe_strict_failure_removes_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "spot_metadata.json"
            output.write_text("symbol,name\nSTALE,old\n", encoding="utf-8")
            metadata.write_text('{"stale": true}\n', encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            with patched_baostock(FakeBaostock(all_stock=FakeAllStockResult([]))):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-partial",
                        ]
                    )

            saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertTrue(saved["partial_result"])
        self.assertEqual(0, saved["raw_items"])
        self.assertEqual("partial_universe_not_full_market", saved["coverage_claim"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("raw_items=0", stderr.getvalue())

    def test_cli_login_failure_writes_failure_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "spot_metadata.json"
            output.write_text("symbol,name\nSTALE,old\n", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            fake = FakeBaostock(login_error_code="10002007", login_error_msg="reset")
            with patched_baostock(fake):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = fetcher.main(
                        [
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--fail-on-partial",
                            "--retries",
                            "0",
                        ]
                    )

            saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual("baostock login failed: 10002007 reset", saved["error"])
        self.assertTrue(saved["partial_result"])
        self.assertEqual(1, saved["fetch_attempts"])
        self.assertEqual(1, saved["max_attempts"])
        self.assertEqual(1, saved["fetch_error_count"])
        self.assertEqual(
            "baostock login failed: 10002007 reset",
            saved["fetch_errors"][0]["error"],
        )
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("partial_result=true", stderr.getvalue())

    def test_cli_removes_stale_metadata_when_initial_metadata_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "spot_metadata.json"
            output.write_text("symbol,name\nSTALE,old\n", encoding="utf-8")
            metadata.write_text('{"stale": true}\n', encoding="utf-8")
            stderr = StringIO()
            fake = FakeBaostock(
                all_stock=FakeAllStockResult(
                    [["sz.000001", "平安银行"]],
                    fields=["code", "code_name"],
                )
            )
            with (
                patched_baostock(fake),
                patch.object(
                    fetcher,
                    "write_json",
                    side_effect=OSError("metadata write failed"),
                ),
                redirect_stderr(stderr),
            ):
                code = fetcher.main(
                    [
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata),
                        "--fail-on-partial",
                    ]
                )

        self.assertEqual(2, code)
        self.assertFalse(output.exists())
        self.assertFalse(metadata.exists())
        self.assertIn("metadata_output_written=false", stderr.getvalue())

    def test_cli_retries_after_login_failure_and_records_prior_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "spot_metadata.json"
            fake = FakeBaostock(
                login_results=[
                    ("10002007", "reset"),
                    ("0", ""),
                ],
                all_stock=FakeAllStockResult(
                    [["sz.000001", "平安银行"]],
                    fields=["code", "code_name"],
                ),
            )
            with patched_baostock(fake):
                code = fetcher.main(
                    [
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata),
                        "--fail-on-partial",
                        "--retries",
                        "1",
                        "--retry-interval-seconds",
                        "0",
                    ]
                )

            rows = csv_rows(output)
            saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual(["000001"], [row["symbol"] for row in rows])
        self.assertEqual(2, saved["fetch_attempts"])
        self.assertEqual(2, saved["max_attempts"])
        self.assertEqual(1, saved["fetch_error_count"])
        self.assertEqual(
            "baostock login failed: 10002007 reset",
            saved["fetch_errors"][0]["error"],
        )
        self.assertTrue(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])

    def test_cli_retries_after_query_error_and_records_prior_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "spot_metadata.json"
            fake = FakeBaostock(
                all_stock_sequence=[
                    FakeAllStockResult(
                        [],
                        error_code="10002007",
                        error_msg="query reset",
                    ),
                    FakeAllStockResult(
                        [["sz.000001", "平安银行"]],
                        fields=["code", "code_name"],
                    ),
                ]
            )
            with patched_baostock(fake):
                code = fetcher.main(
                    [
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata),
                        "--fail-on-partial",
                        "--snapshot-date",
                        "2026-07-09",
                        "--retries",
                        "1",
                        "--retry-interval-seconds",
                        "0",
                    ]
                )

            rows = csv_rows(output)
            saved = json.loads(metadata.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual(["000001"], [row["symbol"] for row in rows])
        self.assertEqual(2, saved["fetch_attempts"])
        self.assertEqual(1, saved["fetch_error_count"])
        self.assertIn("query_all_stock failed", saved["fetch_errors"][0]["error"])
        self.assertEqual(
            "2026-07-09",
            saved["fetch_errors"][0]["attempted_dates"][0]["date"],
        )
        self.assertEqual(["2026-07-09", "2026-07-09"], fake.query_days)
        self.assertEqual("2026-07-09", saved["attempted_dates"][0]["date"])


class patched_baostock:
    def __init__(self, fake_module: object) -> None:
        self.fake_module = fake_module
        self.previous = None
        self.had_previous = False

    def __enter__(self) -> None:
        self.had_previous = "baostock" in sys.modules
        self.previous = sys.modules.get("baostock")
        sys.modules["baostock"] = self.fake_module

    def __exit__(self, *_exc: object) -> None:
        if self.had_previous:
            sys.modules["baostock"] = self.previous
        else:
            sys.modules.pop("baostock", None)


class FakeBaostock(types.SimpleNamespace):
    def __init__(
        self,
        *,
        all_stock: "FakeAllStockResult | None" = None,
        all_stock_sequence: list["FakeAllStockResult"] | None = None,
        all_stock_by_day: dict[str, "FakeAllStockResult"] | None = None,
        login_error_code: str = "0",
        login_error_msg: str = "",
        login_results: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self.all_stock = all_stock or FakeAllStockResult([])
        self.all_stock_sequence = list(all_stock_sequence or [])
        self.all_stock_by_day = all_stock_by_day or {}
        self.login_error_code = login_error_code
        self.login_error_msg = login_error_msg
        self.login_results = list(login_results or [])
        self.logout_called = False
        self.query_days = []

    def login(self) -> object:
        if self.login_results:
            code, message = self.login_results.pop(0)
            return types.SimpleNamespace(error_code=code, error_msg=message)
        return types.SimpleNamespace(
            error_code=self.login_error_code,
            error_msg=self.login_error_msg,
        )

    def logout(self) -> None:
        self.logout_called = True

    def query_all_stock(self, day: str | None = None) -> "FakeAllStockResult":
        self.query_days.append(day)
        if self.all_stock_sequence:
            return self.all_stock_sequence.pop(0)
        return self.all_stock_by_day.get(str(day), self.all_stock)


class FakeAllStockResult:
    def __init__(
        self,
        rows: list[list[str]],
        *,
        fields: list[str] | None = None,
        error_code: str = "0",
        error_msg: str = "",
    ) -> None:
        self.rows = rows
        self.fields = fields or ["code"]
        self.error_code = error_code
        self.error_msg = error_msg
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
