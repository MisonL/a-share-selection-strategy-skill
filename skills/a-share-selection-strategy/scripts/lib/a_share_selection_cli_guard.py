"""Direct-execution guard for non-CLI helper modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path


FALLBACK_CLI_ENTRIES = (
    "validate_ohlcv.py",
    "score_candidates.py",
    "run_today_a_share_selection.py",
    "run_baostock_walk_forward.py",
)


def cli_entries() -> tuple[str, ...]:
    registry = (
        Path(__file__).resolve().parents[2] / "configs" / "script_entrypoints.json"
    )
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
        entries = data.get("entries", {})
        public_entries = sorted(
            script
            for script, metadata in entries.items()
            if isinstance(metadata, dict) and metadata.get("public_entry") is True
        )
    except (OSError, TypeError, ValueError):
        return FALLBACK_CLI_ENTRIES
    return tuple(public_entries) if public_entries else FALLBACK_CLI_ENTRIES


CLI_ENTRIES = cli_entries()


def fail_not_cli(path: str) -> None:
    script = Path(path).name
    entries = ", ".join(CLI_ENTRIES)
    print(
        f"ERROR: {script} is not a CLI entry; use one of: {entries}",
        file=sys.stderr,
    )
    raise SystemExit(2)


if __name__ == "__main__":
    fail_not_cli(__file__)
