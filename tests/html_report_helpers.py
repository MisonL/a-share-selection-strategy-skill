from __future__ import annotations

from contextlib import nullcontext, redirect_stderr, redirect_stdout
from io import StringIO
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import run_today_a_share_selection as runner
from helpers import build_frame


class ReportRun:
    def __init__(
        self,
        extra_args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.extra_args = extra_args or []
        self.env = env
        self.tempdir = tempfile.TemporaryDirectory()
        self.output = Path(self.tempdir.name) / "run"
        self.code = -1
        self.stdout = ""
        self.stderr = ""

    def __enter__(self) -> ReportRun:
        prices = Path(self.tempdir.name) / "input.csv"
        frame = build_frame(include_turn=True, include_tradability=True)
        frame[["open", "high", "low", "close"]] = frame[
            ["open", "high", "low", "close"]
        ] * 0.75
        frame.to_csv(prices, index=False)
        args = ["--prices-input", str(prices), "--output-dir", str(self.output)]
        args.extend(self.extra_args)
        self.code, self.stdout, self.stderr = call_runner(args, self.env)
        return self

    def __exit__(self, *_args: object) -> None:
        self.tempdir.cleanup()


def report_run(
    extra_args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> ReportRun:
    return ReportRun(extra_args=extra_args, env=env)


def call_runner(args: list[str], env: dict[str, str] | None) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    context = patch.dict("os.environ", env, clear=False) if env else nullcontext()
    with context, redirect_stdout(stdout), redirect_stderr(stderr):
        code = runner.main(args)
    return code, stdout.getvalue(), stderr.getvalue()


def read_summary(output: Path) -> dict[str, object]:
    return json.loads((output / "summary.json").read_text(encoding="utf-8"))


def read_report(output: Path) -> str:
    return (output / "report.html").read_text(encoding="utf-8")


def minimal_summary(tmpdir: str, diagnostics: Path) -> dict[str, object]:
    output = Path(tmpdir)
    return {
        "status": "completed",
        "prediction_mode": False,
        "requested_mode": "auto",
        "mode_decision": "auto_generic",
        "mode_decision_reason": "missing_prediction_columns:prediction",
        "prediction_input_source": "not_used",
        "prediction_model_executed_by_runner": False,
        "source_scope": "local_prices_input",
        "candidate_rows": 0,
        "diagnostic_rows": 1,
        "failed_steps": [],
        "html_report": str(output / "report.html"),
        "diagnostics_output": str(diagnostics),
        "diagnostics_output_written": diagnostics.exists(),
        "candidates_output": str(output / "candidates.csv"),
        "candidates_output_written": (output / "candidates.csv").exists(),
        "prices_output": str(output / "prices.csv"),
        "prices_output_written": (output / "prices.csv").exists(),
        "boundary": "",
    }
