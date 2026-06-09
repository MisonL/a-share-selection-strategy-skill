from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_baostock_walk_forward as runner  # noqa: E402
from a_share_selection_model_contracts import (  # noqa: E402
    LIMIT_RULES_MODEL_NOT_MODELED,
    TRADABILITY_MODEL_HOLDING_PERIOD,
)


class BaostockWalkForwardRunnerTests(unittest.TestCase):
    def test_cli_offline_plan_writes_manifest_without_executing_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = runner.main(
                    [
                        "--symbols",
                        "000001,600000",
                        "--start-date",
                        "2024-01-01",
                        "--end-date",
                        "2026-05-29",
                        "--signal-dates",
                        "2026-05-12",
                        "--output-dir",
                        str(output),
                        "--cash-budget",
                        "1000000",
                        "--max-open-positions",
                        "10",
                        "--max-gross-weight",
                        "1.0",
                        "--max-gross-notional",
                        "1000000",
                        "--max-cash-reserved",
                        "1000000",
                        "--offline-plan",
                    ]
                )
            data = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        first_line = stdout.getvalue().splitlines()[0]
        self.assertTrue(first_line.startswith("PLAN: "), first_line)
        self.assertIn("execution_mode=offline_plan", first_line)
        self.assertIn("commands_executed=false", first_line)
        self.assertIn("verdict=offline_plan_not_executed", first_line)
        self.assertIn(
            "claim_boundary=offline_plan_manifest_only_not_real_market_prediction_or_backtest",
            first_line,
        )
        self.assertEqual("offline_plan", data["execution_mode"])
        self.assertFalse(data["commands_executed"])
        self.assertFalse(data["real_market_data_executed"])
        self.assertFalse(data["prediction_model_executed"])
        self.assertFalse(data["backtest_executed"])
        self.assertEqual(
            "offline_plan_manifest_only_not_real_market_prediction_or_backtest",
            data["claim_boundary"],
        )
        self.assertEqual(
            [
                "fetch",
                "2026-05-12:slice",
                "2026-05-12:predict",
                "2026-05-12:validate",
                "2026-05-12:score",
                "2026-05-12:allocate",
                "2026-05-12:backtest",
                "equity",
                "portfolio_overlap",
                "summary",
            ],
            [item["step"] for item in data["steps"]],
        )
        self.assertTrue(all(item["planned_only"] for item in data["steps"]))
        self.assertTrue(all(item["returncode"] is None for item in data["steps"]))

    def test_cli_offline_plan_writes_run_scoped_max_candidates_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            code = runner.main(
                [
                    "--symbols",
                    "000001,600000",
                    "--start-date",
                    "2024-01-01",
                    "--end-date",
                    "2026-05-29",
                    "--signal-dates",
                    "2026-05-12",
                    "--output-dir",
                    str(output),
                    "--cash-budget",
                    "1000000",
                    "--max-open-positions",
                    "10",
                    "--max-gross-weight",
                    "1.0",
                    "--max-gross-notional",
                    "1000000",
                    "--max-cash-reserved",
                    "1000000",
                    "--max-candidates",
                    "2",
                    "--offline-plan",
                ]
            )
            manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            config_path = output / "prediction_profile_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            commands = {item["step"]: item["command"] for item in manifest["steps"]}

        self.assertEqual(0, code)
        self.assertEqual(str(config_path), manifest["config_path"])
        self.assertEqual(2, config["output"]["max_candidates"])
        self.assertIn(str(config_path), commands["2026-05-12:validate"])
        self.assertIn(str(config_path), commands["2026-05-12:score"])

    def test_offline_plan_records_all_steps_and_keeps_overlap_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = args_for(Path(tmpdir), signal_dates=["2026-05-12", "2026-05-20"])
            executor = FakeExecutor({"portfolio_overlap": 3})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=Path(tmpdir) / "run_manifest.json",
                executor=executor,
            )

            runner.run_pipeline(context)
            data = json.loads(context.manifest_path.read_text(encoding="utf-8"))

        steps = [item["step"] for item in data["steps"]]
        self.assertEqual(
            [
                "fetch",
                "2026-05-12:slice",
                "2026-05-12:predict",
                "2026-05-12:validate",
                "2026-05-12:score",
                "2026-05-12:allocate",
                "2026-05-12:backtest",
                "2026-05-20:slice",
                "2026-05-20:predict",
                "2026-05-20:validate",
                "2026-05-20:score",
                "2026-05-20:allocate",
                "2026-05-20:backtest",
                "equity",
                "portfolio_overlap",
                "summary",
            ],
            steps,
        )
        overlap = data["steps"][-2]
        self.assertEqual(3, overlap["returncode"])
        self.assertEqual([0, 3], overlap["allowed_returncodes"])
        summary_command = data["steps"][-1]["command"]
        self.assertIn("--expect-portfolio-violations", summary_command)
        self.assertIn("--required-limit-rules-model", summary_command)
        self.assertIn(LIMIT_RULES_MODEL_NOT_MODELED, summary_command)

    def test_offline_plan_fails_fast_and_records_failed_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = args_for(Path(tmpdir), signal_dates=["2026-05-12"])
            executor = FakeExecutor({"2026-05-12:score": 3})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=Path(tmpdir) / "run_manifest.json",
                executor=executor,
            )

            with self.assertRaises(runner.StepFailure) as raised:
                runner.run_pipeline(context)
            data = json.loads(context.manifest_path.read_text(encoding="utf-8"))

        self.assertEqual("2026-05-12:score", raised.exception.step)
        self.assertEqual(["fetch", "2026-05-12:slice", "2026-05-12:predict", "2026-05-12:validate", "2026-05-12:score"], [item["step"] for item in data["steps"]])
        self.assertEqual(3, data["steps"][-1]["returncode"])

    def test_commands_include_current_p1_gate_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = args_for(Path(tmpdir), signal_dates=["2026-05-12"])
            executor = FakeExecutor({})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=Path(tmpdir) / "run_manifest.json",
                executor=executor,
            )

            runner.run_pipeline(context)
            commands = {item["step"]: item["command"] for item in manifest["steps"]}

        self.assertIn("--fail-on-fetch-error", commands["fetch"])
        self.assertIn("--fail-on-skipped", commands["2026-05-12:predict"])
        self.assertIn("--fail-on-empty-result", commands["2026-05-12:score"])
        self.assertIn("--fail-on-unallocated", commands["2026-05-12:allocate"])
        self.assertIn("--require-tradable-bars", commands["2026-05-12:backtest"])
        self.assertIn("--expected-signal-date", commands["2026-05-12:backtest"])
        self.assertIn("2026-05-12", commands["2026-05-12:backtest"])
        self.assertNotIn("--require-tradable-holding-period", commands["2026-05-12:backtest"])
        self.assertIn("--fail-on-incomplete", commands["2026-05-12:backtest"])
        self.assertIn("--require-capital-fields", commands["portfolio_overlap"])
        self.assertIn("--fail-on-symbol-overlap", commands["portfolio_overlap"])

    def test_run_promotes_summary_verdict_to_manifest_and_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output, signal_dates=["2026-05-12"])
            executor = FakeExecutor({})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=output / "run_manifest.json",
                executor=executor,
            )
            stdout = StringIO()

            runner.run_pipeline(context)
            with redirect_stdout(stdout):
                runner.print_summary(manifest, context.manifest_path)
            data = json.loads(context.manifest_path.read_text(encoding="utf-8"))

        line = stdout.getvalue()
        self.assertEqual("enabled_gates_passed_not_external_proof", data["verdict"])
        self.assertTrue(data["capacity_gate_pass"])
        self.assertEqual("pass", data["capacity_gate_status"])
        self.assertEqual("summary_not_external_gate", data["claim_boundary"])
        self.assertIn("verdict=enabled_gates_passed_not_external_proof", line)
        self.assertIn("capacity_gate_pass=True", line)
        self.assertIn("capacity_gate_status=pass", line)
        self.assertIn("claim_boundary=summary_not_external_gate", line)

    def test_can_request_holding_period_tradability_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = args_for(
                Path(tmpdir),
                signal_dates=["2026-05-12"],
                require_tradable_holding_period=True,
            )
            executor = FakeExecutor({})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=Path(tmpdir) / "run_manifest.json",
                executor=executor,
            )

            runner.run_pipeline(context)
            commands = {item["step"]: item["command"] for item in manifest["steps"]}

        self.assertEqual(TRADABILITY_MODEL_HOLDING_PERIOD, manifest["tradability_model"])
        self.assertIn("--require-tradable-holding-period", commands["2026-05-12:backtest"])
        self.assertIn(TRADABILITY_MODEL_HOLDING_PERIOD, commands["summary"])

    def test_drop_invalid_rows_marks_summary_allowance_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = args_for(Path(tmpdir), signal_dates=["2026-05-12"], drop_invalid_rows=True)
            executor = FakeExecutor({})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=Path(tmpdir) / "run_manifest.json",
                executor=executor,
            )

            runner.run_pipeline(context)
            commands = {item["step"]: item["command"] for item in manifest["steps"]}

        self.assertIn("--drop-invalid-rows", commands["fetch"])
        self.assertIn("--allow-dropped-invalid-rows", commands["summary"])

    def test_max_candidates_writes_run_scoped_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output, signal_dates=["2026-05-12"], max_candidates=2)
            executor = FakeExecutor({})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=output / "run_manifest.json",
                executor=executor,
            )

            runner.run_pipeline(context)
            config_path = output / "prediction_profile_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            commands = {item["step"]: item["command"] for item in manifest["steps"]}

        self.assertEqual(2, config["output"]["max_candidates"])
        self.assertEqual(str(config_path), manifest["config_path"])
        self.assertEqual(2, manifest["max_candidates"])
        self.assertIn(str(config_path), commands["2026-05-12:validate"])
        self.assertIn(str(config_path), commands["2026-05-12:score"])

    def test_portfolio_allocation_model_runs_global_allocate_before_backtests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            args = args_for(
                Path(tmpdir),
                signal_dates=["2026-05-12", "2026-05-20"],
                allocation_model="portfolio_cash_lot_floor",
            )
            executor = FakeExecutor({})
            manifest = runner.initial_manifest(args)
            context = runner.RunContext(
                args=args,
                manifest=manifest,
                manifest_path=Path(tmpdir) / "run_manifest.json",
                executor=executor,
            )

            runner.run_pipeline(context)
            steps = [item["step"] for item in manifest["steps"]]
            commands = {item["step"]: item["command"] for item in manifest["steps"]}

        self.assertNotIn("2026-05-12:allocate", steps)
        self.assertLess(steps.index("portfolio_allocate"), steps.index("2026-05-12:backtest"))
        self.assertLess(steps.index("portfolio_allocate"), steps.index("2026-05-20:backtest"))
        self.assertIn("allocate_portfolio_candidate_capital.py", commands["portfolio_allocate"][1])
        self.assertIn("--expected-signal-dates", commands["portfolio_allocate"])
        self.assertIn("2026-05-12", commands["portfolio_allocate"])
        self.assertIn("2026-05-20", commands["portfolio_allocate"])
        self.assertIn("prediction_raw_candidates.csv", " ".join(commands["2026-05-12:score"]))
        self.assertEqual("portfolio_cash_lot_floor", manifest["allocation_model"])


class FakeExecutor:
    def __init__(self, returncodes: dict[str, int]) -> None:
        self.returncodes = returncodes
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        step = infer_step(command)
        code = self.returncodes.get(step, 0)
        if step == "summary" and code == 0:
            write_fake_run_summary(command)
        return subprocess.CompletedProcess(command, code, stdout=f"{step} stdout", stderr=f"{step} stderr")


def infer_step(command: list[str]) -> str:
    script = Path(command[1]).name
    if script == "fetch_baostock_a_share.py":
        return "fetch"
    if script == "portfolio_equity_curve.py":
        return "equity"
    if script == "allocate_portfolio_candidate_capital.py":
        return "portfolio_allocate"
    if script == "portfolio_overlap_report.py":
        return "portfolio_overlap"
    if script == "summarize_walk_forward_run.py":
        return "summary"
    signal = signal_from_command(command)
    suffix = {
        "slice_prices_as_of.py": "slice",
        "generate_lightgbm_predictions.py": "predict",
        "validate_ohlcv.py": "validate",
        "score_candidates.py": "score",
        "allocate_candidate_capital.py": "allocate",
        "backtest_buy_hold.py": "backtest",
    }[script]
    return f"{signal}:{suffix}"


def signal_from_command(command: list[str]) -> str:
    for part in command:
        path = Path(part)
        if path.parent.name.startswith("2026-"):
            return path.parent.name
        if path.name.startswith("2026-"):
            return path.name
    raise AssertionError(f"cannot infer signal from command: {command}")


def write_fake_run_summary(command: list[str]) -> None:
    output = Path(command[command.index("--output") + 1])
    output.write_text(
        json.dumps(
            {
                "capacity_gate_pass": True,
                "capacity_gate_status": "pass",
                "verdict": "enabled_gates_passed_not_external_proof",
                "claim_boundary": "summary_not_external_gate",
            }
        ),
        encoding="utf-8",
    )


def args_for(
    output_dir: Path,
    *,
    signal_dates: list[str],
    drop_invalid_rows: bool = False,
    max_candidates: int | None = None,
    allocation_model: str | None = None,
    require_tradable_holding_period: bool = False,
) -> object:
    parser = runner.build_parser()
    args = [
        "--symbols",
        "000001,600000",
        "--start-date",
        "2024-01-01",
        "--end-date",
        "2026-05-29",
        "--signal-dates",
        *signal_dates,
        "--output-dir",
        str(output_dir),
        "--cash-budget",
        "1000000",
        "--max-open-positions",
        "10",
        "--max-gross-weight",
        "1.0",
        "--max-gross-notional",
        "1000000",
        "--max-cash-reserved",
        "1000000",
        "--fail-on-symbol-overlap",
        "--expect-portfolio-violations",
    ]
    if max_candidates is not None:
        args.extend(["--max-candidates", str(max_candidates)])
    if allocation_model is not None:
        args.extend(["--allocation-model", allocation_model])
    if require_tradable_holding_period:
        args.append("--require-tradable-holding-period")
    if drop_invalid_rows:
        args.append("--drop-invalid-rows")
    return parser.parse_args(args)


if __name__ == "__main__":
    unittest.main()
