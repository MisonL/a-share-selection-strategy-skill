"""zzshare A-share fetch and field mapping helpers."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)

import os
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Optional

from lib.fetch.zzshare_a_share_checkpoint import (
    append_checkpoint_record,
    checkpoint_frame,
    checkpoint_metadata,
    completed_checkpoint_record,
    empty_checkpoint_batch,
    flush_checkpoint_batch,
    flush_checkpoint_batch_if_ready,
    prepare_checkpoint,
)
from lib.fetch.zzshare_rate_limit import (
    RateLimitController,
    default_request_get,
    install_controller,
)
from lib.selection_core.a_share_selection_symbols import parse_a_share_symbols


OUTPUT_COLUMNS = "symbol name market date open high low close preclose pctChg volume amount turn tradestatus isST source source_type source_scope real_market_data metadata_source source_claim_boundary data_source_note".split()
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount", "turn"]
DEFAULT_HTTP_URL = "https://api.zizizaizai.com"
DEFAULT_FIELDS, DEFAULT_LIMIT = "all", 1000
DEFAULT_REQUEST_INTERVAL_SECONDS = 2.1
CLAIM_BOUNDARY = "zzshare_external_api_not_broker_order_or_long_term_stability_proof"
DATA_SOURCE_NOTE = (
    "zzshare SDK endpoint; quota and stability require external verification"
)
FetchResult = tuple[list[dict[str, Any]], int, bool, Optional[dict[str, Any]]]
EMPTY_QUALITY_FIELDS = {
    "invalid_rows": 0,
    "invalid_symbols": [],
    "invalid_row_examples": [],
    "dropped_invalid_rows": 0,
}
parse_symbols = parse_a_share_symbols


@dataclass
class FetchState:
    rows: list[dict[str, Any]] = field(default_factory=list)
    symbols_meta: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    unprocessed: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)
    batch: dict[str, Any] = field(default_factory=empty_checkpoint_batch)
    skipped: int = 0
    requests: int = 0


@dataclass
class ParallelQueue:
    ready: dict[int, tuple[str, Any]] = field(default_factory=dict)
    inflight: dict[Any, int] = field(default_factory=dict)
    next_submit: int = 0
    next_commit: int = 0


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return
    import pandas as pandas_module
    import lib.selection_core.a_share_selection_tradability as tradability_module

    globals().update(
        {
            "pd": pandas_module,
            "prefixed_tradability_stats": tradability_module.prefixed_tradability_stats,
            "tradability_stats": tradability_module.tradability_stats,
        }
    )


def fetch_prices(args: Any) -> tuple[Any, dict[str, Any]]:
    ensure_runtime_dependencies()
    DataApi = data_api_factory()
    controller = RateLimitController(args, request_get=default_request_get())
    api = install_controller(
        DataApi(
            token=effective_token(args),
            timeout=float(args.timeout_seconds),
            http_url=args.http_url,
        ),
        controller,
    )
    symbols = parse_symbols(args.symbols)
    checkpoint = prepare_checkpoint(args)
    state = FetchState()
    started = time.monotonic()
    if max_concurrent_symbol_requests(args) > 1:
        unprocessed = fetch_prices_parallel(
            args, DataApi, symbols, checkpoint, state, started, controller
        )
    else:
        unprocessed = fetch_prices_serial(
            args, api, symbols, checkpoint, state, started, controller
        )
    return finalize_fetch(args, symbols, checkpoint, state, controller, unprocessed)


def data_api_factory() -> Any:
    try:
        from zzshare.client import DataApi
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("zzshare is required for this fetch script") from exc
    return DataApi


def fetch_prices_serial(
    args: Any,
    api: Any,
    symbols: list[str],
    checkpoint: Optional[dict[str, Any]],
    state: FetchState,
    started: float,
    controller: RateLimitController,
) -> list[str]:
    stopped_at = len(symbols)
    for index, symbol in enumerate(symbols):
        record = completed_checkpoint_record(checkpoint, symbol)
        if record:
            state.skipped += 1
            state.symbols_meta.append(dict(record.get("metadata", {})))
            emit_fetch_progress(args, index, symbols, state, started)
            continue
        if state.requests and args.request_interval_seconds > 0:
            time.sleep(float(args.request_interval_seconds))
        state.requests += 1
        apply_fetch_result(
            symbol,
            guarded_fetch_symbol(api, args, symbol, controller),
            state,
            checkpoint,
        )
        flush_checkpoint_batch_if_ready(checkpoint, state.batch, pd, OUTPUT_COLUMNS)
        emit_fetch_progress(args, index, symbols, state, started)
        if controller.exhausted:
            stopped_at = index + 1
            break
    return symbols[stopped_at:]


def guarded_fetch_symbol(
    api: Any,
    args: Any,
    symbol: str,
    controller: RateLimitController,
) -> FetchResult:
    try:
        result = fetch_symbol(api, args, symbol)
    except Exception as exc:  # noqa: BLE001
        result = ([], 0, False, {"symbol": symbol, "error": str(exc)})
    if controller.exhausted:
        return (
            result[0],
            result[1],
            result[2],
            rate_limit_failure(
                symbol,
                controller,
                original_failure=result[3],
            ),
        )
    return result


def emit_fetch_progress(
    args: Any,
    index: int,
    symbols: list[str],
    state: FetchState,
    started: float,
) -> None:
    emit_progress(
        args,
        index + 1,
        symbols,
        state.symbols_meta,
        started,
        state.skipped,
    )


def fetch_prices_parallel(
    args: Any,
    data_api_factory: Any,
    symbols: list[str],
    checkpoint: Optional[dict[str, Any]],
    state: FetchState,
    started: float,
    controller: RateLimitController,
) -> list[str]:
    """Fetch symbols concurrently after fetch_prices has loaded runtime globals."""
    records = [completed_checkpoint_record(checkpoint, symbol) for symbol in symbols]
    queue = ParallelQueue()
    executor = ThreadPoolExecutor(
        max_workers=max_concurrent_symbol_requests(args),
        thread_name_prefix="zzshare-fetch",
    )
    try:
        while queue.next_commit < len(symbols):
            submit_parallel_work(
                args,
                data_api_factory,
                symbols,
                records,
                executor,
                state,
                queue,
                controller,
            )
            mark_rate_limited_work(symbols, controller, queue)
            if controller.exhausted:
                mark_rate_limited_inflight(symbols, controller, queue)
            commit_parallel_work(args, symbols, checkpoint, state, queue, started)
            if queue.next_commit >= len(symbols):
                break
            if not queue.inflight:
                raise RuntimeError(
                    "zzshare parallel fetch stalled without inflight tasks"
                )
            timeout = controller.remaining_runtime_seconds()
            if timeout <= 0:
                mark_rate_limited_inflight(symbols, controller, queue)
                continue
            done, _ = wait(
                queue.inflight,
                timeout=timeout,
                return_when=FIRST_COMPLETED,
            )
            if not done:
                controller.mark_exhausted("max_runtime_seconds_exceeded")
                mark_rate_limited_inflight(symbols, controller, queue)
                continue
            for future in done:
                index = queue.inflight.pop(future)
                queue.ready[index] = ("fetched", future.result())
    finally:
        executor.shutdown(wait=not controller.exhausted)
    return list(state.unprocessed)


def submit_parallel_work(
    args: Any,
    data_api_factory: Any,
    symbols: list[str],
    records: list[Any],
    executor: ThreadPoolExecutor,
    state: FetchState,
    queue: ParallelQueue,
    controller: RateLimitController,
) -> None:
    capacity = max_concurrent_symbol_requests(args)
    while (
        queue.next_submit < len(symbols)
        and len(queue.inflight) < capacity
        and not controller.exhausted
    ):
        index = queue.next_submit
        record = records[index]
        if record:
            queue.ready[index] = ("skipped", record)
        else:
            if state.requests and args.request_interval_seconds > 0:
                time.sleep(float(args.request_interval_seconds))
            future = executor.submit(
                fetch_symbol_task,
                data_api_factory,
                args,
                symbols[index],
                controller,
            )
            queue.inflight[future] = index
            state.requests += 1
        queue.next_submit += 1


def mark_rate_limited_work(
    symbols: list[str], controller: RateLimitController, queue: ParallelQueue
) -> None:
    if not controller.exhausted or queue.next_submit >= len(symbols):
        return
    for index in range(queue.next_submit, len(symbols)):
        queue.ready[index] = (
            "fetched",
            ([], 0, False, rate_limit_failure(symbols[index], controller, unprocessed=True)),
        )
    queue.next_submit = len(symbols)


def mark_rate_limited_inflight(
    symbols: list[str],
    controller: RateLimitController,
    queue: ParallelQueue,
) -> None:
    for future, index in list(queue.inflight.items()):
        if future.done():
            queue.ready[index] = ("fetched", future.result())
            queue.inflight.pop(future, None)
            continue
        future.cancel()
        queue.ready[index] = (
            "fetched",
            ([], 0, False, rate_limit_failure(symbols[index], controller, unprocessed=True)),
        )
        queue.inflight.pop(future, None)


def commit_parallel_work(
    args: Any,
    symbols: list[str],
    checkpoint: Optional[dict[str, Any]],
    state: FetchState,
    queue: ParallelQueue,
    started: float,
) -> None:
    while queue.next_commit in queue.ready:
        status, payload = queue.ready.pop(queue.next_commit)
        if status == "skipped":
            state.skipped += 1
            state.symbols_meta.append(dict(payload.get("metadata", {})))
        else:
            apply_fetch_result(symbols[queue.next_commit], payload, state, checkpoint)
            flush_checkpoint_batch_if_ready(checkpoint, state.batch, pd, OUTPUT_COLUMNS)
        emit_fetch_progress(args, queue.next_commit, symbols, state, started)
        queue.next_commit += 1


def finalize_fetch(
    args: Any,
    symbols: list[str],
    checkpoint: Optional[dict[str, Any]],
    state: FetchState,
    controller: RateLimitController,
    unprocessed: list[str],
) -> tuple[Any, dict[str, Any]]:
    flush_checkpoint_batch(checkpoint, state.batch, pd, OUTPUT_COLUMNS)
    frame = checkpoint_frame(checkpoint, pd, OUTPUT_COLUMNS, symbols)
    if frame is None:
        frame = pd.DataFrame(state.rows, columns=OUTPUT_COLUMNS)
    metadata = build_metadata(
        args, frame, state.symbols_meta, state.failed, state.truncated
    )
    metadata.update(
        checkpoint_metadata(args, checkpoint, state.skipped, state.requests)
    )
    metadata.update(controller.metadata())
    metadata["unprocessed_symbols"] = unprocessed
    metadata["partial_result"] = bool(
        metadata["partial_result"] or metadata["unprocessed_symbols"]
    )
    return frame, metadata


def fetch_symbol_task(
    data_api_factory: Any,
    args: Any,
    symbol: str,
    controller: RateLimitController,
) -> FetchResult:
    api = install_controller(
        data_api_factory(
            token=effective_token(args),
            timeout=float(args.timeout_seconds),
            http_url=args.http_url,
        ),
        controller,
    )
    try:
        result = fetch_symbol(api, args, symbol)
        if controller.exhausted and result[3]:
            return (
                result[0],
                result[1],
                result[2],
                rate_limit_failure(
                    symbol,
                    controller,
                    original_failure=result[3],
                ),
            )
        return result
    except Exception as exc:  # noqa: BLE001
        failure = {"symbol": symbol, "error": str(exc)}
        if controller.exhausted:
            failure = rate_limit_failure(
                symbol,
                controller,
                original_failure=failure,
            )
        return [], 0, False, failure


def rate_limit_failure(
    symbol: str,
    controller: RateLimitController,
    *,
    unprocessed: bool = False,
    original_failure: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    suffix = "_unprocessed" if unprocessed else ""
    failure = dict(original_failure or {})
    failure.setdefault("symbol", symbol)
    failure.setdefault("error", controller.exhaustion_reason)
    failure["error_code"] = f"rate_limit_budget_exhausted{suffix}"
    failure["rate_limit_exhaustion_reason"] = controller.exhaustion_reason
    return failure


def apply_fetch_result(
    symbol: str,
    result: FetchResult,
    state: FetchState,
    checkpoint: Optional[dict[str, Any]],
) -> None:
    symbol_rows, pages_used, possible_truncated, failure = result
    if failure:
        if failure.get("error_code") == "rate_limit_budget_exhausted_unprocessed":
            if symbol not in state.unprocessed:
                state.unprocessed.append(symbol)
            return
        state.failed.append(failure)
    if possible_truncated:
        state.truncated.append(symbol)
    state.rows.extend(symbol_rows)
    meta = symbol_metadata(symbol, symbol_rows, pages_used, possible_truncated)
    state.symbols_meta.append(meta)
    append_checkpoint_record(
        checkpoint,
        state.batch,
        symbol,
        symbol_rows,
        meta,
        failure,
        possible_truncated,
    )


def max_concurrent_symbol_requests(args: Any) -> int:
    try:
        value = int(getattr(args, "max_concurrent_symbol_requests", 1) or 1)
    except (TypeError, ValueError):
        return 1
    return max(value, 1)


def emit_progress(
    args: Any,
    processed: int,
    symbols: list[str],
    symbols_meta: list[dict[str, Any]],
    started: float,
    skipped: int,
) -> None:
    interval = int(getattr(args, "progress_interval", 0) or 0)
    total = len(symbols)
    if interval < 1 or (processed % interval != 0 and processed != total):
        return
    rows = sum(int(item.get("rows", 0) or 0) for item in symbols_meta)
    elapsed = max(time.monotonic() - started, 0.0)
    rate = processed / elapsed if elapsed else 0.0
    remaining = total - processed
    eta = remaining / rate if rate else 0.0
    print(
        "PROGRESS: "
        f"symbols={processed}/{total} rows={rows} skipped_from_checkpoint={skipped} "
        f"elapsed_seconds={elapsed:.1f} eta_seconds={eta:.1f}",
        file=sys.stderr,
    )


def effective_token(_args: Any) -> str:
    return str(os.environ.get("ZZSHARE_TOKEN", "")).strip()


def fetch_symbol(api: Any, args: Any, symbol: str) -> FetchResult:
    rows: list[dict[str, Any]] = []
    limit = int(args.limit)
    code = ts_code(symbol)
    start_date = zzshare_date(args.start_date)
    end_date = zzshare_date(args.end_date)
    for page in range(int(args.max_pages)):
        if page and float(args.request_interval_seconds) > 0:
            time.sleep(float(args.request_interval_seconds))
        offset = page * limit
        try:
            raw = api.daily(
                ts_code=code,
                start_date=start_date,
                end_date=end_date,
                fields=args.fields,
                adj=args.adjust,
                limit=limit,
                offset=offset,
            )
            page_rows = collect_rows(raw, symbol)
        except Exception as exc:  # noqa: BLE001
            failure = page_failure(
                symbol, code, start_date, end_date, page, offset, limit, exc
            )
            return rows, page, False, failure
        rows.extend(page_rows)
        if len(page_rows) < limit:
            return rows, page + 1, False, None
    possible_truncated = bool(rows and len(rows) >= limit * int(args.max_pages))
    return rows, int(args.max_pages), possible_truncated, None


def page_failure(
    symbol: str,
    code: str,
    start_date: str,
    end_date: str,
    page: int,
    offset: int,
    limit: int,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "ts_code": code,
        "page": page + 1,
        "offset": offset,
        "limit": limit,
        "start_date": start_date,
        "end_date": end_date,
        "error": str(exc),
    }


def zzshare_date(text: str) -> str:
    compact = text.replace("-", "").strip()
    if not compact.isdigit() or len(compact) != 8:
        raise ValueError(f"date must be YYYY-MM-DD or YYYYMMDD: {text}")
    return compact


def ts_code(symbol: str) -> str:
    if symbol.startswith(("4", "8", "920")):
        suffix = "BJ"
    else:
        suffix = "SH" if symbol.startswith(("6", "9")) else "SZ"
    return f"{symbol}.{suffix}"


def collect_rows(frame: Any, requested_symbol: str) -> list[dict[str, Any]]:
    ensure_runtime_dependencies()
    if frame.empty:
        return []
    columns = resolve_columns(frame)
    rows = []
    for _, row in frame.iterrows():
        row_symbol = normalize_ts_code_symbol(
            row_value(row, columns["symbol"], requested_symbol)
        )
        if row_symbol and row_symbol != requested_symbol:
            continue
        rows.append(row_record(row, columns, requested_symbol))
    return rows


def resolve_columns(frame: Any) -> dict[str, str]:
    lookup = {str(column).strip().lower(): str(column) for column in frame.columns}
    required = {
        "symbol": first_present(lookup, ["ts_code", "symbol", "code"]),
        "date": first_present(lookup, ["trade_date", "date"]),
        "open": first_present(lookup, ["open"]),
        "high": first_present(lookup, ["high"]),
        "low": first_present(lookup, ["low"]),
        "close": first_present(lookup, ["close"]),
        "volume": first_present(lookup, ["volume", "vol"]),
        "amount": first_present(lookup, ["turnover", "amount"]),
    }
    missing = [name for name, source in required.items() if not source]
    if missing:
        raise ValueError(
            f"zzshare daily missing required columns: {', '.join(missing)}"
        )
    return optional_columns(lookup, required)


def optional_columns(
    lookup: dict[str, str], required: dict[str, str]
) -> dict[str, str]:
    return {
        **required,
        "turn": first_present(lookup, ["turnover_rate", "turn", "turnoverrate"]),
        "name": first_present(lookup, ["name"]),
        "preclose": first_present(lookup, ["prev_close", "pre_close", "preclose"]),
        "pctChg": first_present(lookup, ["quote_rate", "pct_chg", "pctChg"]),
        "tradestatus": first_present(
            lookup, ["tradestatus", "trade_status", "is_paused"]
        ),
        "isST": first_present(lookup, ["is_st", "isST"]),
    }


def first_present(lookup: dict[str, str], names: list[str]) -> str:
    for name in names:
        key = name.lower()
        if key in lookup:
            return lookup[key]
    return ""


def row_record(
    row: Any, columns: dict[str, str], requested_symbol: str
) -> dict[str, Any]:
    paused = row_value(row, columns["tradestatus"])
    source = (
        columns["tradestatus"].lower() == "is_paused"
        if columns["tradestatus"]
        else False
    )
    return {
        "symbol": requested_symbol,
        "name": row_value(row, columns["name"]),
        "market": "A-share",
        "date": output_date(row_value(row, columns["date"])),
        "open": row_value(row, columns["open"]),
        "high": row_value(row, columns["high"]),
        "low": row_value(row, columns["low"]),
        "close": row_value(row, columns["close"]),
        "preclose": row_value(row, columns["preclose"]),
        "pctChg": row_value(row, columns["pctChg"]),
        "volume": row_value(row, columns["volume"]),
        "amount": row_value(row, columns["amount"]),
        "turn": row_value(row, columns["turn"]),
        "tradestatus": tradestatus_value(paused, source),
        "isST": row_value(row, columns["isST"]),
        "source": "zzshare",
        "source_type": "external_fetch",
        "source_scope": "zzshare_history_fetch",
        "real_market_data": True,
        "metadata_source": "zzshare",
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": DATA_SOURCE_NOTE,
    }


def row_value(row: Any, column: str, default: Any = "") -> Any:
    return row.get(column, default) if column else default


def output_date(value: Any) -> str:
    text = str(value).strip()
    compact = text.replace("-", "")
    if compact.isdigit() and len(compact) == 8:
        return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    return text


def normalize_ts_code_symbol(value: Any) -> str:
    text = str(value).strip()
    if "." in text:
        return text.split(".", 1)[0].zfill(6)
    return text.zfill(6) if text.isdigit() else text


def tradestatus_value(value: Any, is_paused_source: bool) -> str:
    if not is_paused_source:
        return str(value).strip() if str(value).strip() else ""
    text = str(value).strip().lower()
    if text in {"0", "0.0", "false"}:
        return "1"
    if text in {"1", "1.0", "true"}:
        return "0"
    return ""


def symbol_metadata(
    symbol: str, rows: list[dict[str, Any]], pages_used: int, possible_truncated: bool
) -> dict[str, Any]:
    dates = [str(row["date"]) for row in rows if str(row["date"])]
    return {
        "symbol": symbol,
        "ts_code": ts_code(symbol),
        "rows": len(rows),
        "date_min": min(dates) if dates else "",
        "date_max": max(dates) if dates else "",
        "pages_used": int(pages_used),
        "possibly_truncated": bool(possible_truncated),
    }


def build_metadata(
    args: Any,
    frame: Any,
    symbols_meta: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    truncated: list[str],
) -> dict[str, Any]:
    failed_values = failure_symbols(failed)
    empty_values = empty_symbols(symbols_meta, excluded=failed_values)
    return {
        "source": "zzshare",
        "source_type": "external_fetch",
        "source_scope": "zzshare_history_fetch",
        "real_market_data": True,
        "partial_result": bool(failed or empty_values or truncated),
        "source_claim_boundary": CLAIM_BOUNDARY,
        "data_source_note": DATA_SOURCE_NOTE,
        "requested_symbols": parse_symbols(args.symbols),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "adjust": args.adjust,
        "fields": args.fields,
        "limit": int(args.limit),
        "max_pages": int(args.max_pages),
        "http_url": str(args.http_url).rstrip("/"),
        "timeout_seconds": float(args.timeout_seconds),
        "request_interval_seconds": float(args.request_interval_seconds),
        "max_concurrent_symbol_requests": int(
            getattr(args, "max_concurrent_symbol_requests", 1) or 1
        ),
        "token_configured": bool(effective_token(args)),
        "rows": int(len(frame)),
        "raw_rows": int(len(frame)),
        "symbol_count": int(frame["symbol"].nunique()) if not frame.empty else 0,
        "symbols": symbols_meta,
        "failed_symbols": failed,
        "empty_symbols": empty_values,
        "possibly_truncated_symbols": truncated,
        **dict(EMPTY_QUALITY_FIELDS),
        **prefixed_tradability_stats(frame, "raw_"),
        **tradability_stats(frame),
    }


def empty_symbols(
    symbols_meta: list[dict[str, Any]],
    *,
    excluded: set[str] | None = None,
) -> list[str]:
    excluded_values = excluded or set()
    return [
        str(item["symbol"])
        for item in symbols_meta
        if int(item["rows"]) == 0 and str(item["symbol"]) not in excluded_values
    ]


def failure_symbols(failed: list[dict[str, Any]]) -> set[str]:
    return {
        str(item.get("symbol", "")).strip()
        for item in failed
        if str(item.get("symbol", "")).strip()
    }
