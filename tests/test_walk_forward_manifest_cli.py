from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import validate_walk_forward_manifest as manifest_cli  # noqa: E402


class WalkForwardManifestCliTests(unittest.TestCase):
    def test_cli_accepts_offline_manifest_with_expected_overlap_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "run_manifest.json"
            output = Path(tmpdir) / "manifest_report.json"
            write_json(manifest, build_manifest(["2026-05-12"], overlap_code=3))

            code, stdout, stderr = call_cli(manifest, output, ["--expect-portfolio-violations"])
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertIn("OK:", stdout)
        self.assertEqual("", stderr)
        self.assertEqual([], report["errors"])
        self.assertEqual(10, report["steps_checked"])

    def test_cli_rejects_unexpected_step_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "run_manifest.json"
            write_json(manifest, build_manifest(["2026-05-12"], failed_step="2026-05-12:score"))

            code, stdout, stderr = call_cli(manifest, None, ["--expect-portfolio-violations"])

        self.assertEqual(3, code)
        self.assertIn("ERROR_SUMMARY:", stdout)
        self.assertIn("2026-05-12:score_returncode=3", stderr)
        self.assertIn("2026-05-12:score_unexpected_nonzero=3", stderr)

    def test_cli_rejects_missing_gate_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "run_manifest.json"
            data = build_manifest(["2026-05-12"], overlap_code=3)
            score = next(item for item in data["steps"] if item["step"] == "2026-05-12:score")
            score["command"].remove("--fail-on-empty-result")
            write_json(manifest, data)

            code, _stdout, stderr = call_cli(manifest, None, ["--expect-portfolio-violations"])

        self.assertEqual(3, code)
        self.assertIn("2026-05-12:score_missing_--fail-on-empty-result", stderr)

    def test_cli_rejects_missing_steps_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "run_manifest.json"
            data = build_manifest(["2026-05-12"])
            data["steps"] = "bad"
            write_json(manifest, data)

            code, _stdout, stderr = call_cli(manifest, None, ["--expect-portfolio-violations"])

        self.assertEqual(3, code)
        self.assertIn("steps_not_list", stderr)

    def test_cli_checks_expected_max_candidates_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "run_manifest.json"
            output = Path(tmpdir) / "manifest_report.json"
            write_json(manifest, build_manifest(["2026-05-12"], max_candidates=2))

            code, _stdout, stderr = call_cli(
                manifest,
                output,
                ["--expected-max-candidates", "3"],
            )

        self.assertEqual(3, code)
        self.assertIn("manifest_max_candidates=2", stderr)

    def test_cli_accepts_portfolio_allocation_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "run_manifest.json"
            output = Path(tmpdir) / "manifest_report.json"
            write_json(manifest, build_manifest(["2026-05-12"], allocation_model="portfolio_cash_lot_floor"))

            code, stdout, stderr = call_cli(manifest, output, [])
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertIn("OK:", stdout)
        self.assertEqual("", stderr)
        self.assertEqual([], report["errors"])


def call_cli(manifest: Path, output: Path | None, extra: list[str]) -> tuple[int, str, str]:
    args = [
        "--manifest",
        str(manifest),
        "--signal-dates",
        "2026-05-12",
        "--expected-symbol-count",
        "2",
        "--required-tradability-model",
        "tradestatus_entry_exit_only",
        "--required-limit-rules-model",
        "not_modeled",
        *extra,
    ]
    if output:
        args.extend(["--output", str(output)])
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = manifest_cli.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def build_manifest(
    signal_dates: list[str],
    *,
    overlap_code: int = 0,
    failed_step: str = "",
    max_candidates: int | None = None,
    allocation_model: str = "equal_cash_budget_lot_floor",
) -> dict[str, object]:
    steps = [step("fetch", fetch_command())]
    for signal_date in signal_dates:
        steps.extend(signal_steps(signal_date, allocation_model))
    if allocation_model == "portfolio_cash_lot_floor":
        steps.append(step("portfolio_allocate", portfolio_allocate_command()))
        steps.extend(step(f"{signal_date}:backtest", backtest_command()) for signal_date in signal_dates)
    steps.extend(
        [
            step("equity", command("portfolio_equity_curve.py", "--fail-on-incomplete")),
            step("portfolio_overlap", overlap_command(), options=overlap_options(overlap_code)),
            step("summary", summary_command(signal_dates)),
        ]
    )
    for item in steps:
        if item["step"] == failed_step:
            item["returncode"] = 3
    return {
        "schema_version": 1,
        "runner": "run_baostock_walk_forward",
        "source": "baostock",
        "symbols": ["000001", "600000"],
        "signal_dates": signal_dates,
        "tradability_model": "tradestatus_entry_exit_only",
        "limit_rules_model": "not_modeled",
        "max_candidates": max_candidates,
        "allocation_model": allocation_model,
        "steps": steps,
    }


def overlap_options(overlap_code: int) -> dict[str, object]:
    allowed = [0, 3] if overlap_code == 3 else [0]
    return {"code": overlap_code, "allowed": allowed}


def signal_steps(signal_date: str, allocation_model: str) -> list[dict[str, object]]:
    steps = [
        step(f"{signal_date}:slice", command("slice_prices_as_of.py", "--as-of-date", signal_date)),
        step(f"{signal_date}:predict", command("generate_lightgbm_predictions.py", "--summary-output", "--fail-on-skipped")),
        step(f"{signal_date}:validate", command("validate_ohlcv.py", "--config", "qsss_profile_config.json")),
        step(f"{signal_date}:score", command("score_candidates.py", "--fail-on-skipped", "--fail-on-empty-result")),
    ]
    if allocation_model != "portfolio_cash_lot_floor":
        steps.append(step(f"{signal_date}:allocate", command("allocate_candidate_capital.py", "--cash-budget", "1000000", "--lot-size", "100", "--fail-on-unallocated")))
        steps.append(step(f"{signal_date}:backtest", backtest_command()))
    return steps


def fetch_command() -> list[str]:
    return command("fetch_baostock_a_share.py", "--symbols", "000001,600000", "--start-date", "2024-01-01", "--end-date", "2026-05-29", "--metadata-output", "metadata.json", "--adjust", "3", "--fail-on-fetch-error")


def overlap_command() -> list[str]:
    return command("portfolio_overlap_report.py", "--max-open-positions", "10", "--max-gross-weight", "1.0", "--max-gross-notional", "1000000", "--max-cash-reserved", "1000000", "--fail-on-symbol-overlap", "--require-capital-fields")


def portfolio_allocate_command() -> list[str]:
    return command("allocate_portfolio_candidate_capital.py", "--raw-candidates", "raw.csv", "--candidate-outputs", "candidates.csv", "--sized-outputs", "sized.csv", "--skipped-output", "skipped.csv", "--summary-output", "allocation.json", "--max-open-positions", "10", "--max-gross-weight", "1.0", "--max-gross-notional", "1000000", "--max-cash-reserved", "1000000", "--fail-on-symbol-overlap")


def backtest_command() -> list[str]:
    return command("backtest_buy_hold.py", "--require-tradable-bars", "--fail-on-incomplete")


def summary_command(signal_dates: list[str]) -> list[str]:
    return command("summarize_walk_forward_run.py", "--signal-dates", *signal_dates, "--expected-symbol-count", "2", "--required-tradability-model", "tradestatus_entry_exit_only", "--required-limit-rules-model", "not_modeled", "--fail-on-symbol-overlap", "--expect-portfolio-violations")


def command(script: str, *parts: str) -> list[str]:
    return ["python", str(SCRIPTS / script), *parts]


def step(
    name: str,
    cmd: list[str],
    *,
    options: dict[str, object] | None = None,
) -> dict[str, object]:
    data = options or {}
    return {
        "step": name,
        "command": cmd,
        "returncode": data.get("code", 0),
        "allowed_returncodes": data.get("allowed", [0]),
        "stdout": "",
        "stderr": "",
    }


def write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
