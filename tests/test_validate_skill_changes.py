from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, call, patch

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
    def test_skill_frontmatter_contract_accepts_supported_fields(self) -> None:
        validate_skill_changes.validate_skill_frontmatter_data(
            {
                "name": "a-share-selection-strategy",
                "description": "Select and validate A-share candidates.",
                "license": "MIT",
                "allowed-tools": "Bash",
                "metadata": {"category": "finance"},
            },
            source="SKILL.md",
        )

    def test_skill_frontmatter_contract_rejects_non_mapping_root(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "expected mapping root"):
            validate_skill_changes.validate_skill_frontmatter_data(
                ["name", "description"],
                source="SKILL.md",
            )

    def test_skill_frontmatter_contract_rejects_unknown_fields(self) -> None:
        with self.assertRaisesRegex(RuntimeError, r"unexpected fields: \['version'\]"):
            validate_skill_changes.validate_skill_frontmatter_data(
                {
                    "name": "a-share-selection-strategy",
                    "description": "Select A-share candidates.",
                    "version": "1",
                },
                source="SKILL.md",
            )

    def test_skill_frontmatter_contract_reports_non_string_unknown_fields(
        self,
    ) -> None:
        with self.assertRaisesRegex(RuntimeError, "unexpected fields"):
            validate_skill_changes.validate_skill_frontmatter_data(
                {
                    "name": "a-share-selection-strategy",
                    "description": "Select A-share candidates.",
                    1: "invalid",
                    "version": "1",
                },
                source="SKILL.md",
            )

    def test_skill_frontmatter_contract_requires_name_and_description(self) -> None:
        for missing in ["name", "description"]:
            data = {
                "name": "a-share-selection-strategy",
                "description": "Select A-share candidates.",
            }
            del data[missing]
            with (
                self.subTest(missing=missing),
                self.assertRaisesRegex(RuntimeError, f"missing {missing}"),
            ):
                validate_skill_changes.validate_skill_frontmatter_data(
                    data,
                    source="SKILL.md",
                )

    def test_skill_frontmatter_contract_rejects_invalid_names(self) -> None:
        invalid_names = [
            (1, "name must be a string"),
            ("", "name must not be empty"),
            (" a-share", "name must not have surrounding whitespace"),
            (
                "a" * 65,
                "name exceeds 64 characters",
            ),
            (
                "A-share",
                "name must use lowercase letters, digits, and single hyphens",
            ),
            (
                "a_share",
                "name must use lowercase letters, digits, and single hyphens",
            ),
            (
                "-a-share",
                "name must use lowercase letters, digits, and single hyphens",
            ),
            (
                "a-share-",
                "name must use lowercase letters, digits, and single hyphens",
            ),
            (
                "a--share",
                "name must use lowercase letters, digits, and single hyphens",
            ),
        ]
        for name, message in invalid_names:
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(RuntimeError, message),
            ):
                validate_skill_changes.validate_skill_frontmatter_data(
                    {"name": name, "description": "Select A-share candidates."},
                    source="SKILL.md",
                )

    def test_skill_frontmatter_contract_rejects_invalid_descriptions(self) -> None:
        invalid_descriptions = [
            (1, "description must be a string"),
            (" ", "description must not be empty"),
            ("Use <private> data.", "description must not contain angle brackets"),
            (
                "x" * 1025,
                "description exceeds 1024 characters",
            ),
        ]
        for description, message in invalid_descriptions:
            with (
                self.subTest(description=description),
                self.assertRaisesRegex(RuntimeError, message),
            ):
                validate_skill_changes.validate_skill_frontmatter_data(
                    {
                        "name": "a-share-selection-strategy",
                        "description": description,
                    },
                    source="SKILL.md",
                )

    def test_skill_frontmatter_extraction_requires_opening_and_closing_delimiters(
        self,
    ) -> None:
        self.assertEqual(
            "name: example\ndescription: Example skill.\n",
            validate_skill_changes.extract_skill_frontmatter(
                "---\nname: example\ndescription: Example skill.\n---\n# Body\n",
                source="SKILL.md",
            ),
        )
        for text in [
            "name: example\ndescription: Example skill.\n",
            "---\nname: example\ndescription: Example skill.\n",
        ]:
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(RuntimeError, "frontmatter delimiters"),
            ):
                validate_skill_changes.extract_skill_frontmatter(
                    text,
                    source="SKILL.md",
                )

    def test_repo_frontmatter_gate_is_not_skipped_with_external_validator(
        self,
    ) -> None:
        args = validate_skill_changes.build_parser().parse_args(
            ["--skip-skill-validate", "--skip-tests"]
        )

        names = [check.name for check in validate_skill_changes.build_checks(args)]

        self.assertIn("Skill frontmatter contract", names)
        self.assertNotIn("skill quick_validate", names)

    def test_unittest_command_latest_profile_keeps_compatibility_path(self) -> None:
        with patch.object(validate_skill_changes, "uv_command", return_value="uv"):
            command = validate_skill_changes.unittest_command("latest")
        self.assertEqual(
            [
                "uv",
                "run",
                "--with",
                "pandas",
                "--with",
                "numpy",
                "--with",
                "pyarrow",
            ],
            command[:8],
        )
        self.assertEqual(["python", "-m", "unittest"], command[8:11])

    def test_unittest_command_ci_profile_uses_exact_python_constraints(self) -> None:
        with patch.object(validate_skill_changes, "uv_command", return_value="uv"):
            command = validate_skill_changes.unittest_command("ci")
        self.assertEqual(
            [
                "uv",
                "run",
                "--python",
                "3.11",
                "--with-requirements",
                "skills/a-share-selection-strategy/constraints-ci.txt",
            ],
            command[:6],
        )
        self.assertEqual(["python", "-m", "unittest"], command[6:9])

    def test_unittest_command_rejects_unknown_dependency_profile(self) -> None:
        with (
            patch.object(
                validate_skill_changes,
                "uv_command",
                side_effect=AssertionError("uv must not be resolved"),
            ),
            self.assertRaisesRegex(ValueError, "unknown dependency profile"),
        ):
            validate_skill_changes.unittest_command("unsupported")

    def test_positive_float_rejects_non_positive_timeout(self) -> None:
        self.assertEqual(12.5, validate_skill_changes.positive_float("12.5"))
        for value in ["0", "nan", "inf", "-inf"]:
            with self.subTest(value=value), self.assertRaisesRegex(
                validate_skill_changes.argparse.ArgumentTypeError,
                "finite number greater than zero",
            ):
                validate_skill_changes.positive_float(value)

    def test_run_command_reports_timeout_and_reaps_process_group(self) -> None:
        timeout = subprocess.TimeoutExpired(["fake-command"], 600)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, 0]
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ),
            patch.object(validate_skill_changes.os, "killpg") as killpg,
            patch("builtins.print"),
            self.assertRaisesRegex(
                RuntimeError,
                r"timed out after 900 seconds: fake-command",
            ),
        ):
            validate_skill_changes.run_command(["fake-command"])

        self.assertEqual(
            [call(1234, signal.SIGTERM), call(1234, signal.SIGKILL)],
            killpg.call_args_list,
        )
        self.assertEqual(5, process.wait.call_args_list[1].kwargs["timeout"])

    def test_run_command_starts_a_new_session_and_preserves_nonzero_failure(self) -> None:
        process = Mock(pid=1234)
        process.wait.return_value = 3
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
            patch("builtins.print"),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            validate_skill_changes.run_command(["fake-command"])

        self.assertEqual(True, popen.call_args.kwargs["start_new_session"])

    def test_run_command_uses_direct_termination_without_process_groups(self) -> None:
        timeout = subprocess.TimeoutExpired(["fake-command"], 900)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, 0]
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
            patch.object(validate_skill_changes, "process_group_supported", return_value=False),
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "timed out after 900 seconds"),
        ):
            validate_skill_changes.run_command(["fake-command"])

        self.assertNotIn("start_new_session", popen.call_args.kwargs)
        process.terminate.assert_called_once_with()

    def test_timeout_cleanup_keeps_original_error_when_kill_races_with_exit(self) -> None:
        timeout = subprocess.TimeoutExpired(["fake-command"], 900)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, timeout, 0]
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ),
            patch.object(validate_skill_changes.os, "killpg") as killpg,
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "timed out after 900 seconds"),
        ):
            killpg.side_effect = [None, ProcessLookupError()]
            validate_skill_changes.run_command(["fake-command"])

        self.assertEqual(2, killpg.call_count)

    def test_timeout_cleanup_attempts_kill_after_term_signal_races_with_exit(self) -> None:
        timeout = subprocess.TimeoutExpired(["fake-command"], 900)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, timeout, 0]
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ),
            patch.object(validate_skill_changes.os, "killpg") as killpg,
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "timed out after 900 seconds"),
        ):
            killpg.side_effect = [ProcessLookupError(), None]
            validate_skill_changes.run_command(["fake-command"])

        self.assertEqual(
            [call(1234, signal.SIGTERM), call(1234, signal.SIGKILL)],
            killpg.call_args_list,
        )

    def test_non_posix_timeout_cleanup_attempts_kill_after_terminate_failure(self) -> None:
        timeout = subprocess.TimeoutExpired(["fake-command"], 900)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, 0]
        process.terminate.side_effect = OSError("already exited")
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ),
            patch.object(validate_skill_changes, "process_group_supported", return_value=False),
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "timed out after 900 seconds"),
        ):
            validate_skill_changes.run_command(["fake-command"])

        process.kill.assert_called_once_with()

    def test_timeout_cleanup_wait_error_falls_back_to_kill(self) -> None:
        timeout = subprocess.TimeoutExpired(["fake-command"], 900)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, OSError("wait race"), 0]
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ),
            patch.object(validate_skill_changes.os, "killpg") as killpg,
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "timed out after 900 seconds"),
        ):
            validate_skill_changes.run_command(["fake-command"])

        self.assertEqual(
            [call(1234, signal.SIGTERM), call(1234, signal.SIGKILL)],
            killpg.call_args_list,
        )

    def test_timeout_cleanup_escalates_to_kill_when_term_does_not_exit(self) -> None:
        timeout = subprocess.TimeoutExpired(["fake-command"], 900)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, timeout, 0]
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ),
            patch.object(validate_skill_changes.os, "killpg") as killpg,
            patch("builtins.print"),
            self.assertRaisesRegex(RuntimeError, "timed out after 900 seconds"),
        ):
            validate_skill_changes.run_command(["fake-command"])

        self.assertEqual(
            [
                call(1234, signal.SIGTERM),
                call(1234, signal.SIGKILL),
            ],
            killpg.call_args_list,
        )

    def test_timeout_cleanup_kills_descendant_after_leader_exits_on_term(self) -> None:
        if not validate_skill_changes.process_group_supported():
            self.skipTest("requires POSIX process groups")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            child_pid_path = root / "child.pid"
            ready_path = root / "ready"
            child_code = (
                "import os, signal, time\n"
                "from pathlib import Path\n"
                "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                f"Path({str(child_pid_path)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
                f"Path({str(ready_path)!r}).write_text('ready', encoding='utf-8')\n"
                "deadline = time.monotonic() + 10\n"
                "while time.monotonic() < deadline:\n"
                "    time.sleep(0.01)\n"
            )
            parent_code = (
                "import subprocess, sys, time\n"
                "from pathlib import Path\n"
                f"subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
                f"while not Path({str(ready_path)!r}).exists():\n"
                "    time.sleep(0.01)\n"
                "time.sleep(60)\n"
            )
            # A loaded CI worker can need longer than one second to start both
            # interpreters and persist the descendant PID before the timeout.
            with patch.object(validate_skill_changes, "COMMAND_TIMEOUT_SECONDS", 5.0):
                with self.assertRaisesRegex(RuntimeError, "timed out after 5 seconds"):
                    validate_skill_changes.run_command([sys.executable, "-c", parent_code])

            self.assertTrue(child_pid_path.is_file())
            child_pid = int(child_pid_path.read_text(encoding="utf-8"))
            for _ in range(100):
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
            else:
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.fail("timeout cleanup left a descendant process running")

    def test_python_module_probe_reports_bounded_timeout(self) -> None:
        timeout = subprocess.TimeoutExpired(["python", "-c", "import yaml"], 10)
        process = Mock(pid=1234)
        process.wait.side_effect = [timeout, 0]
        with (
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
            patch.object(validate_skill_changes.os, "killpg") as killpg,
            self.assertRaisesRegex(
                RuntimeError,
                r"timed out after 10 seconds: .*import yaml",
            ),
        ):
            validate_skill_changes.python_module_available("yaml")

        self.assertEqual(10.0, process.wait.call_args_list[0].kwargs["timeout"])
        self.assertEqual(True, popen.call_args.kwargs["start_new_session"])
        self.assertEqual(
            [call(1234, signal.SIGTERM), call(1234, signal.SIGKILL)],
            killpg.call_args_list,
        )

    def test_python_module_probe_honors_lower_user_timeout(self) -> None:
        process = Mock(pid=1234)
        process.wait.return_value = 0
        with (
            patch.object(validate_skill_changes, "COMMAND_TIMEOUT_SECONDS", 3.0),
            patch.object(
                validate_skill_changes.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
        ):
            self.assertTrue(validate_skill_changes.python_module_available("yaml"))

        self.assertEqual(3.0, process.wait.call_args.kwargs["timeout"])
        self.assertEqual(subprocess.DEVNULL, popen.call_args.kwargs["stdout"])
        self.assertEqual(subprocess.DEVNULL, popen.call_args.kwargs["stderr"])

    def test_timeout_help_discloses_module_probe_cap(self) -> None:
        help_text = validate_skill_changes.build_parser().format_help()

        self.assertIn("Module availability probes use the", help_text)
        self.assertIn("lower of this value and 10 seconds.", help_text)

    def test_skip_skill_validate_help_preserves_repo_frontmatter_gate(self) -> None:
        help_text = validate_skill_changes.build_parser().format_help()

        self.assertIn("Skip only the machine-local skill-creator", help_text)
        self.assertIn("repository-owned SKILL.md", help_text)
        self.assertIn("frontmatter contract always runs.", help_text)

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

    def test_pyyaml_subprocess_disables_repository_bytecode_writes(self) -> None:
        calls: list[tuple[list[str], dict[str, str] | None]] = []

        with (
            patch.object(
                validate_skill_changes,
                "python_module_available",
                return_value=True,
            ),
            patch.object(
                validate_skill_changes,
                "run_command",
                side_effect=lambda command, env=None: calls.append((command, env)),
            ),
        ):
            validate_skill_changes.run_pyyaml_code("import yaml\n")

        self.assertEqual(1, len(calls))
        self.assertIsNotNone(calls[0][1])
        self.assertEqual("1", calls[0][1]["PYTHONDONTWRITEBYTECODE"])

    def test_skill_validate_disables_repository_bytecode_writes(self) -> None:
        calls: list[tuple[list[str], dict[str, str] | None]] = []
        quick_validate = Path("/tmp/quick_validate.py")
        args = validate_skill_changes.build_parser().parse_args(
            ["--quick-validate", str(quick_validate)]
        )

        with (
            patch.object(
                validate_skill_changes,
                "quick_validate_path",
                return_value=quick_validate,
            ),
            patch.object(validate_skill_changes, "uv_command", return_value="uv"),
            patch.object(
                validate_skill_changes,
                "run_command",
                side_effect=lambda command, env=None: calls.append((command, env)),
            ),
        ):
            validate_skill_changes.check_skill_validate(args)

        self.assertEqual(1, len(calls))
        self.assertIsNotNone(calls[0][1])
        self.assertEqual("1", calls[0][1]["PYTHONDONTWRITEBYTECODE"])

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
