"""CLI parser wiring for the local A-share selection runner."""

from __future__ import annotations

import argparse

from run_today_a_share_selection_history import DEFAULT_HISTORY_SYMBOL_LIMIT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=parser_description())
    add_core_options(parser)
    add_spot_options(parser)
    add_history_options(parser)
    add_gate_options(parser)
    add_report_options(parser)
    return parser


def parser_description() -> str:
    return (
        "Run local A-share selection gates. In --mode auto, inputs with "
        "market plus prediction/prediction_score plus turn/turnover use "
        "prediction-derived external-prediction scoring; otherwise the runner "
        "uses the generic low-price profile. This runner never executes LightGBM. "
        "Standard outputs are run_manifest.json, summary.json, report.html, "
        "candidates.csv, diagnostics.csv, and CSV intermediate files; strict "
        "all-Parquet output is not supported by this CLI. "
        "Without --prices-input, explicit history fetch options are required; "
        "landed files and metadata still require validation before any candidate claim."
    )


def add_core_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--prices-input",
        help=(
            "Local CSV or Parquet prices input; runner outputs still include "
            "CSV artifacts."
        ),
    )
    parser.add_argument("--output-dir", required=True, help="Output run directory.")
    parser.add_argument("--mode", choices=["auto", "generic", "prediction"], default="auto")
    parser.add_argument("--config", help="Override scoring config path.")


def add_spot_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spot-input", help="Optional local spot CSV or Parquet file.")
    parser.add_argument(
        "--fetch-spot",
        choices=["eastmoney"],
        help=(
            "Fetch spot snapshot before scoring; snapshot metadata and partial_result "
            "must be disclosed and do not prove full-market coverage."
        ),
    )
    parser.add_argument("--spot-pages", type=positive_int, default=1)
    parser.add_argument(
        "--fail-on-partial-spot",
        action="store_true",
        help="Fail when fetched spot metadata reports partial_result=true.",
    )


def add_history_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--history-source", choices=["akshare", "baostock"])
    parser.add_argument("--symbols", help="Comma-separated six-digit symbols for history fetch.")
    parser.add_argument("--start-date", help="History start date.")
    parser.add_argument("--end-date", help="History end date.")
    parser.add_argument(
        "--derive-symbols-from-spot",
        action="store_true",
        help="Derive history symbols from the local or fetched spot snapshot.",
    )
    parser.add_argument(
        "--max-history-symbols",
        type=positive_int,
        default=DEFAULT_HISTORY_SYMBOL_LIMIT,
    )
    parser.add_argument("--history-adjust", help="Forwarded adjust value for history fetch.")
    parser.add_argument(
        "--allow-partial-history",
        action="store_true",
        help=(
            "Allow history fetches with failed or empty symbols; metadata must be checked "
            "before claiming coverage."
        ),
    )
    parser.add_argument("--drop-invalid-history-rows", action="store_true")
    parser.add_argument("--min-history-rows", type=positive_int, default=120)


def add_gate_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--fail-on-empty-result", action="store_true")
    parser.add_argument("--fail-on-skipped", action="store_true")


def add_report_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-html-report",
        action="store_true",
        help="Skip writing the human-readable report.html file.",
    )
    parser.add_argument(
        "--html-report-language",
        choices=["auto", "zh", "en"],
        default="auto",
        help="Initial report language; auto follows the process locale.",
    )


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
