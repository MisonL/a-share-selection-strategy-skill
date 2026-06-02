"""Mode resolution helpers for the local A-share selection runner."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModeResolution:
    mode: str
    decision: str
    reason: str


def resolve_mode(args: Any) -> ModeResolution:
    if args.mode != "auto":
        validate_explicit_config_mode(args)
        return ModeResolution(args.mode, "explicit", f"user_requested_{args.mode}")
    if args.config:
        return resolve_config_mode(Path(args.config))
    if not args.prices_input:
        return ModeResolution(
            "generic",
            "auto_generic",
            "history_fetch_inputs_do_not_include_prediction",
        )
    missing = missing_qsss_column_groups(input_columns(Path(args.prices_input)))
    if missing:
        reason = "missing_qsss_columns:" + ",".join(missing)
        return ModeResolution("generic", "auto_generic", reason)
    return ModeResolution("qsss", "auto_qsss", "qsss_required_columns_present")


def resolve_config_mode(path: Path) -> ModeResolution:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config_mode(config) == "qsss":
        return ModeResolution(
            "qsss",
            "auto_qsss_config",
            "config_score_mode_qsss-derived",
        )
    return ModeResolution("generic", "auto_generic_config", "config_not_qsss-derived")


def validate_explicit_config_mode(args: Any) -> None:
    if not args.config:
        return
    resolved = config_mode(json.loads(Path(args.config).read_text(encoding="utf-8")))
    if resolved != args.mode:
        raise ValueError(
            "explicit mode conflicts with config score_mode: "
            f"mode={args.mode} config_mode={resolved}"
        )


def config_mode(config: dict) -> str:
    return "qsss" if config.get("score_mode") == "qsss-derived" else "generic"


def input_columns(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"prices input not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            return set(next(csv.reader(handle), []))
    if suffix in {".parquet", ".pq"}:
        return parquet_columns(path)
    raise ValueError("unsupported input format; use .csv, .parquet, or .pq")


def parquet_columns(path: Path) -> set[str]:
    try:
        import pyarrow.parquet as pq
    except Exception:  # noqa: BLE001
        import pandas as pd

        return set(pd.read_parquet(path).columns)
    return set(pq.ParquetFile(path).schema_arrow.names)


def missing_qsss_column_groups(columns: set[str]) -> list[str]:
    required = {
        "market": {"market"},
        "prediction": {"prediction", "prediction_score"},
        "turnover": {"turn", "turnover"},
    }
    return [name for name, choices in required.items() if not columns & choices]
