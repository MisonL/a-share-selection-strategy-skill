from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import validate_skill_changes


class ValidateSkillChangesTests(unittest.TestCase):
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
