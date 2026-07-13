#!/usr/bin/env python3
"""Fetch Eastmoney A-share realtime spot snapshot into local CSV metadata."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
FIELDS = "f12,f14,f2,f3,f6,f100"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://quote.eastmoney.com/center/gridlist.html",
}
DATA_SOURCE_NOTE = (
    "eastmoney public API spot snapshot; scope is requested pages only; "
    "pagination is sorted by stable symbol code"
)
CSV_COLUMNS = [
    "symbol",
    "name",
    "spot_price",
    "spot_pct_chg",
    "spot_amount",
    "spot_industry",
]
Opener = Callable[[str, float], bytes]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)
    metadata_output = Path(args.metadata_output)
    try:
        rows, metadata = fetch_snapshot(args, open_url)
        metadata = output_status(metadata, output_written=True, metadata_output_written=True)
        write_csv(output, rows)
        write_json(metadata, metadata_output)
    except Exception as exc:  # noqa: BLE001
        remove_output(output)
        print(
            f"ERROR: code=fetch_failed output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    errors = strict_errors(metadata, args)
    if errors:
        if metadata["raw_items"] == 0:
            metadata = output_status(metadata, output_written=False, metadata_output_written=True)
            remove_output(output)
            write_json(metadata, metadata_output)
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; "
            f"{'; '.join(errors)} "
            f"output_written={str(metadata['output_written']).lower()} "
            f"metadata_output_written={str(metadata['metadata_output_written']).lower()}",
            file=sys.stderr,
        )
        return 3
    print_summary(metadata)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Eastmoney A-share spot data into local CSV and metadata. "
            "Partial pages or a small requested page set do not prove full-market coverage."
        )
    )
    parser.add_argument("--output", required=True, help="Output spot CSV path.")
    parser.add_argument("--metadata-output", required=True, help="Output metadata JSON path.")
    parser.add_argument("--pages", type=positive_int, default=1, help="Pages to request.")
    parser.add_argument("--page-size", type=positive_int, default=100)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--retries", type=non_negative_int, default=1)
    parser.add_argument(
        "--retry-interval-seconds",
        type=non_negative_float,
        default=0.0,
        help="Sleep between retry attempts after a failed page request.",
    )
    parser.add_argument(
        "--request-interval-seconds",
        type=non_negative_float,
        default=0.0,
        help="Sleep between page requests. Use a positive value for long full-market scans.",
    )
    parser.add_argument(
        "--stop-after-empty-failed-pages",
        type=non_negative_int,
        default=5,
        help=(
            "Stop early after N consecutive failed pages when no rows have been "
            "collected. Use 0 to disable."
        ),
    )
    parser.add_argument(
        "--fail-on-partial",
        action="store_true",
        help="Return non-zero when metadata partial_result=true.",
    )
    return parser


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0 or not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("value must be a finite non-negative number")
    return parsed


def open_url(url: str, timeout: float) -> bytes:
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read()


def fetch_snapshot(args: argparse.Namespace, opener: Opener) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started_at = utc_now()
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    failed_pages: list[dict[str, Any]] = []
    attempted_pages = 0
    stopped_early = False
    stop_reason = ""
    consecutive_empty_failures = 0
    for page in range(1, args.pages + 1):
        if attempted_pages and args.request_interval_seconds > 0:
            time.sleep(float(args.request_interval_seconds))
        attempted_pages += 1
        try:
            items = page_items(fetch_page_with_retries(args, page, opener))
            rows.extend(normalize_item(item) for item in items)
            consecutive_empty_failures = 0
        except Exception as exc:  # noqa: BLE001
            failed_pages.append({"page": page, "error": str(exc)})
            consecutive_empty_failures += 1
            if should_stop_after_empty_failures(
                args,
                rows,
                consecutive_empty_failures,
            ):
                stopped_early = True
                stop_reason = "consecutive_failed_pages_before_any_rows"
                break
    metadata = build_metadata(
        args,
        rows,
        failed_pages,
        started_at,
        started,
        attempted_pages=attempted_pages,
        stopped_early=stopped_early,
        stop_reason=stop_reason,
    )
    return rows, metadata


def should_stop_after_empty_failures(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    consecutive_failures: int,
) -> bool:
    threshold = int(args.stop_after_empty_failed_pages)
    return threshold > 0 and not rows and consecutive_failures >= threshold


def fetch_page_with_retries(
    args: argparse.Namespace,
    page: int,
    opener: Opener,
) -> dict[str, Any]:
    attempts = int(args.retries) + 1
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fetch_page(args, page, opener)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < attempts - 1 and args.retry_interval_seconds > 0:
                time.sleep(float(args.retry_interval_seconds))
    raise RuntimeError(f"page={page} attempts={attempts} error={last_error}")


def fetch_page(args: argparse.Namespace, page: int, opener: Opener) -> dict[str, Any]:
    payload = opener(page_url(page, args.page_size), float(args.timeout_seconds))
    return json.loads(payload.decode("utf-8"))


def page_url(page: int, page_size: int) -> str:
    query = urlencode(
        {
            "pn": page,
            "pz": page_size,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f12",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": FIELDS,
        }
    )
    return f"{BASE_URL}?{query}"


def page_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    diff = data.get("diff") or []
    if isinstance(diff, dict):
        diff = list(diff.values())
    if not isinstance(diff, list):
        raise ValueError("eastmoney payload data.diff must be a list or dict")
    return [item for item in diff if isinstance(item, dict)]


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(item.get("f12", "")),
        "name": item.get("f14", ""),
        "spot_price": item.get("f2", ""),
        "spot_pct_chg": item.get("f3", ""),
        "spot_amount": item.get("f6", ""),
        "spot_industry": item.get("f100", ""),
    }


def build_metadata(
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    failed_pages: list[dict[str, Any]],
    started_at: str | None = None,
    monotonic_started: float | None = None,
    *,
    attempted_pages: int | None = None,
    stopped_early: bool = False,
    stop_reason: str = "",
) -> dict[str, Any]:
    attempted = int(args.pages if attempted_pages is None else attempted_pages)
    successful = int(attempted - len(failed_pages))
    finished_at = utc_now()
    return {
        "source": "eastmoney",
        "source_type": "external_fetch",
        "source_scope": "a_share_spot_snapshot",
        "real_market_data": True,
        "data_source_note": DATA_SOURCE_NOTE,
        "requested_pages": int(args.pages),
        "attempted_pages": attempted,
        "retry_attempts_per_page": int(args.retries),
        "retries": int(args.retries),
        "retry_interval_seconds": float(args.retry_interval_seconds),
        "request_interval_seconds": float(args.request_interval_seconds),
        "stop_after_empty_failed_pages": int(args.stop_after_empty_failed_pages),
        "stopped_early": bool(stopped_early),
        "stop_reason": stop_reason,
        "successful_pages": successful,
        "pages_successful": successful,
        "failed_pages": failed_pages,
        "pages_failed": len(failed_pages),
        "errors": error_summaries(failed_pages),
        "raw_items": len(rows),
        "filtered_items": len(rows),
        "snapshot_time": finished_at,
        "started_at": started_at or finished_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds(monotonic_started),
        "partial_result": bool(failed_pages) or bool(stopped_early),
        "coverage_claim": coverage_claim(bool(failed_pages) or bool(stopped_early)),
        "source_claim_boundary": source_claim_boundary(
            bool(failed_pages) or bool(stopped_early)
        ),
        "allowed_failure_actions": allowed_failure_actions(
            bool(failed_pages) or bool(stopped_early), len(rows)
        ),
        "output": str(Path(args.output)),
        "metadata_output": str(Path(args.metadata_output)),
    }


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def duration_seconds(started: float | None) -> float:
    if started is None:
        return 0.0
    return round(max(time.monotonic() - started, 0.0), 6)


def error_summaries(failed_pages: list[dict[str, Any]]) -> list[str]:
    return [
        f"page={item.get('page')} error={item.get('error')}"
        for item in failed_pages
    ]


def output_status(
    metadata: dict[str, Any],
    *,
    output_written: bool,
    metadata_output_written: bool,
) -> dict[str, Any]:
    return {
        **metadata,
        "output_written": bool(output_written),
        "metadata_output_written": bool(metadata_output_written),
    }


def coverage_claim(partial_result: bool) -> str:
    if partial_result:
        return "partial_not_full_market"
    return "requested_pages_snapshot_not_full_market_proof"


def source_claim_boundary(partial_result: bool) -> str:
    if partial_result:
        return "partial_spot_snapshot_not_full_market_completion"
    return "requested_pages_snapshot_not_full_market_completion"


def strict_errors(metadata: dict[str, Any], args: argparse.Namespace) -> list[str]:
    errors = []
    if args.fail_on_partial and metadata["partial_result"]:
        errors.append(f"partial_result=true failed_pages={len(metadata['failed_pages'])}")
    if metadata["raw_items"] == 0:
        errors.append("raw_items=0")
    return errors


def allowed_failure_actions(partial_result: bool, raw_items: int) -> list[str]:
    if raw_items == 0:
        return [
            "retry_with_more_pages_or_later_window",
            "switch_source_and_disclose_scope",
            "reuse_landed_snapshot_only_if_user_accepts_stale_scope",
        ]
    if partial_result:
        return [
            "rerun_with_fail_on_partial",
            "use_partial_snapshot_only_with_partial_result_disclosure",
            "switch_source_and_compare_source_scope",
        ]
    return []


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_output(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        return
    path.unlink()


def print_summary(metadata: dict[str, Any], prefix: str = "OK") -> None:
    status = "PARTIAL" if prefix == "OK" and metadata["partial_result"] else prefix
    print(
        f"{status}: source=eastmoney source_scope={metadata['source_scope']} "
        f"requested_pages={metadata['requested_pages']} "
        f"attempted_pages={metadata.get('attempted_pages', metadata['requested_pages'])} "
        f"raw_items={metadata['raw_items']} filtered_items={metadata['filtered_items']} "
        f"retries={metadata['retry_attempts_per_page']} "
        f"stopped_early={str(metadata.get('stopped_early', False)).lower()} "
        f"successful_pages={metadata['successful_pages']} "
        f"pages_successful={metadata['pages_successful']} "
        f"failed_pages={len(metadata['failed_pages'])} "
        f"partial_result={str(metadata['partial_result']).lower()} "
        f"coverage_claim={metadata['coverage_claim']} "
        f"source_claim_boundary={metadata['source_claim_boundary']} "
        f"output_written={str(metadata.get('output_written', False)).lower()} "
        "metadata_output_written="
        f"{str(metadata.get('metadata_output_written', False)).lower()} "
        f"output={metadata['output']} metadata={metadata['metadata_output']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
