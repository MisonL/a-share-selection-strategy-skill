#!/usr/bin/env python3
"""Score stock candidates from local OHLCV data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


OUTPUT_COLUMNS = [
    "rank", "symbol", "name", "market", "date", "close", "volume", "turn", "amount",
    "tradestatus", "isST", "one_word_bar",
    "requested_as_of_date", "actual_data_date", "as_of_date_observed",
    "spot_price", "spot_pct_chg", "spot_amount", "spot_industry",
    "rsi", "volatility", "macd", "macd_status", "momentum_score", "trend_score",
    "prediction_score", "prediction_source", "prediction_input_source",
    "prediction_model_executed_by_score_script",
    "lightgbm_not_executed_by_this_script",
    "explosion_score", "risk_score", "total_score", "ma15",
    "low_ma15_flag", "explosion_focus_flag", "low_price_explosion_flag",
    "signal_tier", "recommendation", "key_reasons", "risk_notes", "data_window",
]


def build_parser() -> argparse.ArgumentParser:
    description = "Score stock candidates from local CSV or Parquet OHLCV data."
    epilog = (
        "prediction-derived config consumes existing prediction or prediction_score "
        "columns only; prediction_source=external_unverified means separate upstream "
        "audit is required. This script does not train or execute LightGBM. "
        "strict empty results return non-zero when --fail-on-empty-result is set. "
        "--output and --diagnostics-output accept CSV output paths only; "
        ".parquet/.pq output paths fail."
    )
    parser = argparse.ArgumentParser(
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--input", required=True, help="Path to CSV or Parquet file.")
    parser.add_argument("--config", required=True, help="Path to JSON config file.")
    parser.add_argument("--output", required=True, help="Path to output CSV file.")
    parser.add_argument(
        "--fail-on-skipped",
        action="store_true",
        help="Return a non-zero exit code if any symbol is skipped.",
    )
    parser.add_argument(
        "--fail-on-empty-result",
        action="store_true",
        help="Return a non-zero exit code if scoring produces zero candidates.",
    )
    parser.add_argument(
        "--diagnostics-output",
        help="Optional CSV path for scored-symbol threshold diagnostics.",
    )
    parser.add_argument(
        "--spot-input",
        help="Optional CSV or Parquet realtime spot file merged into outputs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_path = Path(args.output)
    diagnostics_path = Path(args.diagnostics_output) if args.diagnostics_output else None
    try:
        reject_parquet_output_suffix(output_path, "candidate output")
        if diagnostics_path is not None:
            reject_parquet_output_suffix(diagnostics_path, "diagnostics output")
        ensure_runtime_dependencies()
        config = load_config(Path(args.config))
        spot = read_table(Path(args.spot_input)) if args.spot_input else None
        candidates, summary = score_candidates(read_table(Path(args.input)), config, spot)
        summary["input"] = Path(args.input).name
        if args.spot_input:
            summary["spot_input"] = Path(args.spot_input).name
        strict_errors = strict_gate_errors(
            summary,
            fail_on_skipped=args.fail_on_skipped,
            fail_on_empty_result=args.fail_on_empty_result,
        )
        if strict_errors:
            remove_stale_outputs(output_path, diagnostics_path)
            print_summary(summary, args.output, prefix="ERROR_SUMMARY")
            print(
                "ERROR: strict gate failed; "
                f"{'; '.join(strict_errors)} output_not_written=true",
                file=sys.stderr,
            )
            return 3
        write_output(candidates, output_path)
        if args.diagnostics_output:
            write_threshold_diagnostics(
                summary.get("threshold_diagnostics", []),
                diagnostics_path,
            )
    except (ImportError, ModuleNotFoundError) as exc:
        remove_stale_outputs(output_path, diagnostics_path)
        print(
            "ERROR: code=dependency_error "
            f"input={Path(args.input).name} output_not_written=true message={exc}",
            file=sys.stderr,
        )
        return 2
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        remove_stale_outputs(output_path, diagnostics_path)
        print(
            "ERROR: code=config_error "
            f"input={Path(args.input).name} output_not_written=true message={exc}",
            file=sys.stderr,
        )
        return 2
    except ValueError as exc:
        remove_stale_outputs(output_path, diagnostics_path)
        print(
            "ERROR: code=bad_input "
            f"input={Path(args.input).name} output_not_written=true message={exc}",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001
        remove_stale_outputs(output_path, diagnostics_path)
        print(
            "ERROR: code=runtime_error "
            f"input={Path(args.input).name} output_not_written=true message={exc}",
            file=sys.stderr,
        )
        return 2
    print_summary(summary, args.output)
    return 0


def ensure_runtime_dependencies() -> None:
    if "pd" in globals():
        return

    import pandas as pandas_module
    import a_share_selection_candidate_fields as gate_fields_module
    import a_share_selection_config as config_module
    import a_share_selection_data as data_module
    import a_share_selection_disclosure as disclosure_module
    import a_share_selection_diagnostics as diagnostics_module
    import a_share_selection_metrics as metrics_module
    import a_share_selection_prepare as prepare_module
    import a_share_selection_profile as profile_module
    import a_share_selection_score_summary as summary_module
    import a_share_selection_spot as spot_module
    import a_share_selection_universe as universe_module
    import validate_ohlcv as validator_module

    globals().update(
        {
            "pd": pandas_module,
            "merge_latest_gate_fields": gate_fields_module.merge_latest_gate_fields,
            "load_config": config_module.load_config,
            "parse_dates": data_module.parse_dates,
            "read_table": data_module.read_table,
            "add_threshold_summary": diagnostics_module.add_threshold_summary,
            "add_prediction_disclosure_fields": (
                disclosure_module.add_prediction_disclosure_fields
            ),
            "build_summary": diagnostics_module.build_summary,
            "complete_summary": diagnostics_module.complete_summary,
            "no_scored_symbols_message": summary_module.no_scored_symbols_message,
            "prepare_input_frame": prepare_module.prepare_frame,
            "print_skipped_history_warning": summary_module.print_skipped_history_warning,
            "print_summary": summary_module.print_summary,
            "strict_gate_errors": diagnostics_module.strict_gate_errors,
            "threshold_masks": diagnostics_module.threshold_masks,
            "threshold_diagnostics": diagnostics_module.threshold_diagnostics,
            "write_threshold_diagnostics": (
                diagnostics_module.write_threshold_diagnostics
            ),
            "is_prediction_mode": metrics_module.is_prediction_mode,
            "score_symbol": metrics_module.score_symbol,
            "profile_column_errors": profile_module.profile_column_errors,
            "prediction_value_errors": profile_module.prediction_value_errors,
            "merge_latest_spot_fields": spot_module.merge_latest_spot_fields,
            "merge_spot_view": spot_module.merge_spot_view,
            "apply_universe_filter": universe_module.apply_universe_filter,
            "validate_frame": validator_module.validate_frame,
        }
    )


def score_candidates(
    frame: pd.DataFrame, config: dict[str, Any], spot: pd.DataFrame | None = None
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensure_runtime_dependencies()
    validate_input_frame(frame, config)
    validate_profile_requirements(frame, config)
    prepared = prepare_input_frame(frame, parse_dates)
    raw_symbols = int(frame["symbol"].astype(str).nunique())
    if prepared.empty and raw_symbols:
        raise ValueError("no valid rows after basic data cleaning")
    validate_prediction_symbols(prepared, config)
    input_frame, universe_summary = apply_universe_filter(prepared, config)
    spot_view, spot_summary = merge_spot_view(input_frame, spot)
    validate_prediction_values(input_frame, config)
    scored_rows, failed_symbols, short_symbols = score_groups(input_frame, config)
    scored = pd.DataFrame(scored_rows)
    summary = build_summary(
        raw=frame,
        prepared=prepared,
        input_frame=input_frame,
        scored=scored,
        failed_symbols=failed_symbols,
        short_symbols=short_symbols,
        config=config,
        universe_summary=universe_summary,
    )
    summary.update(spot_summary)
    if short_symbols:
        min_history = int(config["thresholds"].get("min_history_rows", 120))
        print_skipped_history_warning(short_symbols, min_history)
    if scored.empty:
        return empty_result(summary)
    scored = add_prediction_disclosure_fields(scored, config)
    scored = merge_latest_gate_fields(scored, input_frame)
    scored = merge_latest_spot_fields(scored, spot_view)
    thresholded = apply_thresholds(scored, config["thresholds"])
    summary = add_threshold_summary(
        summary=summary,
        scored=scored,
        thresholded=thresholded,
        config=config,
    )
    ranked = rank_and_limit(thresholded, config)
    summary["threshold_diagnostics"] = threshold_diagnostics(
        scored=scored,
        ranked=ranked,
        config=config,
    )
    return ranked_result(ranked, summary)


def empty_result(
    summary: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if summary["input_symbols"] and (
        summary["failed_symbols"] or summary["insufficient_history_symbols"]
    ):
        raise ValueError(no_scored_symbols_message(summary))
    return pd.DataFrame(columns=OUTPUT_COLUMNS), complete_summary(summary, 0)


def ranked_result(
    ranked: pd.DataFrame,
    summary: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    return ensure_output_columns(ranked), complete_summary(summary, len(ranked))


def score_groups(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    min_history = int(config["thresholds"].get("min_history_rows", 120))
    rows = []
    failed_symbols = []
    short_symbols = []
    for _, group in frame.groupby("symbol", sort=False):
        symbol = str(group["symbol"].iloc[-1])
        if len(group) >= min_history:
            try:
                rows.append(score_symbol(group, config))
            except Exception as exc:  # noqa: BLE001
                failed_symbols.append(symbol)
                print(f"WARNING: skipped symbol {symbol}: {exc}", file=sys.stderr)
        else:
            short_symbols.append(symbol)
    return rows, failed_symbols, short_symbols


def validate_input_frame(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    errors = validate_frame(frame, min_history_rows=0)
    if errors:
        raise ValueError("; ".join(errors))


def validate_prediction_values(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    if not is_prediction_mode(config):
        return
    for column in ["prediction", "prediction_score"]:
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        missing = int(values.isna().sum())
        invalid = int(((values < 0) | (values > 1)).sum())
        invalid_count = missing + invalid
        if invalid_count:
            raise ValueError(
                f"{column} has {invalid_count} invalid values; "
                "prediction values must be numbers between 0 and 1"
            )


def validate_profile_requirements(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    errors = profile_column_errors(frame, config)
    if errors:
        raise ValueError("; ".join(errors))


def validate_prediction_symbols(frame: pd.DataFrame, config: dict[str, Any]) -> None:
    errors = prediction_value_errors(frame, config)
    if errors:
        raise ValueError("; ".join(errors))


def rank_and_limit(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    ranked = frame.copy()
    sort_columns = ["total_score"]
    ascending = [False]
    if not is_prediction_mode(config):
        sort_columns.extend(["explosion_score", "momentum_score"])
        ascending.extend([False, False])
    ranked = ranked.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)
    max_candidates = int(config.get("output", {}).get("max_candidates", 50))
    if max_candidates > 0:
        ranked = ranked.head(max_candidates)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked


def apply_thresholds(frame: pd.DataFrame, thresholds: dict[str, Any]) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for threshold_mask in threshold_masks(frame, thresholds).values():
        mask &= threshold_mask
    return frame[mask].copy()


def ensure_output_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in OUTPUT_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[OUTPUT_COLUMNS]


def write_output(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def reject_parquet_output_suffix(path: Path, label: str) -> None:
    if path.suffix.lower() in {".parquet", ".pq"}:
        raise ValueError(f"{label} supports CSV only; parquet output is not supported")


def remove_stale_outputs(*paths: Path | None) -> None:
    for path in paths:
        if path is None:
            continue
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
