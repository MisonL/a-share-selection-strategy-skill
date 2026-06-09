"""Price consistency checks for walk-forward artifacts."""

from __future__ import annotations

from walk_forward_date_checks import normalized_date_text, same_calendar_date


PRICE_TOLERANCE = 1e-9


def signal_price_errors(
    candidates: list[dict[str, str]],
    sized: list[dict[str, str]],
    prices: list[dict[str, str]],
    signal_date: str,
) -> list[str]:
    close_map, errors = signal_close_map(prices, signal_date)
    candidate_keys, candidate_errors = unique_keys(candidates, signal_date, "candidates")
    sized_keys, sized_errors = unique_keys(sized, signal_date, "sized")
    errors.extend(candidate_errors)
    errors.extend(sized_errors)
    if candidate_keys != sized_keys:
        errors.append(f"{signal_date}_candidate_sized_keys_mismatch")
    errors.extend(raw_close_errors(candidates, close_map, signal_date, "candidates", "close"))
    errors.extend(raw_close_errors(sized, close_map, signal_date, "sized", "signal_close"))
    errors.extend(raw_close_errors(sized, close_map, signal_date, "sized", "close"))
    return errors


def signal_close_map(
    rows: list[dict[str, str]],
    signal_date: str,
) -> tuple[dict[tuple[str, str], float], list[str]]:
    values: dict[tuple[str, str], float] = {}
    duplicates: set[str] = set()
    errors = []
    for row in rows:
        if not same_calendar_date(row.get("date", ""), signal_date):
            continue
        symbol = row.get("symbol", "")
        key = (symbol, normalized_date_text(signal_date) or signal_date)
        if key in values:
            duplicates.add(symbol)
            continue
        close = row.get("close", "")
        if not symbol or close == "":
            errors.append(f"{signal_date}_price_signal_close_missing")
            continue
        values[key] = float(close)
    if duplicates:
        errors.append(f"{signal_date}_price_signal_duplicate_symbol={sorted(duplicates)[0]}")
    return values, errors


def unique_keys(
    rows: list[dict[str, str]],
    signal_date: str,
    label: str,
) -> tuple[set[tuple[str, str]], list[str]]:
    keys: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.get("symbol", ""), normalized_date_text(row.get("date", "")) or row.get("date", ""))
        if key in keys:
            duplicates.add(key)
        keys.add(key)
    if duplicates:
        symbol, _date = sorted(duplicates)[0]
        return keys, [f"{signal_date}_{label}_duplicate_symbol={symbol}"]
    return keys, []


def raw_close_errors(
    rows: list[dict[str, str]],
    close_map: dict[tuple[str, str], float],
    signal_date: str,
    label: str,
    field: str,
) -> list[str]:
    errors = []
    for row in rows:
        if field == "close" and field not in row and label == "sized":
            continue
        value = row.get(field, "")
        if value == "":
            errors.append(f"{signal_date}_{label}_missing_{field}")
            continue
        key = (row.get("symbol", ""), normalized_date_text(row.get("date", "")) or row.get("date", ""))
        raw_close = close_map.get(key)
        if raw_close is None:
            errors.append(f"{signal_date}_{label}_missing_raw_close={key[0]}")
        elif abs(float(value) - raw_close) > PRICE_TOLERANCE:
            errors.append(f"{signal_date}_{label}_{field}_raw_mismatch={key[0]}")
    return errors

if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
