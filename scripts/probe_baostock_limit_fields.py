#!/usr/bin/env python3
"""Probe baostock field availability without modeling limit rules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from stock_selection_symbols import baostock_code, parse_six_digit_symbols

CANDIDATE_FIELDS = ("up_limit", "down_limit", "limit_status", "is_trading", "suspended")
CONTROL_FIELDS = ("preclose", "pctChg", "tradestatus", "isST", "turn", "volume", "amount")
DIRECT_LIMIT_FIELDS = frozenset(("up_limit", "down_limit", "limit_status"))
TRADING_STATE_FIELDS = frozenset(("is_trading", "suspended"))
BASE_FIELDS = ("date", "code")
PARAMETER_ERROR_CODES = {"10004012"}
SAMPLE_ROWS = 3


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = probe_fields(args)
        write_json(report, Path(args.output))
        errors = strict_errors(report, args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: code=probe_failed output_written=false message={exc}", file=sys.stderr)
        return 2
    if errors:
        print_summary(report, prefix="ERROR_SUMMARY")
        print(
            "ERROR: strict gate failed; " + "; ".join(errors) + " output_written=true",
            file=sys.stderr,
        )
        return 3
    print_summary(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe baostock daily field availability.")
    parser.add_argument("--symbols", required=True, help="Comma-separated six-digit symbols.")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--adjust", default="3", help="baostock adjustflag. Default: 3.")
    parser.add_argument("--candidate-fields", default=",".join(CANDIDATE_FIELDS))
    parser.add_argument("--control-fields", default=",".join(CONTROL_FIELDS))
    parser.add_argument("--fail-on-provider-error", action="store_true")
    parser.add_argument("--require-control-rows", action="store_true")
    return parser


def probe_fields(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import baostock as bs
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("baostock is required for this probe script") from exc
    symbols = parse_symbols(args.symbols)
    candidate_fields = parse_fields(args.candidate_fields)
    control_fields = parse_fields(args.control_fields)
    login = bs.login()
    try:
        if login.error_code != "0":
            raise RuntimeError(f"baostock login failed: {login.error_code} {login.error_msg}")
        results = field_results(bs, args=args, symbols=symbols, fields=candidate_fields, role="candidate")
        results.extend(field_results(bs, args=args, symbols=symbols, fields=control_fields, role="control"))
    finally:
        bs.logout()
    return build_report(args=args, symbols=symbols, candidate_fields=candidate_fields, control_fields=control_fields, results=results)


def field_results(
    bs: Any,
    *,
    args: argparse.Namespace,
    symbols: list[str],
    fields: list[str],
    role: str,
) -> list[dict[str, Any]]:
    return [probe_one_field(bs, args=args, field=field, symbols=symbols, role=role) for field in fields]


def parse_fields(text: str) -> list[str]:
    fields = [item.strip() for item in text.split(",") if item.strip()]
    if not fields:
        raise ValueError("fields must not be empty")
    invalid = [field for field in fields if "," in field or field in BASE_FIELDS]
    if invalid:
        raise ValueError(f"invalid probe fields: {','.join(invalid)}")
    return fields


def probe_one_field(
    bs: Any,
    *,
    args: argparse.Namespace,
    field: str,
    symbols: list[str],
    role: str,
) -> dict[str, Any]:
    details = [query_symbol_field(bs, args=args, field=field, symbol=symbol) for symbol in symbols]
    supported = any(item["status"] == "supported" for item in details)
    provider_error = any(item["status"] == "provider_error" for item in details)
    status = "supported" if supported else "provider_error" if provider_error else "unsupported"
    return {
        "field": field,
        "field_role": f"{role}_field",
        "overall_status": status,
        "supported": supported,
        "rows": sum(int(item["rows"]) for item in details),
        "symbol_results": details,
        "error_codes": sorted({item["error_code"] for item in details if item["error_code"]}),
        "sample_rows": [row for item in details for row in item["sample_rows"]][:SAMPLE_ROWS],
        **field_stats(field, details),
    }


def query_symbol_field(
    bs: Any,
    *,
    args: argparse.Namespace,
    field: str,
    symbol: str,
) -> dict[str, Any]:
    query_fields = ",".join((*BASE_FIELDS, field))
    result = bs.query_history_k_data_plus(
        baostock_code(symbol),
        query_fields,
        start_date=args.start_date,
        end_date=args.end_date,
        frequency="d",
        adjustflag=str(args.adjust),
    )
    if result.error_code != "0":
        status = "unsupported" if str(result.error_code) in PARAMETER_ERROR_CODES else "provider_error"
        return symbol_result(symbol=symbol, field=field, query_fields=query_fields, status=status, error_code=str(result.error_code), error_msg=str(result.error_msg))
    row_count, samples, values = collect_values(result, field)
    return symbol_result(symbol=symbol, field=field, query_fields=query_fields, status="supported", row_count=row_count, samples=samples, values=values)


def collect_values(result: Any, field: str) -> tuple[int, list[dict[str, str]], list[str]]:
    samples: list[dict[str, str]] = []
    values: list[str] = []
    row_count = 0
    while result.next():
        raw = dict(zip(result.fields, result.get_row_data()))
        row_count += 1
        values.append(raw.get(field, ""))
        if len(samples) < SAMPLE_ROWS:
            samples.append({"date": raw.get("date", ""), "code": raw.get("code", ""), field: raw.get(field, "")})
    return row_count, samples, values


def symbol_result(
    *,
    symbol: str,
    field: str,
    query_fields: str,
    status: str,
    row_count: int = 0,
    samples: list[dict[str, str]] | None = None,
    values: list[str] | None = None,
    error_code: str = "",
    error_msg: str = "",
) -> dict[str, Any]:
    value_list = values or []
    low, high = numeric_range(value_list)
    return {
        "symbol": symbol,
        "source_code": baostock_code(symbol),
        "query_fields": query_fields,
        "field": field,
        "status": status,
        "rows": row_count,
        "missing_values": count_missing(value_list),
        "value_counts": value_counts(value_list),
        "numeric_min": low,
        "numeric_max": high,
        "error_code": error_code,
        "error_msg": error_msg,
        "sample_rows": samples or [],
    }


def field_stats(field: str, details: list[dict[str, Any]]) -> dict[str, Any]:
    values = expand_values(details)
    low, high = numeric_range(values)
    return {
        "missing_values": sum(int(item["missing_values"]) for item in details),
        "value_counts": value_counts(values) if field in {"tradestatus", "isST"} else {},
        "numeric_min": low,
        "numeric_max": high,
    }


def expand_values(details: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for item in details:
        for value, count in item["value_counts"].items():
            values.extend([value] * int(count))
    return values


def count_missing(values: list[str]) -> int:
    return sum(1 for value in values if str(value).strip() == "")


def value_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        text = str(value)
        counts[text] = counts.get(text, 0) + 1
    return dict(sorted(counts.items()))


def numeric_range(values: list[str]) -> tuple[float | None, float | None]:
    numbers = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number != number:
            continue
        numbers.append(number)
    if not numbers:
        return None, None
    return min(numbers), max(numbers)


def parse_symbols(text: str) -> list[str]:
    return parse_six_digit_symbols(text)


def build_report(
    *,
    args: argparse.Namespace,
    symbols: list[str],
    candidate_fields: list[str],
    control_fields: list[str],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "source": "baostock",
        "probe_type": "limit_field_availability",
        "requested_symbols": symbols,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "frequency": "d",
        "adjustflag": str(args.adjust),
        "candidate_fields": candidate_fields,
        "control_fields": control_fields,
        "limit_rules_model": "not_modeled",
        "rule_inference_performed": False,
        "field_results": results,
        "summary": summary(results),
    }


def summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    candidate = [item for item in results if item["field_role"] == "candidate_field"]
    control = [item for item in results if item["field_role"] == "control_field"]
    supported_candidate = [item["field"] for item in candidate if item["overall_status"] == "supported"]
    supported_direct_limit = [field for field in supported_candidate if field in DIRECT_LIMIT_FIELDS]
    supported_trading_state = [field for field in supported_candidate if field in TRADING_STATE_FIELDS]
    provider_error = [item["field"] for item in results if any(detail["status"] == "provider_error" for detail in item["symbol_results"])]
    return {
        "supported_candidate_fields": supported_candidate,
        "unsupported_candidate_fields": [item["field"] for item in candidate if item["overall_status"] == "unsupported"],
        "provider_error_fields": provider_error,
        "available_control_fields": [item["field"] for item in control if item["overall_status"] == "supported"],
        "control_rows": sum(int(item["rows"]) for item in control),
        "supported_direct_limit_fields": supported_direct_limit,
        "supported_trading_state_fields": supported_trading_state,
        "direct_limit_field_available": bool(supported_direct_limit),
        "trading_state_field_available": bool(supported_trading_state),
    }


def strict_errors(report: dict[str, Any], args: argparse.Namespace) -> list[str]:
    errors = []
    if args.fail_on_provider_error and report["summary"]["provider_error_fields"]:
        fields = ",".join(report["summary"]["provider_error_fields"])
        errors.append(f"provider_error_fields={fields}")
    if args.require_control_rows and int(report["summary"]["control_rows"]) <= 0:
        errors.append("control_rows=0")
    return errors


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(report: dict[str, Any], prefix: str = "OK") -> None:
    data = report["summary"]
    print(
        f"{prefix}: source=baostock probe_type=limit_field_availability "
        f"symbols={len(report['requested_symbols'])} "
        f"supported_candidate_fields={len(data['supported_candidate_fields'])} "
        f"unsupported_candidate_fields={len(data['unsupported_candidate_fields'])} "
        f"supported_direct_limit_fields={len(data['supported_direct_limit_fields'])} "
        f"supported_trading_state_fields={len(data['supported_trading_state_fields'])} "
        f"available_control_fields={len(data['available_control_fields'])} "
        f"provider_error_fields={len(data['provider_error_fields'])} "
        f"control_rows={data['control_rows']} "
        f"direct_limit_field_available={data['direct_limit_field_available']} "
        f"trading_state_field_available={data['trading_state_field_available']} "
        f"limit_rules_model={report['limit_rules_model']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
