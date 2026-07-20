from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lib.a_share_selection_run_state as run_state  # noqa: E402
import lib.runner.run_today_a_share_selection_helpers as runner_helpers  # noqa: E402
import lib.runner.run_today_a_share_selection_input_metadata as input_metadata  # noqa: E402


def imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def imports_package(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def layer_imports(
    path: Path,
    *,
    absolute_package: str,
    relative_level: int,
    relative_package: str,
) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            matches.extend(
                alias.name
                for alias in node.names
                if imports_package(alias.name, absolute_package)
            )
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        if imports_package(module, absolute_package):
            matches.append(module)
        elif node.level == 0 and module == "lib":
            matches.extend(
                f"lib.{alias.name}"
                for alias in node.names
                if imports_package(alias.name, relative_package)
            )
        elif node.level == relative_level and imports_package(
            module, relative_package
        ):
            matches.append(f"relative:{module}")
        elif node.level == relative_level and not module:
            matches.extend(
                f"relative:{alias.name}"
                for alias in node.names
                if imports_package(alias.name, relative_package)
            )
    return matches


class SharedRunStateTests(unittest.TestCase):
    def test_layer_imports_detects_absolute_and_relative_runner_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "report_helper.py"
            source.write_text(
                "import lib.runner.helpers\n"
                "from lib.runner import helpers\n"
                "from lib import runner\n"
                "from ..runner import helpers\n"
                "from .. import runner\n",
                encoding="utf-8",
            )

            imports = layer_imports(
                source,
                absolute_package="lib.runner",
                relative_level=2,
                relative_package="runner",
            )

        self.assertEqual(
            [
                "lib.runner.helpers",
                "lib.runner",
                "lib.runner",
                "relative:runner",
                "relative:runner",
            ],
            imports,
        )

    def test_shared_predicates_preserve_partial_state_contracts(self) -> None:
        self.assertEqual([], run_state.list_value({"symbols": "000001"}, "symbols"))
        self.assertEqual(["000001"], run_state.list_value({"symbols": ["000001"]}, "symbols"))
        self.assertEqual(3, run_state.integer_value("3"))
        self.assertIsNone(run_state.integer_value("not-an-integer"))
        self.assertFalse(run_state.quality_count_present({"invalid_rows": 0}))
        self.assertTrue(run_state.quality_count_present({"non_trading_rows": "1"}))
        self.assertFalse(run_state.history_partial_result({"symbol_count": 1}))
        self.assertTrue(
            run_state.history_partial_result(
                {"requested_symbols": ["000001"], "symbol_count": 0}
            )
        )
        with self.assertRaises(ValueError):
            run_state.history_partial_result(
                {"requested_symbols": ["000001"], "symbol_count": "invalid"}
            )
        self.assertFalse(
            run_state.local_input_partial_result(
                {"input_requested_symbol_count": 2, "symbol_count": 2}
            )
        )
        self.assertTrue(
            run_state.local_input_partial_result(
                {"input_requested_symbol_count": 2, "symbol_count": 1}
            )
        )
        self.assertTrue(
            run_state.history_selection_partial_result(
                {"history_metadata_fallback_error_count": "1"}
            )
        )
        self.assertTrue(run_state.is_synthetic_demo({"source_type": "synthetic_demo"}))
        self.assertFalse(run_state.is_synthetic_demo({"source_type": "external_fetch"}))
        self.assertTrue(run_state.step_executed({}))
        self.assertFalse(run_state.step_executed({"executed": False}))

    def test_runner_modules_keep_shared_contract_aliases(self) -> None:
        for name in [
            "QUALITY_COUNT_KEYS",
            "list_value",
            "integer_value",
            "quality_count_present",
            "requested_symbol_count",
            "history_partial_result",
            "history_selection_partial_result",
            "local_input_partial_result",
            "is_synthetic_demo",
        ]:
            with self.subTest(name=name):
                self.assertIs(getattr(input_metadata, name), getattr(run_state, name))
        self.assertIs(runner_helpers.step_executed, run_state.step_executed)

    def test_report_html_cannot_depend_on_runner_implementation(self) -> None:
        report_html = SCRIPTS / "lib" / "report_html"
        runner_imports = []
        for path in sorted(report_html.rglob("*.py")):
            for module in layer_imports(
                path,
                absolute_package="lib.runner",
                relative_level=2,
                relative_package="runner",
            ):
                runner_imports.append((path.relative_to(SCRIPTS).as_posix(), module))

        self.assertEqual([], runner_imports)
        for path in [
            report_html / "a_share_selection_html_modes.py",
            report_html / "a_share_selection_html_sections.py",
        ]:
            self.assertIn("lib.a_share_selection_run_state", imported_module_names(path))

    def test_shared_module_stays_below_runner_and_report_layers(self) -> None:
        shared_module = SCRIPTS / "lib" / "a_share_selection_run_state.py"
        self.assertEqual(
            [],
            layer_imports(
                shared_module,
                absolute_package="lib.runner",
                relative_level=1,
                relative_package="runner",
            ),
        )
        self.assertEqual(
            [],
            layer_imports(
                shared_module,
                absolute_package="lib.report_html",
                relative_level=1,
                relative_package="report_html",
            ),
        )
        for path in [
            SCRIPTS / "lib" / "runner" / "run_today_a_share_selection_helpers.py",
            SCRIPTS / "lib" / "runner" / "run_today_a_share_selection_input_metadata.py",
            SCRIPTS / "lib" / "runner" / "run_today_a_share_selection_summary.py",
        ]:
            self.assertIn("lib.a_share_selection_run_state", imported_module_names(path))

    def test_script_inventory_counts_the_internal_shared_module(self) -> None:
        inventory = (
            SCRIPTS.parent / "references" / "script-inventory.md"
        ).read_text(encoding="utf-8")
        all_python_files = list(SCRIPTS.rglob("*.py"))
        internal_python_files = list((SCRIPTS / "lib").rglob("*.py"))

        self.assertIn(
            "当前整个 `scripts/` 树有 "
            f"{len(all_python_files)} 个 Python 文件；其中 "
            f"{len(internal_python_files)} 个是按领域分层的内部实现",
            inventory,
        )
