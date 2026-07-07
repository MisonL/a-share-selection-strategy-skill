from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import probe_baostock_limit_fields as probe  # noqa: E402
from lib.selection_core.a_share_selection_model_contracts import (
    LIMIT_RULES_MODEL_NOT_MODELED,
)  # noqa: E402


class ProbeBaostockLimitFieldsTests(unittest.TestCase):
    def test_parse_fields_rejects_empty_and_base_fields(self) -> None:
        self.assertEqual(
            ["preclose", "up_limit"], probe.parse_fields("preclose,up_limit")
        )
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            probe.parse_fields("")
        with self.assertRaisesRegex(ValueError, "invalid probe fields"):
            probe.parse_fields("date")

    def test_probe_records_roles_and_error_codes(self) -> None:
        args = args_for(candidate_fields="up_limit", control_fields="preclose")
        results = [
            probe.probe_one_field(
                FakeBaostock(),
                args=args,
                field="up_limit",
                symbols=["000001"],
                role="candidate",
            ),
            probe.probe_one_field(
                FakeBaostock(),
                args=args,
                field="preclose",
                symbols=["000001"],
                role="control",
            ),
        ]
        report = probe.build_report(
            args=args,
            symbols=["000001"],
            candidate_fields=["up_limit"],
            control_fields=["preclose"],
            results=results,
        )

        by_field = {item["field"]: item for item in report["field_results"]}
        self.assertEqual(2, report["schema_version"])
        self.assertEqual(
            ["up_limit"], report["summary"]["unsupported_candidate_fields"]
        )
        self.assertEqual(["preclose"], report["summary"]["available_control_fields"])
        self.assertEqual([], report["summary"]["supported_direct_limit_fields"])
        self.assertEqual([], report["summary"]["supported_trading_state_fields"])
        self.assertEqual("10004012", by_field["up_limit"]["error_codes"][0])
        self.assertEqual(2, by_field["preclose"]["rows"])
        self.assertEqual(False, report["rule_inference_performed"])
        self.assertEqual(LIMIT_RULES_MODEL_NOT_MODELED, report["limit_rules_model"])

    def test_cli_allows_unsupported_candidate_fields(self) -> None:
        original_probe = probe.probe_fields
        probe.probe_fields = lambda args: fake_report(args, provider_error=False)
        try:
            code, stdout, stderr, data = call_cli(["--fail-on-provider-error"])
        finally:
            probe.probe_fields = original_probe

        self.assertEqual(0, code)
        self.assertEqual("", stderr)
        self.assertIn("direct_limit_field_available=False", stdout)
        self.assertIn("trading_state_field_available=False", stdout)
        self.assertEqual(["up_limit"], data["summary"]["unsupported_candidate_fields"])

    def test_trading_state_field_does_not_make_direct_limit_available(self) -> None:
        args = args_for(candidate_fields="is_trading", control_fields="preclose")
        results = [
            probe.probe_one_field(
                TradingStateBaostock(),
                args=args,
                field="is_trading",
                symbols=["000001"],
                role="candidate",
            ),
            probe.probe_one_field(
                TradingStateBaostock(),
                args=args,
                field="preclose",
                symbols=["000001"],
                role="control",
            ),
        ]
        report = probe.build_report(
            args=args,
            symbols=["000001"],
            candidate_fields=["is_trading"],
            control_fields=["preclose"],
            results=results,
        )

        self.assertEqual(
            ["is_trading"], report["summary"]["supported_candidate_fields"]
        )
        self.assertEqual([], report["summary"]["supported_direct_limit_fields"])
        self.assertEqual(
            ["is_trading"], report["summary"]["supported_trading_state_fields"]
        )
        self.assertEqual(False, report["summary"]["direct_limit_field_available"])
        self.assertEqual(True, report["summary"]["trading_state_field_available"])

    def test_default_field_set_keeps_limit_rules_not_modeled_without_direct_fields(
        self,
    ) -> None:
        args = args_for(
            candidate_fields=",".join(probe.CANDIDATE_FIELDS),
            control_fields=",".join(probe.CONTROL_FIELDS),
        )
        fake = DefaultFieldSetBaostock()
        results = [
            probe.probe_one_field(
                fake, args=args, field=field, symbols=["000001"], role="candidate"
            )
            for field in probe.CANDIDATE_FIELDS
        ]
        results.extend(
            probe.probe_one_field(
                fake, args=args, field=field, symbols=["000001"], role="control"
            )
            for field in probe.CONTROL_FIELDS
        )
        report = probe.build_report(
            args=args,
            symbols=["000001"],
            candidate_fields=list(probe.CANDIDATE_FIELDS),
            control_fields=list(probe.CONTROL_FIELDS),
            results=results,
        )
        summary = report["summary"]

        self.assertEqual(
            list(probe.CANDIDATE_FIELDS), summary["unsupported_candidate_fields"]
        )
        self.assertEqual([], summary["supported_direct_limit_fields"])
        self.assertEqual(False, summary["direct_limit_field_available"])
        self.assertEqual([], summary["supported_trading_state_fields"])
        self.assertEqual(False, summary["trading_state_field_available"])
        self.assertEqual(LIMIT_RULES_MODEL_NOT_MODELED, report["limit_rules_model"])
        self.assertEqual(False, report["rule_inference_performed"])

    def test_cli_fails_on_provider_error_when_requested(self) -> None:
        original_probe = probe.probe_fields
        probe.probe_fields = lambda args: fake_report(args, provider_error=True)
        try:
            code, _stdout, stderr, data = call_cli(["--fail-on-provider-error"])
        finally:
            probe.probe_fields = original_probe

        self.assertEqual(3, code)
        self.assertIn("provider_error_fields=up_limit", stderr)
        self.assertEqual(["up_limit"], data["summary"]["provider_error_fields"])

    def test_provider_error_is_reported_when_other_symbol_succeeds(self) -> None:
        args = args_for(candidate_fields="up_limit", control_fields="preclose")
        mixed = MixedBaostock()
        result = probe.probe_one_field(
            mixed,
            args=args,
            field="up_limit",
            symbols=["000001", "600000"],
            role="candidate",
        )
        report = probe.build_report(
            args=args,
            symbols=["000001", "600000"],
            candidate_fields=["up_limit"],
            control_fields=[],
            results=[result],
        )

        self.assertEqual("supported", result["overall_status"])
        self.assertEqual(["up_limit"], report["summary"]["provider_error_fields"])


def call_cli(extra: list[str]) -> tuple[int, str, str, dict[str, object]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "probe.json"
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = probe.main(
                [
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2025-08-25",
                    "--end-date",
                    "2025-09-10",
                    "--candidate-fields",
                    "up_limit",
                    "--control-fields",
                    "preclose",
                    "--output",
                    str(output),
                    *extra,
                ]
            )
        data = json.loads(output.read_text(encoding="utf-8"))
    return code, stdout.getvalue(), stderr.getvalue(), data


def fake_report(args: object, *, provider_error: bool) -> dict[str, object]:
    status_code = "999999" if provider_error else "10004012"
    fake = FakeBaostock(error_code=status_code)
    results = [
        probe.probe_one_field(
            fake, args=args, field="up_limit", symbols=["000001"], role="candidate"
        ),
        probe.probe_one_field(
            fake, args=args, field="preclose", symbols=["000001"], role="control"
        ),
    ]
    return probe.build_report(
        args=args,
        symbols=["000001"],
        candidate_fields=["up_limit"],
        control_fields=["preclose"],
        results=results,
    )


class FakeBaostock:
    def __init__(self, error_code: str = "10004012") -> None:
        self.error_code = error_code

    def query_history_k_data_plus(
        self, _code: str, fields: str, **_kwargs: object
    ) -> object:
        field = fields.split(",")[-1]
        if field == "preclose":
            return FakeResult(
                field,
                error_code="0",
                rows=[
                    ["2025-09-01", "sz.000001", "10.0"],
                    ["2025-09-02", "sz.000001", "10.2"],
                ],
            )
        return FakeResult(field, error_code=self.error_code, error_msg="参数错误")


class MixedBaostock:
    def query_history_k_data_plus(
        self, code: str, fields: str, **_kwargs: object
    ) -> object:
        field = fields.split(",")[-1]
        if code == "sz.000001":
            return FakeResult(
                field, error_code="0", rows=[["2025-09-01", code, "10.0"]]
            )
        return FakeResult(field, error_code="999999", error_msg="provider unavailable")


class TradingStateBaostock:
    def query_history_k_data_plus(
        self, code: str, fields: str, **_kwargs: object
    ) -> object:
        field = fields.split(",")[-1]
        if field == "preclose":
            return FakeResult(
                field, error_code="0", rows=[["2025-09-01", code, "10.0"]]
            )
        if field == "is_trading":
            return FakeResult(field, error_code="0", rows=[["2025-09-01", code, "1"]])
        return FakeResult(field, error_code="10004012", error_msg="参数错误")


class DefaultFieldSetBaostock:
    def query_history_k_data_plus(
        self, code: str, fields: str, **_kwargs: object
    ) -> object:
        field = fields.split(",")[-1]
        if field in probe.CONTROL_FIELDS:
            return FakeResult(field, error_code="0", rows=[["2025-09-01", code, "1"]])
        return FakeResult(field, error_code="10004012", error_msg="参数错误")


class FakeResult:
    def __init__(
        self,
        field: str,
        *,
        error_code: str,
        rows: list[list[str]] | None = None,
        error_msg: str = "",
    ) -> None:
        self.fields = ["date", "code", field]
        self.error_code = error_code
        self.error_msg = error_msg
        self.rows = rows or []
        self.index = -1

    def next(self) -> bool:
        self.index += 1
        return self.index < len(self.rows)

    def get_row_data(self) -> list[str]:
        return self.rows[self.index]


def args_for(
    candidate_fields: str = "up_limit", control_fields: str = "preclose"
) -> object:
    class Args:
        symbols = "000001"
        start_date = "2025-08-25"
        end_date = "2025-09-10"
        adjust = "3"
        output = ""

    Args.candidate_fields = candidate_fields
    Args.control_fields = control_fields
    return Args()


if __name__ == "__main__":
    unittest.main()
