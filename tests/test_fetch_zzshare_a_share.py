from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import Future
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
TESTS = ROOT / "tests"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(TESTS))

import fetch_zzshare_a_share as fetcher  # noqa: E402
import lib.fetch.zzshare_a_share_checkpoint as checkpoint_helpers  # noqa: E402
import lib.fetch.zzshare_a_share_data as zzshare_data  # noqa: E402
from zzshare_fetch_fakes import FakeDataApi, restore_module, valid_daily  # noqa: E402


def checkpoint_cli_args(root: Path, checkpoint: Path) -> object:
    args = fetcher.build_parser().parse_args(
        [
            "--symbols",
            "000001",
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-29",
            "--output",
            str(root / "prices.csv"),
            "--metadata-output",
            str(root / "metadata.json"),
            "--request-interval-seconds",
            "0",
            "--checkpoint-dir",
            str(checkpoint),
            "--checkpoint-batch-size",
            "1",
            "--resume-from-checkpoint",
        ]
    )
    fetcher.validate_arguments(args)
    return args


class FetchZzshareAShareTests(unittest.TestCase):
    def test_guarded_fetch_symbol_preserves_failure_when_budget_exhausts(self) -> None:
        controller = types.SimpleNamespace(
            exhausted=True,
            exhaustion_reason="max_runtime_seconds_exceeded",
        )
        original_failure = {
            "symbol": "000001",
            "page": 3,
            "error": "provider payload invalid",
        }

        with patch.object(
            zzshare_data,
            "fetch_symbol",
            return_value=([], 2, False, original_failure),
        ):
            result = zzshare_data.guarded_fetch_symbol(
                types.SimpleNamespace(),
                types.SimpleNamespace(),
                "000001",
                controller,
            )

        failure = result[3]
        self.assertEqual("provider payload invalid", failure["error"])
        self.assertEqual("rate_limit_budget_exhausted", failure["error_code"])
        self.assertEqual(
            "max_runtime_seconds_exceeded",
            failure["rate_limit_exhaustion_reason"],
        )

    def test_fetch_symbol_task_preserves_failure_when_budget_exhausts(self) -> None:
        args = types.SimpleNamespace(
            timeout_seconds=10,
            http_url="https://example.test",
        )
        controller = types.SimpleNamespace(
            exhausted=True,
            exhaustion_reason="max_429_events_exceeded",
        )
        original_failure = {
            "symbol": "000001",
            "page": 2,
            "error": "provider parse failed",
        }

        with patch.object(
            zzshare_data,
            "fetch_symbol",
            return_value=([], 1, False, original_failure),
        ):
            result = zzshare_data.fetch_symbol_task(
                lambda **_kwargs: types.SimpleNamespace(),
                args,
                "000001",
                controller,
            )

        failure = result[3]
        self.assertEqual("provider parse failed", failure["error"])
        self.assertEqual("rate_limit_budget_exhausted", failure["error_code"])
        self.assertEqual(
            "max_429_events_exceeded",
            failure["rate_limit_exhaustion_reason"],
        )

    def test_fetch_symbol_task_wraps_exception_when_budget_exhausts(self) -> None:
        args = types.SimpleNamespace(
            timeout_seconds=10,
            http_url="https://example.test",
        )
        controller = types.SimpleNamespace(
            exhausted=True,
            exhaustion_reason="max_runtime_seconds_exceeded",
        )

        with patch.object(
            zzshare_data,
            "fetch_symbol",
            side_effect=RuntimeError("provider connection failed"),
        ):
            result = zzshare_data.fetch_symbol_task(
                lambda **_kwargs: types.SimpleNamespace(),
                args,
                "000001",
                controller,
            )

        failure = result[3]
        self.assertEqual("provider connection failed", failure["error"])
        self.assertEqual("rate_limit_budget_exhausted", failure["error_code"])
        self.assertEqual(
            "max_runtime_seconds_exceeded",
            failure["rate_limit_exhaustion_reason"],
        )

    def test_fail_on_fetch_error_help_keeps_base_gates_explicit(self) -> None:
        help_text = fetcher.build_parser().format_help()

        self.assertIn("Also fail on failed_symbols, empty_symbols", help_text)
        self.assertIn("possibly_truncated_symbols", help_text)
        self.assertIn("Invalid or tradestatus-missing rows", help_text)
        self.assertIn("Non-trading rows follow --non-trading-policy", help_text)

    def test_non_trading_policy_drop_filters_rows_with_audit_metadata(self) -> None:
        row = valid_daily().iloc[0].to_dict()
        non_trading = {**row, "trade_date": "20260521", "is_paused": 1}
        fake_api = FakeDataApi({"000001.SZ": pd.DataFrame([row, non_trading])})
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
                            "--non-trading-policy",
                            "drop",
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                frame = pd.read_csv(output, dtype={"symbol": str})
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertIn("OK:", stdout.getvalue())
        self.assertEqual("drop", saved["non_trading_policy"])
        self.assertEqual(1, saved["raw_non_trading_rows"])
        self.assertEqual(1, saved["dropped_non_trading_rows"])
        self.assertEqual(0, saved["retained_non_trading_rows"])
        self.assertEqual(1, saved["rows"])
        self.assertEqual(1, len(frame))

    def test_non_trading_policy_drop_does_not_hide_missing_tradestatus(self) -> None:
        row = valid_daily().iloc[0].to_dict()
        missing_tradestatus = {**row, "trade_date": "20260521", "is_paused": ""}
        fake_api = FakeDataApi({"000001.SZ": pd.DataFrame([row, missing_tradestatus])})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stderr = StringIO()
                with redirect_stderr(stderr):
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
                            "--non-trading-policy",
                            "drop",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual(1, saved["tradestatus_missing_rows"])
        self.assertEqual(1, saved["non_trading_rows"])
        self.assertEqual(0, saved["dropped_non_trading_rows"])
        self.assertIn("tradestatus_missing_rows=1", stderr.getvalue())

    def test_cli_checkpoint_resume_reuses_completed_symbol_parts(self) -> None:
        fake_api = FakeDataApi(
            {
                "000001.SZ": valid_daily(),
                "600000.SH": valid_daily(ts_code="600000.SH"),
            }
        )
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                checkpoint = root / "checkpoint"
                output = root / "prices.csv"
                metadata = root / "metadata.json"
                stdout = StringIO()
                with redirect_stdout(stdout):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
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
                            "--checkpoint-dir",
                            str(checkpoint),
                            "--checkpoint-batch-size",
                            "1",
                        ]
                    )
                first = json.loads(metadata.read_text(encoding="utf-8"))

                resume_output = root / "prices-resume.csv"
                resume_metadata = root / "metadata-resume.json"
                with redirect_stdout(stdout):
                    code_resume = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(resume_output),
                            "--metadata-output",
                            str(resume_metadata),
                            "--request-interval-seconds",
                            "0",
                            "--checkpoint-dir",
                            str(checkpoint),
                            "--checkpoint-batch-size",
                            "1",
                            "--resume-from-checkpoint",
                        ]
                    )
                resumed = json.loads(resume_metadata.read_text(encoding="utf-8"))
                resumed_frame = pd.read_csv(resume_output, dtype={"symbol": str})
                checkpoint_manifest_exists = (checkpoint / "manifest.json").is_file()
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertEqual(0, code_resume)
        self.assertTrue(first["checkpoint_enabled"])
        self.assertEqual(2, first["checkpoint_parts_available"])
        self.assertTrue(checkpoint_manifest_exists)
        self.assertEqual(2, resumed["checkpoint_symbols_skipped"])
        self.assertEqual(0, resumed["checkpoint_requests_executed"])
        self.assertEqual(2, len(resumed_frame))

    def test_checkpoint_empty_symbol_is_not_reused_as_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = types.SimpleNamespace(
                checkpoint_dir=tmpdir,
                checkpoint_batch_size=1,
                resume_from_checkpoint=False,
                start_date="2026-05-01",
                end_date="2026-05-29",
                fields="all",
                adjust="",
                limit=1000,
                max_pages=10,
                http_url="https://api.zizizaizai.com",
                timeout_seconds=10.0,
                request_interval_seconds=0.0,
                max_concurrent_symbol_requests=1,
                max_rate_limit_sleep_seconds=120.0,
                max_429_events=3,
                max_runtime_seconds=900.0,
                non_trading_policy="drop",
                drop_invalid_rows=False,
            )
            checkpoint = checkpoint_helpers.prepare_checkpoint(args)
            batch = checkpoint_helpers.empty_checkpoint_batch()
            checkpoint_helpers.append_checkpoint_record(
                checkpoint,
                batch,
                "000001",
                [],
                {"symbol": "000001", "rows": 0},
                None,
                False,
            )
            checkpoint_helpers.flush_checkpoint_batch(
                checkpoint,
                batch,
                pd,
                ["symbol", "date", "close"],
            )

            record = checkpoint["manifest"]["symbols"]["000001"]
            self.assertEqual("empty", record["status"])
            self.assertIsNone(
                checkpoint_helpers.completed_checkpoint_record(checkpoint, "000001")
            )

    def test_checkpoint_resume_rejects_changed_fetch_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = dict(
                checkpoint_dir=tmpdir,
                checkpoint_batch_size=1,
                start_date="2026-05-01",
                end_date="2026-05-29",
                fields="all",
                adjust="",
                limit=1000,
                max_pages=10,
                http_url="https://api.zizizaizai.com",
                timeout_seconds=10.0,
                request_interval_seconds=0.0,
                max_concurrent_symbol_requests=1,
                max_rate_limit_sleep_seconds=120.0,
                max_429_events=3,
                max_runtime_seconds=900.0,
                non_trading_policy="drop",
                drop_invalid_rows=False,
            )
            first_args = types.SimpleNamespace(**base, resume_from_checkpoint=False)
            checkpoint = checkpoint_helpers.prepare_checkpoint(first_args)
            batch = checkpoint_helpers.empty_checkpoint_batch()
            checkpoint_helpers.append_checkpoint_record(
                checkpoint,
                batch,
                "000001",
                [{"symbol": "000001", "date": "2026-05-29", "close": 10.0}],
                {"symbol": "000001", "rows": 1},
                None,
                False,
            )
            checkpoint_helpers.flush_checkpoint_batch(
                checkpoint,
                batch,
                pd,
                ["symbol", "date", "close"],
            )

            changed_args = types.SimpleNamespace(
                **{**base, "end_date": "2026-06-01"},
                resume_from_checkpoint=True,
            )
            with self.assertRaisesRegex(ValueError, "checkpoint execution contract"):
                checkpoint_helpers.prepare_checkpoint(changed_args)

    def test_checkpoint_contract_does_not_persist_sensitive_http_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = types.SimpleNamespace(
                checkpoint_dir=tmpdir,
                checkpoint_batch_size=1,
                resume_from_checkpoint=False,
                start_date="2026-05-01",
                end_date="2026-05-29",
                fields="all",
                adjust="",
                limit=1000,
                max_pages=10,
                http_url=(
                    "https://user:placeholder-password@example.test/private-path"
                    "?token=placeholder-token"
                ),
                timeout_seconds=10.0,
                request_interval_seconds=0.0,
                max_concurrent_symbol_requests=1,
                max_rate_limit_sleep_seconds=120.0,
                max_429_events=3,
                max_runtime_seconds=900.0,
                non_trading_policy="drop",
                drop_invalid_rows=False,
            )

            checkpoint = checkpoint_helpers.prepare_checkpoint(args)
            serialized = json.dumps(checkpoint["manifest"], sort_keys=True)

        self.assertNotIn("placeholder-password", serialized)
        self.assertNotIn("placeholder-token", serialized)
        self.assertNotIn("private-path", serialized)
        contract = checkpoint["manifest"]["execution_contract"]
        self.assertEqual("example.test", contract["http_url_host"])
        self.assertRegex(contract["http_url_sha256"], r"^[0-9a-f]{64}$")

    def test_checkpoint_resume_ignores_failed_partial_parts(self) -> None:
        old_row = valid_daily().iloc[0].to_dict()
        old_row["close"] = 10.1
        new_row = valid_daily().iloc[0].to_dict()
        new_row["close"] = 20.2
        other_row = valid_daily(ts_code="600000.SH").iloc[0].to_dict()
        failed_once = {"000001.SZ": False}

        def first_daily(**kwargs):
            ts_code = str(kwargs["ts_code"])
            offset = int(kwargs["offset"])
            if ts_code == "000001.SZ" and offset > 0:
                failed_once[ts_code] = True
                raise RuntimeError("page two failed")
            if ts_code == "000001.SZ":
                return pd.DataFrame([old_row])
            if offset > 0:
                return pd.DataFrame()
            return pd.DataFrame([other_row])

        def resume_daily(**kwargs):
            if int(kwargs["offset"]) > 0:
                return pd.DataFrame()
            return pd.DataFrame([new_row])

        first_api = types.SimpleNamespace(
            factory=lambda **_kwargs: types.SimpleNamespace(daily=first_daily)
        )
        resume_api = types.SimpleNamespace(
            factory=lambda **_kwargs: types.SimpleNamespace(daily=resume_daily)
        )
        old_module = sys.modules.get("zzshare.client")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                checkpoint = root / "checkpoint"
                stdout = StringIO()
                sys.modules["zzshare.client"] = types.SimpleNamespace(
                    DataApi=first_api.factory
                )
                with redirect_stdout(stdout):
                    first_code = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(root / "prices.csv"),
                            "--metadata-output",
                            str(root / "metadata.json"),
                            "--request-interval-seconds",
                            "0",
                            "--limit",
                            "1",
                            "--max-pages",
                            "2",
                            "--checkpoint-dir",
                            str(checkpoint),
                            "--checkpoint-batch-size",
                            "1",
                        ]
                    )

                sys.modules["zzshare.client"] = types.SimpleNamespace(
                    DataApi=resume_api.factory
                )
                resume_output = root / "prices-resume.csv"
                resume_metadata = root / "metadata-resume.json"
                with redirect_stdout(stdout):
                    resume_code = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
                            "--start-date",
                            "2026-05-01",
                            "--end-date",
                            "2026-05-29",
                            "--output",
                            str(resume_output),
                            "--metadata-output",
                            str(resume_metadata),
                            "--request-interval-seconds",
                            "0",
                            "--limit",
                            "1",
                            "--max-pages",
                            "2",
                            "--checkpoint-dir",
                            str(checkpoint),
                            "--checkpoint-batch-size",
                            "1",
                            "--resume-from-checkpoint",
                        ]
                    )
                resumed = json.loads(resume_metadata.read_text(encoding="utf-8"))
                frame = pd.read_csv(resume_output, dtype={"symbol": str})
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, first_code)
        self.assertTrue(failed_once["000001.SZ"])
        self.assertEqual(0, resume_code)
        self.assertEqual(1, resumed["checkpoint_symbols_skipped"])
        self.assertEqual(["000001", "600000"], sorted(frame["symbol"].tolist()))
        close = frame[frame["symbol"] == "000001"]["close"].iloc[0]
        self.assertEqual(20.2, float(close))

    def test_checkpoint_frame_concatenates_unique_parts_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir)
            pd.DataFrame(
                [
                    {"symbol": "000001", "close": 10.1},
                    {"symbol": "000002", "close": 10.2},
                ]
            ).to_csv(checkpoint_dir / "prices_part_00001.csv", index=False)
            pd.DataFrame(
                [
                    {"symbol": "600000", "close": 20.1},
                    {"symbol": "600001", "close": 20.2},
                ]
            ).to_csv(checkpoint_dir / "prices_part_00002.csv", index=False)
            checkpoint = {
                "dir": checkpoint_dir,
                "manifest": {
                    "parts": [
                        "prices_part_00001.csv",
                        "prices_part_00002.csv",
                    ],
                    "symbols": {
                        "000001": {"status": "completed", "part": "prices_part_00001.csv"},
                        "000002": {"status": "completed", "part": "prices_part_00001.csv"},
                        "600000": {"status": "completed", "part": "prices_part_00002.csv"},
                        "600001": {"status": "completed", "part": "prices_part_00002.csv"},
                    },
                },
            }

            frame = checkpoint_helpers.checkpoint_frame(
                checkpoint,
                pd,
                ["symbol", "close"],
            )

        self.assertEqual(
            ["000001", "000002", "600000", "600001"],
            frame["symbol"].astype(str).tolist(),
        )

    def test_checkpoint_resume_filters_to_requested_symbol_subset(self) -> None:
        fake_api = FakeDataApi(
            {
                "000001.SZ": valid_daily(),
                "600000.SH": valid_daily(ts_code="600000.SH"),
            }
        )
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                checkpoint = root / "checkpoint"
                fetcher.main(
                    [
                        "--symbols",
                        "000001,600000",
                        "--start-date",
                        "2026-05-01",
                        "--end-date",
                        "2026-05-29",
                        "--output",
                        str(root / "prices.csv"),
                        "--metadata-output",
                        str(root / "metadata.json"),
                        "--request-interval-seconds",
                        "0",
                        "--checkpoint-dir",
                        str(checkpoint),
                        "--checkpoint-batch-size",
                        "1",
                    ]
                )

                subset_output = root / "prices-subset.csv"
                subset_metadata = root / "metadata-subset.json"
                fetcher.main(
                    [
                        "--symbols",
                        "600000",
                        "--start-date",
                        "2026-05-01",
                        "--end-date",
                        "2026-05-29",
                        "--output",
                        str(subset_output),
                        "--metadata-output",
                        str(subset_metadata),
                        "--request-interval-seconds",
                        "0",
                        "--checkpoint-dir",
                        str(checkpoint),
                        "--checkpoint-batch-size",
                        "1",
                        "--resume-from-checkpoint",
                    ]
                )
                subset_frame = pd.read_csv(subset_output, dtype={"symbol": str})
                subset_saved = json.loads(subset_metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(["600000"], subset_frame["symbol"].astype(str).unique().tolist())
        self.assertEqual(1, subset_saved["symbol_count"])
        self.assertEqual(["600000"], [item["symbol"] for item in subset_saved["symbols"]])

    def test_checkpoint_resume_refetches_completed_record_missing_from_part(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": valid_daily()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                checkpoint = root / "checkpoint"
                checkpoint.mkdir()
                resume_args = checkpoint_cli_args(root, checkpoint)
                contract = checkpoint_helpers.checkpoint_execution_contract(resume_args)
                part_path = checkpoint / "prices_part_00001.csv"
                pd.DataFrame([{"symbol": "600000", "close": 20.1}]).to_csv(
                    part_path,
                    index=False,
                )
                (checkpoint / "manifest.json").write_text(
                    json.dumps(
                        {
                            "version": checkpoint_helpers.CHECKPOINT_SCHEMA_VERSION,
                            "execution_contract": contract,
                            "execution_contract_sha256": (
                                checkpoint_helpers.checkpoint_contract_digest(contract)
                            ),
                            "parts": ["prices_part_00001.csv"],
                            "part_artifacts": {
                                "prices_part_00001.csv": (
                                    checkpoint_helpers.checkpoint_part_fingerprint(
                                        part_path
                                    )
                                )
                            },
                            "symbols": {
                                "000001": {
                                    "status": "completed",
                                    "rows": 1,
                                    "part": "prices_part_00001.csv",
                                    "metadata": {
                                        "symbol": "000001",
                                        "rows": 1,
                                        "date_min": "2026-05-20",
                                        "date_max": "2026-05-20",
                                    },
                                    "failure": {},
                                    "possibly_truncated": False,
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                output = root / "prices.csv"
                metadata = root / "metadata.json"

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
                        "--checkpoint-dir",
                        str(checkpoint),
                        "--checkpoint-batch-size",
                        "1",
                        "--resume-from-checkpoint",
                        "--fail-on-fetch-error",
                    ]
                )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                frame = pd.read_csv(output, dtype={"symbol": str})
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertEqual(["000001"], frame["symbol"].astype(str).unique().tolist())
        self.assertEqual(0, saved["checkpoint_symbols_skipped"])
        self.assertEqual(1, saved["checkpoint_requests_executed"])
        self.assertEqual(1, saved["checkpoint_integrity_issue_count"])
        self.assertEqual(
            "completed_record_symbol_missing_from_part",
            saved["checkpoint_integrity_issues"][0]["issue"],
        )

    def test_checkpoint_resume_refetches_completed_record_row_count_mismatch(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": valid_daily()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                checkpoint = root / "checkpoint"
                checkpoint.mkdir()
                resume_args = checkpoint_cli_args(root, checkpoint)
                contract = checkpoint_helpers.checkpoint_execution_contract(resume_args)
                part_path = checkpoint / "prices_part_00001.csv"
                pd.DataFrame([{"symbol": "000001", "close": 20.1}]).to_csv(
                    part_path,
                    index=False,
                )
                (checkpoint / "manifest.json").write_text(
                    json.dumps(
                        {
                            "version": checkpoint_helpers.CHECKPOINT_SCHEMA_VERSION,
                            "execution_contract": contract,
                            "execution_contract_sha256": (
                                checkpoint_helpers.checkpoint_contract_digest(contract)
                            ),
                            "parts": ["prices_part_00001.csv"],
                            "part_artifacts": {
                                "prices_part_00001.csv": (
                                    checkpoint_helpers.checkpoint_part_fingerprint(
                                        part_path
                                    )
                                )
                            },
                            "symbols": {
                                "000001": {
                                    "status": "completed",
                                    "rows": 2,
                                    "part": "prices_part_00001.csv",
                                    "metadata": {"symbol": "000001", "rows": 2},
                                    "failure": {},
                                    "possibly_truncated": False,
                                }
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                metadata = root / "metadata.json"

                code = fetcher.main(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-01",
                        "--end-date",
                        "2026-05-29",
                        "--output",
                        str(root / "prices.csv"),
                        "--metadata-output",
                        str(metadata),
                        "--request-interval-seconds",
                        "0",
                        "--checkpoint-dir",
                        str(checkpoint),
                        "--checkpoint-batch-size",
                        "1",
                        "--resume-from-checkpoint",
                    ]
                )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertEqual(0, saved["checkpoint_symbols_skipped"])
        self.assertEqual(1, saved["checkpoint_requests_executed"])
        self.assertEqual(1, saved["checkpoint_integrity_issue_count"])
        self.assertEqual(
            "completed_record_symbol_row_count_mismatch",
            saved["checkpoint_integrity_issues"][0]["issue"],
        )

    def test_checkpoint_reset_preserves_unrelated_files(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": valid_daily()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                checkpoint = root / "checkpoint"
                checkpoint.mkdir()
                unrelated = checkpoint / "notes.txt"
                unrelated.write_text("keep\n", encoding="utf-8")
                old_part = checkpoint / "prices_part_00001.csv"
                old_part.write_text("symbol\n600000\n", encoding="utf-8")
                old_temporary_part = checkpoint / "prices_part_00002.csv.tmp"
                old_temporary_part.write_text("symbol\n600001\n", encoding="utf-8")
                (checkpoint / "manifest.json").write_text('{"symbols":{}}\n', encoding="utf-8")

                code = fetcher.main(
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-01",
                        "--end-date",
                        "2026-05-29",
                        "--output",
                        str(root / "prices.csv"),
                        "--metadata-output",
                        str(root / "metadata.json"),
                        "--request-interval-seconds",
                        "0",
                        "--checkpoint-dir",
                        str(checkpoint),
                        "--checkpoint-batch-size",
                        "1",
                    ]
                )
                unrelated_exists = unrelated.is_file()
                unrelated_text = unrelated.read_text(encoding="utf-8")
                old_temporary_part_exists = old_temporary_part.exists()
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertTrue(unrelated_exists)
        self.assertEqual("keep\n", unrelated_text)
        self.assertFalse(old_temporary_part_exists)

    def test_zzshare_date_accepts_dash_or_compact(self) -> None:
        self.assertEqual("20260529", fetcher.zzshare_date("2026-05-29"))
        self.assertEqual("20260529", fetcher.zzshare_date("20260529"))
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            fetcher.zzshare_date("2026/05/29")

    def test_ts_code_maps_six_digit_symbols_to_exchange_suffix(self) -> None:
        self.assertEqual("000001.SZ", fetcher.ts_code("000001"))
        self.assertEqual("300750.SZ", fetcher.ts_code("300750"))
        self.assertEqual("600000.SH", fetcher.ts_code("600000"))
        self.assertEqual("688001.SH", fetcher.ts_code("688001"))
        self.assertEqual("900901.SH", fetcher.ts_code("900901"))
        self.assertEqual("430047.BJ", fetcher.ts_code("430047"))
        self.assertEqual("835185.BJ", fetcher.ts_code("835185"))
        self.assertEqual("920002.BJ", fetcher.ts_code("920002"))

    def test_parse_symbols_accepts_bj_prefixes_and_suffixes_for_zzshare(self) -> None:
        self.assertEqual(
            ["430047", "835185"], fetcher.parse_symbols("bj.430047,835185.BJ")
        )

    def test_collect_rows_maps_zzshare_fields_and_preserves_amount(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20260520",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.9,
                    "close": 10.1,
                    "vol": 1000,
                    "amount": 10100,
                    "turnover_rate": 0.5,
                    "is_paused": 0,
                    "is_st": 0,
                    "name": "平安银行",
                }
            ]
        )

        rows = fetcher.collect_rows(raw, "000001")

        self.assertEqual("000001", rows[0]["symbol"])
        self.assertEqual("A-share", rows[0]["market"])
        self.assertEqual("2026-05-20", rows[0]["date"])
        self.assertEqual(1000, rows[0]["volume"])
        self.assertEqual(10100, rows[0]["amount"])
        self.assertEqual(0.5, rows[0]["turn"])
        self.assertEqual("zzshare", rows[0]["source"])

    def test_cli_writes_prices_and_metadata_with_fake_zzshare(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": valid_daily()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with patch.dict("os.environ", {"ZZSHARE_TOKEN": "test-token"}):
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
                                "--http-url",
                                "https://example.test",
                                "--timeout-seconds",
                                "7",
                                "--request-interval-seconds",
                                "0",
                                "--fail-on-fetch-error",
                            ]
                        )
                    saved = json.loads(metadata.read_text(encoding="utf-8"))
                    frame = pd.read_csv(output, dtype={"symbol": str})
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertIn("OK: source=zzshare rows=1", stdout.getvalue())
        self.assertIn("source_scope=zzshare_history_fetch", stdout.getvalue())
        self.assertIn("limit=1000", stdout.getvalue())
        self.assertIn("max_pages=10", stdout.getvalue())
        self.assertIn("token_configured=true", stdout.getvalue())
        self.assertEqual(1, saved["rows"])
        self.assertEqual(1, saved["symbol_count"])
        self.assertEqual([], saved["failed_symbols"])
        self.assertEqual([], saved["empty_symbols"])
        self.assertEqual("external_fetch", saved["source_type"])
        self.assertEqual("zzshare_history_fetch", saved["source_scope"])
        self.assertTrue(saved["real_market_data"])
        self.assertFalse(saved["partial_result"])
        self.assertTrue(saved["token_configured"])
        self.assertIn(
            "quota and stability require external verification",
            saved["data_source_note"],
        )
        self.assertNotIn("free SDK endpoint", saved["data_source_note"])
        self.assertEqual("https://example.test", saved["http_url"])
        self.assertEqual(7.0, saved["timeout_seconds"])
        self.assertEqual(0.0, saved["request_interval_seconds"])
        self.assertEqual(1, saved["max_concurrent_symbol_requests"])
        self.assertEqual("000001.SZ", saved["symbols"][0]["ts_code"])
        self.assertEqual("test-token", fake_api.instances[0].token)
        self.assertEqual(7.0, fake_api.instances[0].timeout)
        self.assertEqual("https://example.test", fake_api.instances[0].http_url)
        self.assertEqual("000001", frame["symbol"].iloc[0])

    def test_help_uses_environment_token_not_cli_token_argument(self) -> None:
        help_text = fetcher.build_parser().format_help()
        normalized = " ".join(help_text.split())

        self.assertNotIn("--token", help_text)
        self.assertIn("ZZSHARE_TOKEN environment variable", normalized)

    def test_collect_rows_leaves_missing_name_blank_for_symbol_fallback(self) -> None:
        rows = fetcher.collect_rows(valid_daily().drop(columns=["name"]), "000001")

        self.assertEqual("", rows[0]["name"])

    def test_cli_partial_default_discloses_empty_symbol(self) -> None:
        fake_api = FakeDataApi(
            {"000001.SZ": valid_daily(), "600000.SH": pd.DataFrame()}
        )
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
                            "000001,600000",
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
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                output_exists = output.exists()
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(0, code)
        self.assertTrue(output_exists)
        self.assertTrue(stdout.getvalue().startswith("PARTIAL:"))
        self.assertEqual(["600000"], saved["empty_symbols"])
        self.assertTrue(saved["partial_result"])
        self.assertTrue(saved["output_written"])

    def test_cli_strict_error_removes_stale_output_and_keeps_metadata(self) -> None:
        fake_api = FakeDataApi({"000001.SZ": pd.DataFrame()})
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                output.write_text(
                    "symbol,date,close\n000001,2026-01-01,1\n", encoding="utf-8"
                )
                metadata.write_text('{"stale": true}\n', encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
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
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertFalse(saved["output_written"])
        self.assertTrue(saved["metadata_output_written"])
        self.assertTrue(saved["partial_result"])
        self.assertEqual(["000001"], saved["empty_symbols"])
        self.assertIn("ERROR_SUMMARY:", stdout.getvalue())
        self.assertIn("empty_symbols=1", stderr.getvalue())

    def test_cli_strict_invalid_rows_returns_error_with_metadata(self) -> None:
        fake_api = FakeDataApi(
            {
                "000001.SZ": pd.DataFrame(
                    [
                        {
                            **valid_daily().iloc[0].to_dict(),
                            "vol": "",
                            "amount": "",
                            "turnover_rate": "",
                            "is_paused": 0,
                            "is_st": 0,
                        }
                    ]
                )
            }
        )
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir) / "prices.csv"
                metadata = Path(tmpdir) / "metadata.json"
                stdout = StringIO()
                stderr = StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
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
                            "--fail-on-fetch-error",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
        finally:
            restore_module("zzshare.client", old_module)

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertEqual(1, saved["invalid_rows"])
        self.assertEqual(0, saved["dropped_invalid_rows"])
        self.assertIn("invalid_rows=1", stderr.getvalue())

    def test_fetch_prices_sleeps_between_symbol_requests(self) -> None:
        fake_api = FakeDataApi(
            {
                "000001.SZ": valid_daily(),
                "600000.SH": valid_daily(ts_code="600000.SH"),
            }
        )
        old_module = sys.modules.get("zzshare.client")
        old_sleep = zzshare_data.time.sleep
        sleep_calls: list[float] = []
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        zzshare_data.time.sleep = sleep_calls.append  # type: ignore[assignment]
        try:
            args = types.SimpleNamespace(
                symbols="000001,600000",
                start_date="2026-05-01",
                end_date="2026-05-29",
                output="",
                metadata_output="",
                token="",
                http_url="https://example.test",
                timeout_seconds=7,
                request_interval_seconds=1.25,
                fields="all",
                adjust="",
                limit=1000,
                max_pages=1,
            )

            frame, metadata = fetcher.fetch_prices(args)
        finally:
            restore_module("zzshare.client", old_module)
            zzshare_data.time.sleep = old_sleep  # type: ignore[assignment]

        self.assertEqual([1.25], sleep_calls)
        self.assertEqual(2, len(frame))
        self.assertEqual(2, metadata["symbol_count"])

    def test_fetch_prices_parallel_uses_requested_concurrency_and_keeps_symbol_order(
        self,
    ) -> None:
        fake_api = FakeDataApi({})
        old_module = sys.modules.get("zzshare.client")
        old_fetch_symbol_task = zzshare_data.fetch_symbol_task
        active = 0
        max_active = 0
        lock = threading.Lock()

        def fake_fetch_symbol_task(_factory, _args, symbol: str, _controller):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return (
                [
                    {
                        "symbol": symbol,
                        "name": symbol,
                        "market": "A-share",
                        "date": "2026-05-20",
                        "open": 10.0,
                        "high": 10.2,
                        "low": 9.9,
                        "close": 10.1,
                        "preclose": "",
                        "pctChg": "",
                        "volume": 1000,
                        "amount": 10100,
                        "turn": 0.5,
                        "tradestatus": 1,
                        "isST": 0,
                        "source": "zzshare",
                        "source_type": "external_fetch",
                        "source_scope": "zzshare_history_fetch",
                        "real_market_data": True,
                        "metadata_source": "external_fetch",
                        "source_claim_boundary": (
                            "zzshare_external_api_not_broker_order_or_long_term_stability_proof"
                        ),
                        "data_source_note": (
                            "zzshare SDK endpoint; quota and stability require external verification"
                        ),
                    }
                ],
                1,
                False,
                None,
            )

        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        zzshare_data.fetch_symbol_task = fake_fetch_symbol_task
        try:
            args = types.SimpleNamespace(
                symbols="000001,000002,600000",
                start_date="2026-05-01",
                end_date="2026-05-29",
                output="",
                metadata_output="",
                token="",
                http_url="https://example.test",
                timeout_seconds=7,
                request_interval_seconds=0,
                fields="all",
                adjust="",
                limit=1000,
                max_pages=1,
                max_concurrent_symbol_requests=2,
                checkpoint_dir="",
                checkpoint_batch_size=0,
                resume_from_checkpoint=False,
                progress_interval=0,
            )

            frame, metadata = fetcher.fetch_prices(args)
        finally:
            restore_module("zzshare.client", old_module)
            zzshare_data.fetch_symbol_task = old_fetch_symbol_task

        self.assertGreaterEqual(max_active, 2)
        self.assertEqual(["000001", "000002", "600000"], frame["symbol"].tolist())
        self.assertEqual(2, metadata["max_concurrent_symbol_requests"])
        self.assertEqual(3, metadata["symbol_count"])

    def test_unprocessed_rate_limited_symbol_is_not_counted_as_empty(self) -> None:
        state = zzshare_data.FetchState()

        zzshare_data.apply_fetch_result(
            "600000",
            (
                [],
                0,
                False,
                {
                    "symbol": "600000",
                    "error_code": "rate_limit_budget_exhausted_unprocessed",
                    "error": "max_runtime_seconds_exceeded",
                },
            ),
            state,
            None,
        )

        self.assertEqual([], state.symbols_meta)
        self.assertEqual([], zzshare_data.empty_symbols(state.symbols_meta))
        self.assertEqual([], state.failed)
        self.assertEqual(["600000"], state.unprocessed)

    def test_rate_limited_parallel_queue_keeps_completed_future_result(self) -> None:
        result = ([{"symbol": "000001"}], 1, False, None)
        future: Future[object] = Future()
        future.set_result(result)
        queue = zzshare_data.ParallelQueue(inflight={future: 0})
        controller = types.SimpleNamespace(
            exhausted=True,
            exhaustion_reason="max_runtime_seconds_exceeded",
        )

        zzshare_data.mark_rate_limited_inflight(
            ["000001"], controller, queue
        )

        self.assertEqual({}, queue.inflight)
        self.assertEqual(("fetched", result), queue.ready[0])

    def test_parallel_worker_keeps_success_when_peer_budget_exhausts(self) -> None:
        result = ([{"symbol": "000001"}], 1, False, None)
        args = types.SimpleNamespace(timeout_seconds=1, http_url="https://example.test")
        controller = types.SimpleNamespace(
            exhausted=True,
            exhaustion_reason="max_429_events_exceeded",
        )

        with patch.object(zzshare_data, "fetch_symbol", return_value=result):
            actual = zzshare_data.fetch_symbol_task(
                lambda **_kwargs: types.SimpleNamespace(),
                args,
                "000001",
                controller,
            )

        self.assertEqual(result, actual)

    def test_parallel_fetch_stops_waiting_at_total_runtime_budget(self) -> None:
        fake_api = FakeDataApi({})
        old_module = sys.modules.get("zzshare.client")
        old_fetch_symbol_task = zzshare_data.fetch_symbol_task
        release = threading.Event()

        def blocked_fetch_symbol_task(_factory, _args, _symbol, _controller):
            release.wait(timeout=1.0)
            return [], 0, False, None

        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=fake_api.factory)
        zzshare_data.fetch_symbol_task = blocked_fetch_symbol_task
        try:
            args = types.SimpleNamespace(
                symbols="000001,600000",
                start_date="2026-05-01",
                end_date="2026-05-29",
                http_url="https://example.test",
                timeout_seconds=7,
                request_interval_seconds=0,
                fields="all",
                adjust="",
                limit=1000,
                max_pages=1,
                max_concurrent_symbol_requests=2,
                max_rate_limit_sleep_seconds=120,
                max_429_events=3,
                max_runtime_seconds=0.02,
                checkpoint_dir="",
                checkpoint_batch_size=0,
                resume_from_checkpoint=False,
                progress_interval=0,
            )
            started = time.monotonic()

            frame, metadata = fetcher.fetch_prices(args)
            elapsed = time.monotonic() - started
        finally:
            release.set()
            restore_module("zzshare.client", old_module)
            zzshare_data.fetch_symbol_task = old_fetch_symbol_task

        self.assertLess(elapsed, 0.5)
        self.assertTrue(frame.empty)
        self.assertTrue(metadata["rate_limit_budget_exhausted"])
        self.assertEqual("max_runtime_seconds_exceeded", metadata["rate_limit_exhaustion_reason"])
        self.assertEqual(["000001", "600000"], metadata["unprocessed_symbols"])
        self.assertEqual([], metadata["empty_symbols"])


if __name__ == "__main__":
    unittest.main()
