from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_eastmoney_a_share_spot as eastmoney  # noqa: E402


class FetchEastmoneyAShareSpotTests(unittest.TestCase):
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
        self.assertEqual(1, metadata["successful_pages"])
        self.assertEqual(1, metadata["retry_attempts_per_page"])
        self.assertFalse(metadata["partial_result"])

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
        self.assertIn("partial_result=true", stderr.getvalue())
        self.assertTrue(data["partial_result"])
        self.assertEqual(1, len(data["failed_pages"]))
        self.assertIn(
            "use_partial_snapshot_only_with_partial_result_disclosure",
            data["allowed_failure_actions"],
        )
        self.assertEqual(2, len(rows))

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
