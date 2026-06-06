from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentConsistencyTests(unittest.TestCase):
    def test_agents_license_statement_matches_repository_license(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertIn("MIT License", license_text)
        self.assertIn("MIT License", readme)
        self.assertNotIn("当前仓库未声明许可证", agents)


if __name__ == "__main__":
    unittest.main()
