"""Direct-execution guard for non-CLI helper modules."""

from __future__ import annotations

import sys
from pathlib import Path


CLI_ENTRIES = (
    "validate_ohlcv.py",
    "score_candidates.py",
    "run_today_a_share_selection.py",
    "run_baostock_walk_forward.py",
)


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
