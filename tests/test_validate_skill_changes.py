from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import validate_skill_changes


def exemption_record() -> dict[str, str]:
    return {
        "reason": "Cohesive declarative contract.",
        "responsibility": "One stable schema projection.",
        "reassess_when": "the contract changes",
    }


def task_csv_row(task_id: str, status: str) -> str:
    header = "ID,标题,内容,验收标准,审查要求,状态,标签\n" if task_id == "TASK-1" else ""
    return header + f"{task_id},title,content,acceptance,review,{status},priority\n"


class ValidateSkillChangesTests(unittest.TestCase):
    def test_task_tracking_check_accepts_single_in_progress_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks = Path(tmpdir) / "tasks.csv"
            tasks.write_text(
                task_csv_row("TASK-1", "进行中") + task_csv_row("TASK-2", "未开始"),
                encoding="utf-8",
            )

            with patch.object(validate_skill_changes, "TASKS_FILE", tasks):
                validate_skill_changes.check_task_tracking()

    def test_task_tracking_check_rejects_multiple_in_progress_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tasks = Path(tmpdir) / "tasks.csv"
            tasks.write_text(
                task_csv_row("TASK-1", "进行中") + task_csv_row("TASK-2", "进行中"),
                encoding="utf-8",
            )

            with (
                patch.object(validate_skill_changes, "TASKS_FILE", tasks),
                self.assertRaisesRegex(RuntimeError, "at most one in-progress task"),
            ):
                validate_skill_changes.check_task_tracking()

    def test_production_complexity_check_accepts_exact_exemptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts = root / "scripts"
            scripts.mkdir()
            source = "def long_function():\n" + "    value = 1\n" * 80
            source += "\n" * 720
            script = scripts / "large.py"
            script.write_text(source, encoding="utf-8")
            manifest = root / "production_complexity_exemptions.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "claim_boundary": (
                            "production_complexity_exemptions_not_permanent_waivers"
                        ),
                        "thresholds": {
                            "file_lines": 800,
                            "function_non_empty_lines": 80,
                        },
                        "file_exemptions": {
                            "large.py": exemption_record(),
                        },
                        "function_exemptions": {
                            "large.py::long_function": exemption_record(),
                        },
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(validate_skill_changes, "SCRIPTS", scripts),
                patch.object(
                    validate_skill_changes,
                    "PRODUCTION_COMPLEXITY_MANIFEST",
                    manifest,
                ),
            ):
                validate_skill_changes.check_production_complexity()

    def test_production_complexity_check_rejects_stale_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "small.py").write_text("def small():\n    return 1\n", encoding="utf-8")
            manifest = root / "production_complexity_exemptions.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "claim_boundary": (
                            "production_complexity_exemptions_not_permanent_waivers"
                        ),
                        "thresholds": {
                            "file_lines": 800,
                            "function_non_empty_lines": 80,
                        },
                        "file_exemptions": {
                            "small.py": exemption_record(),
                        },
                        "function_exemptions": {},
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(validate_skill_changes, "SCRIPTS", scripts),
                patch.object(
                    validate_skill_changes,
                    "PRODUCTION_COMPLEXITY_MANIFEST",
                    manifest,
                ),
                self.assertRaisesRegex(RuntimeError, "stale file exemptions"),
            ):
                validate_skill_changes.check_production_complexity()

    def test_yaml_manifest_check_uses_current_python_when_pyyaml_is_installed(
        self,
    ) -> None:
        commands: list[list[str]] = []

        with (
            patch.object(
                validate_skill_changes,
                "python_module_available",
                return_value=True,
            ),
            patch.object(
                validate_skill_changes,
                "uv_command",
                side_effect=AssertionError("uv should not be required"),
            ),
            patch.object(
                validate_skill_changes,
                "run_command",
                side_effect=lambda command, env=None: commands.append(command),
            ),
        ):
            validate_skill_changes.check_yaml_agent_manifest()

        self.assertEqual(1, len(commands))
        self.assertEqual([sys.executable, "-c"], commands[0][:2])

    def test_yaml_manifest_check_falls_back_to_uv_when_pyyaml_is_missing(
        self,
    ) -> None:
        commands: list[list[str]] = []

        with (
            patch.object(
                validate_skill_changes,
                "python_module_available",
                return_value=False,
            ),
            patch.object(validate_skill_changes, "uv_command", return_value="uv"),
            patch.object(
                validate_skill_changes,
                "run_command",
                side_effect=lambda command, env=None: commands.append(command),
            ),
        ):
            validate_skill_changes.check_yaml_agent_manifest()

        self.assertEqual(1, len(commands))
        self.assertEqual(["uv", "run", "--with", "pyyaml", "python"], commands[0][:5])

    def test_pycache_check_reports_without_deleting_repository_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            managed_paths = [
                root / "__pycache__",
                root / "skills" / "skill" / "__pycache__",
                root / "tests" / "unit" / "__pycache__",
            ]
            ignored_path = root / ".venv" / "lib" / "__pycache__"
            for path in [*managed_paths, ignored_path]:
                path.mkdir(parents=True)

            with patch.object(validate_skill_changes, "ROOT", root):
                with self.assertRaisesRegex(RuntimeError, "__pycache__ directories found"):
                    validate_skill_changes.check_pycache_absent()

            for path in managed_paths:
                self.assertTrue(path.is_dir())
            self.assertTrue(ignored_path.is_dir())


if __name__ == "__main__":
    unittest.main()
