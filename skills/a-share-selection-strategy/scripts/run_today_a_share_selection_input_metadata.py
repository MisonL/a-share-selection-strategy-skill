"""Input metadata loading for today's A-share runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


METADATA_KEYS = (
    "source_type",
    "scenario",
    "days",
    "prices",
    "synthetic_prediction_input",
    "synthetic_prediction_proves_real_model",
    "real_market_data",
)


def input_metadata_for_prices(prices_input: str | None) -> dict[str, Any]:
    if not prices_input:
        return {}
    metadata_path = Path(prices_input).parent / "metadata.json"
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"input metadata must be a JSON object: {metadata_path}")
    return {key: data[key] for key in METADATA_KEYS if key in data}


def history_metadata_for_output(output_dir: Path) -> dict[str, Any]:
    metadata_path = output_dir / "history_metadata.json"
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"history metadata must be a JSON object: {metadata_path}")
    source = str(data.get("source", "external_fetch") or "external_fetch")
    return {
        "source_type": "external_fetch",
        "source": source,
        "history_provider": source,
        "real_market_data": True,
        "history_partial_result": history_partial_result(data),
        "history_failed_symbol_count": len(list_value(data, "failed_symbols")),
        "history_empty_symbol_count": len(list_value(data, "empty_symbols")),
        "history_fallback_error_count": len(list_value(data, "fallback_errors")),
        "history_output_written": bool(data.get("output_written", True)),
        "history_metadata_output_written": bool(data.get("metadata_output_written", True)),
    }


def list_value(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key, [])
    return value if isinstance(value, list) else []


def history_partial_result(data: dict[str, Any]) -> bool:
    if data.get("partial_result") is True:
        return True
    if data.get("output_written") is False:
        return True
    if list_value(data, "failed_symbols"):
        return True
    if list_value(data, "empty_symbols"):
        return True
    if list_value(data, "fallback_errors"):
        return True
    requested = list_value(data, "requested_symbols")
    if requested and data.get("symbol_count") is not None:
        return int(data["symbol_count"]) != len(requested)
    return False


def is_synthetic_demo(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("source_type", "")) == "synthetic_demo"
