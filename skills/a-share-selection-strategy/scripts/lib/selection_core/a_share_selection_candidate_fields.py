"""Candidate gate fields derived from the latest input row."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)


from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

    DataFrame = pd.DataFrame
    Series = pd.Series
else:
    DataFrame = Any
    Series = Any


GATE_COLUMNS = ["amount", "tradestatus", "isST", "one_word_bar"]
EMPTY_FIELD_VALUES = {"", "-", "nan", "none", "unknown", "not_used", "not_verified"}


@dataclass(frozen=True)
class CandidateFieldDefinition:
    key: str
    aliases: tuple[str, ...]
    label_en: str
    label_zh: str


OPTIONAL_CANDIDATE_FIELDS = (
    CandidateFieldDefinition(
        "industry",
        ("spot_industry", "industry", "sector", "sw_industry", "申万行业"),
        "Industry",
        "行业",
    ),
    CandidateFieldDefinition(
        "one_year_pct_chg",
        ("one_year_pct_chg", "pct_chg_1y"),
        "1Y change",
        "近一年涨跌幅",
    ),
    CandidateFieldDefinition(
        "market_cap",
        ("market_cap_billion", "market_cap_cny_billion", "market_cap"),
        "Market cap",
        "市值（亿元）",
    ),
    CandidateFieldDefinition(
        "pe_ttm",
        ("pe_ttm", "peTTM", "pe"),
        "PE TTM",
        "PE（TTM）",
    ),
    CandidateFieldDefinition(
        "pb_lf",
        ("pb_lf", "pbLF", "pb"),
        "PB LF",
        "PB（LF）",
    ),
)
OPTIONAL_CANDIDATE_FIELD_KEYS = tuple(field.key for field in OPTIONAL_CANDIDATE_FIELDS)
OPTIONAL_CANDIDATE_FIELD_ALIASES = {
    field.key: field.aliases for field in OPTIONAL_CANDIDATE_FIELDS
}


def candidate_field_aliases(key: str) -> tuple[str, ...]:
    return OPTIONAL_CANDIDATE_FIELD_ALIASES[key]


def candidate_field_labels(key: str) -> tuple[str, str]:
    for field in OPTIONAL_CANDIDATE_FIELDS:
        if field.key == key:
            return field.label_en, field.label_zh
    return key, key


def candidate_field_value_present(value: Any) -> bool:
    text = str(value).strip().lower() if value is not None else ""
    return text not in EMPTY_FIELD_VALUES


def pandas_module() -> Any:
    import pandas as pd

    return pd


def merge_latest_gate_fields(scored: DataFrame, input_frame: DataFrame) -> DataFrame:
    if scored.empty:
        return scored
    latest = latest_gate_view(input_frame)
    return scored.merge(latest, on="symbol", how="left")


def latest_gate_view(input_frame: DataFrame) -> DataFrame:
    pd = pandas_module()
    latest = input_frame.drop_duplicates(subset=["symbol"], keep="last").copy()
    result = pd.DataFrame({"symbol": latest["symbol"].astype(str)})
    result["amount"] = numeric_column(latest, "amount")
    result["tradestatus"] = text_column(latest, "tradestatus")
    result["isST"] = text_column(latest, "isST")
    result["one_word_bar"] = one_word_bar_values(latest)
    return result.reset_index(drop=True)


def numeric_column(frame: DataFrame, column: str) -> Series:
    pd = pandas_module()
    if column not in frame:
        return pd.Series(float("nan"), index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def text_column(frame: DataFrame, column: str) -> Series:
    pd = pandas_module()
    if column not in frame:
        return pd.Series("", index=frame.index, dtype="object")
    return frame[column].fillna("").astype(str).str.strip()


def one_word_bar_values(frame: DataFrame) -> Series:
    pd = pandas_module()
    price_columns = ["open", "high", "low", "close"]
    if any(column not in frame for column in price_columns):
        return pd.Series(False, index=frame.index, dtype="bool")
    prices = frame[price_columns].apply(pd.to_numeric, errors="coerce")
    return prices.notna().all(axis=1) & prices.eq(prices["open"], axis=0).all(axis=1)


def numeric_value(row: Series, column: str) -> float:
    pd = pandas_module()
    if column not in row:
        return float("nan")
    value = pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0]
    return float(value) if pd.notna(value) else float("nan")


def text_value(row: Series, column: str) -> str:
    pd = pandas_module()
    if column not in row or pd.isna(row[column]):
        return ""
    return str(row[column]).strip()
