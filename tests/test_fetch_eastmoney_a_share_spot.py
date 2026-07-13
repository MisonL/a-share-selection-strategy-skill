from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_eastmoney_a_share_spot as eastmoney  # noqa: E402


class FetchEastmoneyAShareSpotTests(unittest.TestCase):
    def test_page_url_sorts_by_stable_symbol_code(self) -> None:
        query = parse_qs(urlparse(eastmoney.page_url(2, 100)).query)

        self.assertEqual(["2"], query["pn"])
        self.assertEqual(["100"], query["pz"])
        self.assertEqual(["f12"], query["fid"])
        self.assertIn("f3", query["fields"][0])

    def test_fetch_snapshot_writes_rows_and_metadata(self) -> None:
        args = eastmoney.build_parser().parse_args(
            [
                "--output",
                "/tmp/spot.csv",
                "--metadata-output",
                "/tmp/meta.json",
                "--pages",
                "1",
            ]
        )

        rows, metadata = eastmoney.fetch_snapshot(args, FakeOpener())

        self.assertEqual(2, len(rows))
        self.assertEqual("000001", rows[0]["symbol"])
        self.assertEqual("eastmoney", metadata["source"])
        self.assertEqual("external_fetch", metadata["source_type"])
        self.assertEqual("a_share_spot_snapshot", metadata["source_scope"])
        self.assertTrue(metadata["real_market_data"])
        self.assertIn("scope is requested pages", metadata["data_source_note"])
        self.assertIn("stable symbol code", metadata["data_source_note"])
        self.assertEqual(1, metadata["successful_pages"])
        self.assertEqual(1, metadata["pages_successful"])
        self.assertEqual(1, metadata["attempted_pages"])
        self.assertFalse(metadata["stopped_early"])
        self.assertEqual(5, metadata["stop_after_empty_failed_pages"])
        self.assertEqual(0.0, metadata["request_interval_seconds"])
        self.assertEqual(0.0, metadata["retry_interval_seconds"])
        self.assertEqual(0, metadata["pages_failed"])
        self.assertEqual(1, metadata["retry_attempts_per_page"])
        self.assertEqual(1, metadata["retries"])
        self.assertEqual([], metadata["errors"])
        self.assertIsInstance(metadata["started_at"], str)
        self.assertIsInstance(metadata["finished_at"], str)
        self.assertGreaterEqual(metadata["duration_seconds"], 0.0)
        self.assertFalse(metadata["partial_result"])
        self.assertEqual(
            "requested_pages_snapshot_not_full_market_proof",
            metadata["coverage_claim"],
        )
        self.assertEqual(
            "requested_pages_snapshot_not_full_market_completion",
            metadata["source_claim_boundary"],
        )

    def test_cli_writes_partial_metadata_and_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "metadata.json"
            stdout = StringIO()
            stderr = StringIO()
            old_open_url = eastmoney.open_url
            eastmoney.open_url = FailingSecondPageOpener()
            try:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = eastmoney.main(
                        [
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--pages",
                            "2",
                            "--retries",
                            "0",
                            "--fail-on-partial",
                        ]
                    )
            finally:
                eastmoney.open_url = old_open_url
            data = json.loads(metadata.read_text(encoding="utf-8"))
            rows = pd.read_csv(output)

        self.assertEqual(3, code)
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("coverage_claim=partial_not_full_market", stdout.getvalue())
        self.assertIn(
            "source_claim_boundary=partial_spot_snapshot_not_full_market_completion",
            stdout.getvalue(),
        )
        self.assertIn("output_written=true", stdout.getvalue())
        self.assertIn("metadata_output_written=true", stdout.getvalue())
        self.assertIn("partial_result=true", stderr.getvalue())
        self.assertTrue(data["partial_result"])
        self.assertEqual("partial_not_full_market", data["coverage_claim"])
        self.assertEqual(
            "partial_spot_snapshot_not_full_market_completion",
            data["source_claim_boundary"],
        )
        self.assertEqual(1, len(data["failed_pages"]))
        self.assertEqual(1, len(data["errors"]))
        self.assertIn("remote disconnected", data["errors"][0])
        self.assertEqual(0, data["retries"])
        self.assertIsInstance(data["started_at"], str)
        self.assertIsInstance(data["finished_at"], str)
        self.assertGreaterEqual(data["duration_seconds"], 0.0)
        self.assertIn(
            "use_partial_snapshot_only_with_partial_result_disclosure",
            data["allowed_failure_actions"],
        )
        self.assertEqual(2, len(rows))

    def test_cli_default_partial_result_discloses_scope_without_strict_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "metadata.json"
            stdout = StringIO()
            stderr = StringIO()
            old_open_url = eastmoney.open_url
            eastmoney.open_url = FailingSecondPageOpener()
            try:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = eastmoney.main(
                        [
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--pages",
                            "2",
                            "--retries",
                            "0",
                        ]
                    )
            finally:
                eastmoney.open_url = old_open_url
            data = json.loads(metadata.read_text(encoding="utf-8"))
            output_exists = output.exists()

        self.assertEqual(0, code, stderr.getvalue())
        self.assertTrue(stdout.getvalue().startswith("PARTIAL:"))
        self.assertIn("partial_result=true", stdout.getvalue())
        self.assertIn("coverage_claim=partial_not_full_market", stdout.getvalue())
        self.assertIn(
            "source_claim_boundary=partial_spot_snapshot_not_full_market_completion",
            stdout.getvalue(),
        )
        self.assertIn("output_written=true", stdout.getvalue())
        self.assertIn("metadata_output_written=true", stdout.getvalue())
        self.assertEqual("partial_not_full_market", data["coverage_claim"])
        self.assertEqual(
            "partial_spot_snapshot_not_full_market_completion",
            data["source_claim_boundary"],
        )
        self.assertTrue(output_exists)

    def test_cli_raw_empty_strict_failure_removes_stale_output_and_keeps_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "spot.csv"
            metadata = Path(tmpdir) / "metadata.json"
            output.write_text("symbol,name\nSTALE,old\n", encoding="utf-8")
            metadata.write_text('{"stale": true}\n', encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            old_open_url = eastmoney.open_url
            eastmoney.open_url = EmptyOpener()
            try:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = eastmoney.main(
                        [
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--pages",
                            "1",
                            "--retries",
                            "0",
                        ]
                    )
            finally:
                eastmoney.open_url = old_open_url
            data = json.loads(metadata.read_text(encoding="utf-8"))
            output_exists = output.exists()
            metadata_exists = metadata.exists()

        self.assertEqual(3, code)
        self.assertFalse(output_exists)
        self.assertTrue(metadata_exists)
        self.assertEqual(0, data["raw_items"])
        self.assertFalse(data["output_written"])
        self.assertTrue(data["metadata_output_written"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("output_written=false", stdout.getvalue())
        self.assertIn("metadata_output_written=true", stdout.getvalue())
        self.assertIn("raw_items=0", stderr.getvalue())
        self.assertIn("output_written=false metadata_output_written=true", stderr.getvalue())

    def test_fetch_retries_page_before_marking_failure(self) -> None:
        args = eastmoney.build_parser().parse_args(
            [
                "--output",
                "/tmp/spot.csv",
                "--metadata-output",
                "/tmp/meta.json",
                "--pages",
                "1",
                "--retries",
                "2",
            ]
        )

        rows, metadata = eastmoney.fetch_snapshot(args, FailOnceOpener())

        self.assertEqual(2, len(rows))
        self.assertEqual(2, metadata["retry_attempts_per_page"])
        self.assertFalse(metadata["partial_result"])

    def test_retry_interval_is_used_between_attempts(self) -> None:
        args = eastmoney.build_parser().parse_args(
            [
                "--output",
                "/tmp/spot.csv",
                "--metadata-output",
                "/tmp/meta.json",
                "--pages",
                "1",
                "--retries",
                "1",
                "--retry-interval-seconds",
                "0.25",
            ]
        )
        sleeps = []
        old_sleep = eastmoney.time.sleep
        eastmoney.time.sleep = sleeps.append
        try:
            rows, metadata = eastmoney.fetch_snapshot(args, FailOnceOpener())
        finally:
            eastmoney.time.sleep = old_sleep

        self.assertEqual(2, len(rows))
        self.assertEqual([0.25], sleeps)
        self.assertEqual(0.25, metadata["retry_interval_seconds"])
        self.assertFalse(metadata["partial_result"])

    def test_request_interval_is_used_between_pages(self) -> None:
        args = eastmoney.build_parser().parse_args(
            [
                "--output",
                "/tmp/spot.csv",
                "--metadata-output",
                "/tmp/meta.json",
                "--pages",
                "3",
                "--request-interval-seconds",
                "0.25",
            ]
        )
        sleeps = []
        old_sleep = eastmoney.time.sleep
        eastmoney.time.sleep = sleeps.append
        try:
            rows, metadata = eastmoney.fetch_snapshot(args, FakeOpener())
        finally:
            eastmoney.time.sleep = old_sleep

        self.assertEqual(6, len(rows))
        self.assertEqual([0.25, 0.25], sleeps)
        self.assertEqual(0.25, metadata["request_interval_seconds"])
        self.assertFalse(metadata["partial_result"])

    def test_fetch_snapshot_stops_early_when_initial_pages_all_fail(self) -> None:
        args = eastmoney.build_parser().parse_args(
            [
                "--output",
                "/tmp/spot.csv",
                "--metadata-output",
                "/tmp/meta.json",
                "--pages",
                "300",
                "--retries",
                "0",
                "--stop-after-empty-failed-pages",
                "3",
            ]
        )

        rows, metadata = eastmoney.fetch_snapshot(args, AlwaysFailingOpener())

        self.assertEqual([], rows)
        self.assertEqual(300, metadata["requested_pages"])
        self.assertEqual(3, metadata["attempted_pages"])
        self.assertEqual(3, metadata["pages_failed"])
        self.assertTrue(metadata["stopped_early"])
        self.assertEqual(
            "consecutive_failed_pages_before_any_rows",
            metadata["stop_reason"],
        )
        self.assertTrue(metadata["partial_result"])

    def test_page_items_accepts_dict_diff_payload(self) -> None:
        data = {
            "data": {
                "diff": {
                    "0": {"f12": "000001"},
                    "1": {"f12": "600000"},
                    "metadata": "ignored",
                }
            }
        }

        rows = eastmoney.page_items(data)

        self.assertEqual(["000001", "600000"], [row["f12"] for row in rows])

    def test_page_items_accepts_list_diff_payload(self) -> None:
        data = {
            "data": {
                "diff": [
                    {"f12": "000001"},
                    "ignored",
                    {"f12": "600000"},
                ]
            }
        }

        rows = eastmoney.page_items(data)

        self.assertEqual(["000001", "600000"], [row["f12"] for row in rows])


class FakeOpener:
    def __call__(self, _url: str, _timeout: float) -> bytes:
        return json.dumps(payload()).encode("utf-8")


class FailingSecondPageOpener:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _url: str, _timeout: float) -> bytes:
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("remote disconnected")
        return json.dumps(payload()).encode("utf-8")


class FailOnceOpener:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _url: str, _timeout: float) -> bytes:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary disconnect")
        return json.dumps(payload()).encode("utf-8")


class EmptyOpener:
    def __call__(self, _url: str, _timeout: float) -> bytes:
        return json.dumps({"data": {"diff": []}}).encode("utf-8")


class AlwaysFailingOpener:
    def __call__(self, _url: str, _timeout: float) -> bytes:
        raise RuntimeError("remote disconnected")


def payload() -> dict[str, object]:
    return {
        "data": {
            "diff": [
                {
                    "f12": "000001",
                    "f14": "平安银行",
                    "f2": 12.34,
                    "f3": 1.2,
                    "f6": 123000000,
                    "f100": "银行",
                },
                {
                    "f12": "600000",
                    "f14": "浦发银行",
                    "f2": 9.87,
                    "f3": -0.5,
                    "f6": 89000000,
                    "f100": "银行",
                },
            ]
        }
    }


if __name__ == "__main__":
    unittest.main()
