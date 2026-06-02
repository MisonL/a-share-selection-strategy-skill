#!/usr/bin/env python3
"""Fetch Eastmoney A-share realtime spot snapshot into local CSV metadata."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import urlopen


BASE_URL = "https://push2.eastmoney.com/api/qt/clist/get"
FIELDS = "f12,f14,f2,f3,f6,f100"
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
    try:
        rows, metadata = fetch_snapshot(args, open_url)
        write_csv(Path(args.output), rows)
        write_json(metadata, Path(args.metadata_output))
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: code=fetch_failed output_written=false message={exc}",
            file=sys.stderr,
        )
        return 2
    errors = strict_errors(metadata, args)
    if errors:
        print_summary(metadata, prefix="ERROR_SUMMARY")
        print(f"ERROR: strict gate failed; {'; '.join(errors)}", file=sys.stderr)
        return 3
    print_summary(metadata)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Eastmoney A-share spot data.")
    parser.add_argument("--output", required=True, help="Output spot CSV path.")
    parser.add_argument("--metadata-output", required=True, help="Output metadata JSON path.")
    parser.add_argument("--pages", type=positive_int, default=1, help="Pages to request.")
    parser.add_argument("--page-size", type=positive_int, default=100)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--retries", type=non_negative_int, default=1)
    parser.add_argument("--fail-on-partial", action="store_true")
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


def open_url(url: str, timeout: float) -> bytes:
    with urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.read()


def fetch_snapshot(args: argparse.Namespace, opener: Opener) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    failed_pages: list[dict[str, Any]] = []
    for page in range(1, args.pages + 1):
        try:
            items = page_items(fetch_page_with_retries(args, page, opener))
            rows.extend(normalize_item(item) for item in items)
        except Exception as exc:  # noqa: BLE001
            failed_pages.append({"page": page, "error": str(exc)})
    metadata = build_metadata(args, rows, failed_pages)
    return rows, metadata


def fetch_page_with_retries(
    args: argparse.Namespace,
    page: int,
    opener: Opener,
) -> dict[str, Any]:
    attempts = int(args.retries) + 1
    last_error: Exception | None = None
    for _attempt in range(attempts):
        try:
            return fetch_page(args, page, opener)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
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
            "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
            "fields": FIELDS,
        }
    )
    return f"{BASE_URL}?{query}"


def page_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    diff = data.get("diff") or []
    if not isinstance(diff, list):
        raise ValueError("eastmoney payload data.diff must be a list")
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
) -> dict[str, Any]:
    successful = int(args.pages - len(failed_pages))
    return {
        "source": "eastmoney",
        "source_scope": "a_share_spot_snapshot",
        "requested_pages": int(args.pages),
        "retry_attempts_per_page": int(args.retries),
        "successful_pages": successful,
        "failed_pages": failed_pages,
        "raw_items": len(rows),
        "filtered_items": len(rows),
        "snapshot_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "partial_result": bool(failed_pages),
        "allowed_failure_actions": allowed_failure_actions(bool(failed_pages), len(rows)),
        "output": str(Path(args.output)),
        "metadata_output": str(Path(args.metadata_output)),
    }


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


def print_summary(metadata: dict[str, Any], prefix: str = "OK") -> None:
    print(
        f"{prefix}: source=eastmoney raw_items={metadata['raw_items']} "
        f"retries={metadata['retry_attempts_per_page']} "
        f"successful_pages={metadata['successful_pages']} "
        f"failed_pages={len(metadata['failed_pages'])} "
        f"partial_result={str(metadata['partial_result']).lower()} "
        f"output={metadata['output']} metadata={metadata['metadata_output']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
