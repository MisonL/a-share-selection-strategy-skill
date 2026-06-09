"""Input metadata loading for today's A-share runner."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


METADATA_KEYS = (
    "source_type",
    "source",
    "scenario",
    "days",
    "prices",
    "market",
    "market_label_only",
    "source_claim_boundary",
    "adjustment",
    "requested_symbols",
    "symbol_count",
    "rows",
    "failed_symbols",
    "empty_symbols",
    "output_written",
    "metadata_output_written",
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
    metadata = {key: data[key] for key in METADATA_KEYS if key in data}
    if local_input_partial_result(data):
        metadata["input_partial_result"] = True
    if "failed_symbols" in data:
        metadata["input_failed_symbol_count"] = len(list_value(data, "failed_symbols"))
    if "empty_symbols" in data:
        metadata["input_empty_symbol_count"] = len(list_value(data, "empty_symbols"))
    if "requested_symbols" in data:
        metadata["input_requested_symbol_count"] = len(list_value(data, "requested_symbols"))
    return metadata


def history_metadata_for_output(output_dir: Path) -> dict[str, Any]:
    metadata_path = output_dir / "history_metadata.json"
    if not metadata_path.is_file():
        return {}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"history metadata must be a JSON object: {metadata_path}")
    source = str(data.get("source", "external_fetch") or "external_fetch")
    metadata = {
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
    if "adjust" in data:
        metadata["history_adjust"] = data["adjust"]
    if "adjustflag" in data:
        metadata["history_adjustflag"] = str(data["adjustflag"])
    return metadata


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


def local_input_partial_result(data: dict[str, Any]) -> bool:
    if data.get("partial_result") is True:
        return True
    if data.get("output_written") is False:
        return True
    if list_value(data, "failed_symbols"):
        return True
    if list_value(data, "empty_symbols"):
        return True
    requested = list_value(data, "requested_symbols")
    if requested and data.get("symbol_count") is not None:
        return int(data["symbol_count"]) != len(requested)
    return False


def is_synthetic_demo(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("source_type", "")) == "synthetic_demo"

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
