"""Bounded shared HTTP retry control for zzshare rate limits."""

from __future__ import annotations

import threading
import time
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable


DEFAULT_MAX_RATE_LIMIT_SLEEP_SECONDS = 120.0
DEFAULT_MAX_429_EVENTS = 3
DEFAULT_MAX_RUNTIME_SECONDS = 900.0
RETRY_AFTER_PADDING_SECONDS = 0.5
MAX_NETWORK_RETRIES = 3


class RateLimitController:
    def __init__(
        self,
        args: Any,
        *,
        request_get: Callable[..., Any],
        sleep: Callable[[float], None] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.request_get = request_get
        self.sleep = sleep or time.sleep
        self.monotonic = monotonic or time.monotonic
        self.started = self.monotonic()
        self.max_sleep = float(
            getattr(
                args,
                "max_rate_limit_sleep_seconds",
                DEFAULT_MAX_RATE_LIMIT_SLEEP_SECONDS,
            )
        )
        self.max_events = int(getattr(args, "max_429_events", DEFAULT_MAX_429_EVENTS))
        self.max_runtime = float(
            getattr(args, "max_runtime_seconds", DEFAULT_MAX_RUNTIME_SECONDS)
        )
        self.events = 0
        self.sleep_seconds = 0.0
        self._exhausted = False
        self._exhaustion_reason = ""
        self.retry_after_values: list[float] = []
        self.network_retry_events = 0
        self.network_retry_sleep_seconds = 0.0
        self._lock = threading.RLock()

    def request(self, api: Any, url: str, params: Any = None) -> Any:
        network_backoff = 2.0
        rate_limit_backoff = 2.0
        network_retries = 0
        while True:
            with self._lock:
                if not self.check_runtime_budget():
                    return budget_response()
            try:
                response = self.request_get(
                    url,
                    params=params,
                    headers=api.headers,
                    timeout=api.timeout,
                )
            except Exception as exc:  # noqa: BLE001
                if not is_request_exception(exc):
                    raise
                network_retries += 1
                with self._lock:
                    if self._exhausted:
                        return budget_response()
                    self.network_retry_events += 1
                    if network_retries > MAX_NETWORK_RETRIES:
                        raise
                    allowed = self.reserve_network_sleep(network_backoff)
                if not allowed:
                    return budget_response()
                self.sleep(network_backoff)
                network_backoff *= 2.0
                continue
            if response.status_code != 429:
                return response
            retry_after = retry_after_seconds(response.headers.get("Retry-After"))
            delay = (
                retry_after + RETRY_AFTER_PADDING_SECONDS
                if retry_after
                else rate_limit_backoff
            )
            with self._lock:
                if self._exhausted:
                    return budget_response()
                self.events += 1
                self.retry_after_values.append(retry_after)
                if not self.reserve_sleep(delay):
                    return response
                self.sleep(delay)
            rate_limit_backoff *= 2.0

    def check_runtime_budget(self) -> bool:
        with self._lock:
            if self._exhausted:
                return False
            return self.remaining_runtime_seconds() > 0

    def remaining_runtime_seconds(self) -> float:
        with self._lock:
            elapsed = self.monotonic() - self.started
            remaining = self.max_runtime - elapsed
            if remaining > 0:
                return remaining
            self.mark_exhausted("max_runtime_seconds_exceeded")
            return 0.0

    def reserve_sleep(self, delay: float) -> bool:
        if self.events > self.max_events:
            self.mark_exhausted("max_429_events_exceeded")
            return False
        if self.sleep_seconds + delay > self.max_sleep:
            self.mark_exhausted("max_rate_limit_sleep_seconds_exceeded")
            return False
        if self.monotonic() - self.started + delay > self.max_runtime:
            self.mark_exhausted("max_runtime_seconds_exceeded")
            return False
        self.sleep_seconds += delay
        return True

    def reserve_network_sleep(self, delay: float) -> bool:
        if self.monotonic() - self.started + delay > self.max_runtime:
            self.mark_exhausted("max_runtime_seconds_exceeded")
            return False
        self.network_retry_sleep_seconds += delay
        return True

    def mark_exhausted(self, reason: str) -> None:
        with self._lock:
            self._exhausted = True
            if not self._exhaustion_reason:
                self._exhaustion_reason = reason

    @property
    def exhausted(self) -> bool:
        with self._lock:
            return self._exhausted

    @property
    def exhaustion_reason(self) -> str:
        with self._lock:
            return self._exhaustion_reason

    def metadata(self) -> dict[str, Any]:
        with self._lock:
            return {
                "rate_limit_429_events": self.events,
                "rate_limit_sleep_seconds": round(self.sleep_seconds, 6),
                "rate_limit_retry_after_seconds": list(self.retry_after_values),
                "network_retry_events": self.network_retry_events,
                "network_retry_sleep_seconds": round(
                    self.network_retry_sleep_seconds, 6
                ),
                "rate_limit_budget_exhausted": self._exhausted,
                "rate_limit_exhaustion_reason": self._exhaustion_reason,
                "max_rate_limit_sleep_seconds": self.max_sleep,
                "max_429_events": self.max_events,
                "max_runtime_seconds": self.max_runtime,
            }


def install_controller(api: Any, controller: RateLimitController) -> Any:
    def controlled_request(url: str, params: Any = None, max_retries: int = 3) -> Any:
        del max_retries
        return controller.request(api, url, params)

    api._request_with_retry = controlled_request
    return api


def is_request_exception(exc: Exception) -> bool:
    try:
        import requests
    except ModuleNotFoundError:
        return False

    return isinstance(exc, requests.RequestException)


def default_request_get() -> Callable[..., Any]:
    try:
        import requests
    except ModuleNotFoundError:
        def missing_requests(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("requests is required for zzshare HTTP requests")

        return missing_requests
    return requests.get


def retry_after_seconds(value: Any, now: datetime | None = None) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        seconds = float(text)
        return seconds if math.isfinite(seconds) and seconds > 0 else 0.0
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            return 0.0
    current = now or datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max((parsed - current).total_seconds(), 0.0)


def budget_response() -> Any:
    return type(
        "RateLimitBudgetResponse",
        (),
        {
            "status_code": 429,
            "headers": {},
            "text": "rate limit budget exhausted",
        },
    )()
