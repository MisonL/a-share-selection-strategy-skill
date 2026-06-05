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


def is_synthetic_demo(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("source_type", "")) == "synthetic_demo"
