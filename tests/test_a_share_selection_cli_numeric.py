from __future__ import annotations

import math
import sys
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.selection_core.a_share_selection_cli_numeric import (  # noqa: E402
    integer_or_non_finite,
    normalize_negative_non_finite_option_values,
)


class CliNumericTests(unittest.TestCase):
    def test_normalizes_negative_non_finite_value_after_known_option(self) -> None:
        result = normalize_negative_non_finite_option_values(
            ["--value", "-inf", "--other", "1"],
            ["--value"],
        )

        self.assertEqual(["--value=-inf", "--other", "1"], result)

    def test_only_normalizes_known_options_and_literals(self) -> None:
        result = normalize_negative_non_finite_option_values(
            ["--unknown", "-inf", "--value", "-1.0", "--value", "-NaN"],
            ["--value"],
        )

        self.assertEqual(
            ["--unknown", "-inf", "--value", "-1.0", "--value=-NaN"], result
        )

    def test_uses_process_arguments_when_argv_is_none(self) -> None:
        with patch.object(sys, "argv", ["tool.py", "--value", "-inf"]):
            result = normalize_negative_non_finite_option_values(None, ["--value"])

        self.assertEqual(["--value=-inf"], result)

    def test_integer_parser_preserves_non_finite_values_for_contract_validation(
        self,
    ) -> None:
        self.assertEqual(5, integer_or_non_finite("5"))
        for value in ["nan", "inf", "-inf"]:
            with self.subTest(value=value):
                self.assertFalse(math.isfinite(integer_or_non_finite(value)))

    def test_integer_parser_rejects_finite_non_integer_values(self) -> None:
        with self.assertRaisesRegex(Exception, "integer"):
            integer_or_non_finite("1.5")


if __name__ == "__main__":
    unittest.main()
