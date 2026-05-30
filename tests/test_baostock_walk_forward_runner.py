from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_baostock_walk_forward as runner  # noqa: E402


class BaostockWalkForwardRunnerTests(unittest.TestCase):
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
        self.assertIn("not_modeled", summary_command)

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
        self.assertIn("--fail-on-incomplete", commands["2026-05-12:backtest"])
        self.assertIn("--require-capital-fields", commands["portfolio_overlap"])
        self.assertIn("--fail-on-symbol-overlap", commands["portfolio_overlap"])


class FakeExecutor:
    def __init__(self, returncodes: dict[str, int]) -> None:
        self.returncodes = returncodes
        self.calls: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(command)
        step = infer_step(command)
        code = self.returncodes.get(step, 0)
        return subprocess.CompletedProcess(command, code, stdout=f"{step} stdout", stderr=f"{step} stderr")


def infer_step(command: list[str]) -> str:
    script = Path(command[1]).name
    if script == "fetch_baostock_a_share.py":
        return "fetch"
    if script == "portfolio_equity_curve.py":
        return "equity"
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


def args_for(output_dir: Path, *, signal_dates: list[str]) -> object:
    parser = runner.build_parser()
    return parser.parse_args(
        [
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
    )


if __name__ == "__main__":
    unittest.main()
