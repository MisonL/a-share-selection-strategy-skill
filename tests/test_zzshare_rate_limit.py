from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_zzshare_a_share as fetcher  # noqa: E402
from lib.fetch.zzshare_a_share_data import (  # noqa: E402
    OUTPUT_COLUMNS,
    FetchState,
    apply_fetch_result,
)
from lib.fetch.zzshare_a_share_quality import apply_quality_policy  # noqa: E402
from lib.fetch.zzshare_rate_limit import RateLimitController  # noqa: E402


class FakeResponse:
    def __init__(self, status_code: int, retry_after: str = "") -> None:
        self.status_code = status_code
        self.headers = {"Retry-After": retry_after} if retry_after else {}
        self.text = "rate limited" if status_code == 429 else "ok"


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class RateLimitedDataApi:
    def __init__(self, token: str = "", timeout: float = 10, http_url: str = ""):
        self.token = token
        self.timeout = timeout
        self.http_url = http_url
        self.headers = {}

    def daily(self, **kwargs):
        response = self._request_with_retry(
            f"{self.http_url}/v3/market/kline/day/{kwargs['ts_code']}",
            params=kwargs,
        )
        if response.status_code == 429:
            return pd.DataFrame()
        raise AssertionError("test expected only rate-limit responses")


class ZzshareRateLimitTests(unittest.TestCase):
    def test_unprocessed_symbol_is_not_counted_as_failed(self) -> None:
        state = FetchState()

        apply_fetch_result(
            "000001",
            (
                [],
                0,
                False,
                {
                    "symbol": "000001",
                    "error": "max runtime exceeded",
                    "error_code": "rate_limit_budget_exhausted_unprocessed",
                },
            ),
            state,
            None,
        )

        self.assertEqual([], state.failed)
        self.assertEqual(["000001"], state.unprocessed)
        self.assertEqual([], state.symbols_meta)

    def test_quality_policy_excludes_failed_symbol_from_empty(self) -> None:
        frame = pd.DataFrame(columns=OUTPUT_COLUMNS)
        metadata = {
            "requested_symbols": ["000001"],
            "failed_symbols": [
                {
                    "symbol": "000001",
                    "error": "rate limited",
                    "error_code": "rate_limit_budget_exhausted",
                }
            ],
            "empty_symbols": ["000001"],
            "possibly_truncated_symbols": [],
            "unprocessed_symbols": [],
            "symbols": [{"symbol": "000001", "rows": 0}],
            "partial_result": True,
            "rate_limit_budget_exhausted": True,
        }

        _frame, updated = apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=False,
            non_trading_policy="fail",
        )

        self.assertEqual([], updated["empty_symbols"])
        self.assertEqual("000001", updated["failed_symbols"][0]["symbol"])

    def test_quality_policy_keeps_unprocessed_result_partial(self) -> None:
        frame = pd.DataFrame(columns=OUTPUT_COLUMNS)
        metadata = {
            "requested_symbols": ["000001"],
            "failed_symbols": [],
            "empty_symbols": [],
            "possibly_truncated_symbols": [],
            "unprocessed_symbols": ["000001"],
            "symbols": [],
            "partial_result": True,
            "rate_limit_budget_exhausted": True,
        }

        _frame, updated = apply_quality_policy(
            frame,
            metadata,
            drop_invalid_rows=False,
            non_trading_policy="fail",
        )

        self.assertTrue(updated["partial_result"])
        self.assertEqual([], updated["empty_symbols"])

    def test_controller_rejects_requests_after_budget_exhaustion(self) -> None:
        calls = []
        args = types.SimpleNamespace(
            max_rate_limit_sleep_seconds=20,
            max_429_events=3,
            max_runtime_seconds=30,
        )
        controller = RateLimitController(
            args,
            request_get=lambda *args, **kwargs: calls.append((args, kwargs))
            or FakeResponse(200),
        )
        controller.mark_exhausted("max_429_events_exceeded")

        response = controller.request(
            types.SimpleNamespace(headers={}, timeout=1),
            "https://example.test",
        )

        self.assertEqual(429, response.status_code)
        self.assertEqual([], calls)
        self.assertEqual(0, controller.events)

    def test_late_429_after_peer_exhaustion_does_not_mutate_metrics(self) -> None:
        clock = FakeClock()
        holder = {}
        calls = []

        def request_get(*_args, **_kwargs):
            calls.append(True)
            holder["controller"].mark_exhausted("peer_budget_exhausted")
            return FakeResponse(429, "4")

        args = types.SimpleNamespace(
            max_rate_limit_sleep_seconds=20,
            max_429_events=3,
            max_runtime_seconds=30,
        )
        controller = RateLimitController(
            args,
            request_get=request_get,
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )
        holder["controller"] = controller

        response = controller.request(
            types.SimpleNamespace(headers={}, timeout=1),
            "https://example.test",
        )

        self.assertEqual(429, response.status_code)
        self.assertEqual([True], calls)
        self.assertEqual(0, controller.events)
        self.assertEqual([], clock.sleeps)

    def test_remaining_runtime_exhausts_controller_at_deadline(self) -> None:
        clock = FakeClock()
        args = types.SimpleNamespace(
            max_rate_limit_sleep_seconds=20,
            max_429_events=3,
            max_runtime_seconds=30,
        )
        controller = RateLimitController(
            args,
            request_get=lambda *_args, **_kwargs: FakeResponse(200),
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )

        self.assertEqual(30.0, controller.remaining_runtime_seconds())
        clock.value = 31.0
        self.assertEqual(0.0, controller.remaining_runtime_seconds())
        self.assertTrue(controller.exhausted)
        self.assertEqual("max_runtime_seconds_exceeded", controller.exhaustion_reason)

    def test_controller_honors_retry_after_and_stops_at_event_budget(self) -> None:
        responses = [FakeResponse(429, "4"), FakeResponse(429, "5")]
        clock = FakeClock()
        args = types.SimpleNamespace(
            max_rate_limit_sleep_seconds=20,
            max_429_events=1,
            max_runtime_seconds=30,
        )
        controller = RateLimitController(
            args,
            request_get=lambda *args, **kwargs: responses.pop(0),
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )
        api = types.SimpleNamespace(headers={}, timeout=10)

        response = controller.request(api, "https://example.test")

        self.assertEqual(429, response.status_code)
        self.assertEqual([4.5], clock.sleeps)
        self.assertEqual(2, controller.events)
        self.assertEqual(4.5, controller.sleep_seconds)
        self.assertTrue(controller.exhausted)
        self.assertEqual("max_429_events_exceeded", controller.exhaustion_reason)

    def test_network_retry_does_not_inflate_rate_limit_backoff(self) -> None:
        responses: list[object] = [
            RuntimeError("network unavailable"),
            FakeResponse(429),
            FakeResponse(200),
        ]
        clock = FakeClock()
        args = types.SimpleNamespace(
            max_rate_limit_sleep_seconds=20,
            max_429_events=3,
            max_runtime_seconds=30,
        )

        def request_get(*_args, **_kwargs):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        controller = RateLimitController(
            args,
            request_get=request_get,
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )

        with patch(
            "lib.fetch.zzshare_rate_limit.is_request_exception",
            return_value=True,
        ):
            response = controller.request(
                types.SimpleNamespace(headers={}, timeout=1),
                "https://example.test",
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual([2.0, 2.0], clock.sleeps)
        self.assertEqual(1, controller.network_retry_events)
        self.assertEqual(1, controller.events)

    def test_cli_flushes_checkpoint_before_rate_limit_partial_exit(self) -> None:
        old_module = sys.modules.get("zzshare.client")
        sys.modules["zzshare.client"] = types.SimpleNamespace(DataApi=RateLimitedDataApi)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                output = root / "prices.csv"
                metadata = root / "metadata.json"
                checkpoint = root / "checkpoint"
                stdout = StringIO()
                stderr = StringIO()
                with (
                    patch(
                        "lib.fetch.zzshare_a_share_data.default_request_get",
                        return_value=lambda *_args, **_kwargs: FakeResponse(429, "4"),
                    ),
                    patch("lib.fetch.zzshare_rate_limit.time.sleep"),
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    code = fetcher.main(
                        [
                            "--symbols",
                            "000001,600000",
                            "--start-date",
                            "2026-07-09",
                            "--end-date",
                            "2026-07-10",
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata),
                            "--http-url",
                            "https://example.test",
                            "--request-interval-seconds",
                            "0",
                            "--max-429-events",
                            "1",
                            "--max-rate-limit-sleep-seconds",
                            "20",
                            "--checkpoint-dir",
                            str(checkpoint),
                            "--checkpoint-batch-size",
                            "1",
                        ]
                    )
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                manifest = json.loads(
                    (checkpoint / "manifest.json").read_text(encoding="utf-8")
                )
        finally:
            if old_module is None:
                sys.modules.pop("zzshare.client", None)
            else:
                sys.modules["zzshare.client"] = old_module

        self.assertEqual(3, code)
        self.assertFalse(output.exists())
        self.assertTrue(saved["rate_limit_budget_exhausted"])
        self.assertEqual("max_429_events_exceeded", saved["rate_limit_exhaustion_reason"])
        self.assertEqual(2, saved["rate_limit_429_events"])
        self.assertEqual(4.5, saved["rate_limit_sleep_seconds"])
        self.assertEqual(["600000"], saved["unprocessed_symbols"])
        self.assertEqual([], saved["empty_symbols"])
        self.assertEqual("failed", manifest["symbols"]["000001"]["status"])
        self.assertNotIn("600000", manifest["symbols"])
        self.assertIn("unprocessed_symbols=1", stdout.getvalue())
        self.assertIn("unprocessed_symbol_examples=600000", stdout.getvalue())
        self.assertIn("rate_limit_budget_exhausted", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
