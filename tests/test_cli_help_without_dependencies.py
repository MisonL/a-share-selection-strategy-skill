from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliHelpWithoutDependenciesTests(unittest.TestCase):
    def test_walk_forward_navigation_help_does_not_import_pandas(self) -> None:
        scripts = [
            ROOT / "scripts/run_baostock_walk_forward.py",
            ROOT / "scripts/probe_baostock_limit_fields.py",
        ]
        for script in scripts:
            with self.subTest(script=script.name):
                result = subprocess.run(
                    [sys.executable, "-S", str(script), "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("usage:", result.stdout)
