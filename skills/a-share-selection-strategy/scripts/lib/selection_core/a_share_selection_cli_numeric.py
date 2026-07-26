"""Small argparse adapters for numeric fail-closed CLI contracts."""

from __future__ import annotations

import math
import sys
from collections.abc import Iterable, Sequence


NEGATIVE_NON_FINITE_LITERALS = frozenset({"-nan", "-inf", "-infinity"})


def normalize_negative_non_finite_option_values(
    argv: Sequence[str] | None,
    option_names: Iterable[str],
) -> list[str]:
    """Make negative non-finite literals visible to argparse as option values."""
    if argv is None:
        argv = sys.argv[1:]
    known_options = frozenset(option_names)
    normalized: list[str] = []
    index = 0
    while index < len(argv):
        current = argv[index]
        if (
            current in known_options
            and index + 1 < len(argv)
            and is_negative_non_finite_literal(argv[index + 1])
        ):
            normalized.append(f"{current}={argv[index + 1]}")
            index += 2
            continue
        normalized.append(current)
        index += 1
    return normalized


def is_negative_non_finite_literal(value: str) -> bool:
    return value.lower() in NEGATIVE_NON_FINITE_LITERALS


def integer_or_non_finite(value: str) -> int | float:
    """Keep integer parsing strict while passing non-finite values to validators."""
    try:
        return int(value)
    except ValueError:
        try:
            numeric = float(value)
        except ValueError as exc:
            raise ValueError("value must be an integer") from exc
        if not math.isfinite(numeric):
            return numeric
        raise ValueError("value must be an integer")
