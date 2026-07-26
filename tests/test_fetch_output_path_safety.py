from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import fetch_akshare_a_share as akshare_a_share  # noqa: E402
import fetch_akshare_hk_daily as akshare_hk_daily  # noqa: E402
import fetch_baostock_a_share_universe as baostock_universe  # noqa: E402
import fetch_eastmoney_a_share_spot as eastmoney_spot  # noqa: E402
import fetch_pytdx_a_share as pytdx_a_share  # noqa: E402
import fetch_yfinance_ohlcv as yfinance_ohlcv  # noqa: E402


FETCH_CLI_CASES = (
    (
        "akshare_a_share",
        akshare_a_share,
        "fetch_prices",
        [
            "--symbols",
            "000001",
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-29",
        ],
    ),
    (
        "akshare_hk_daily",
        akshare_hk_daily,
        "fetch_prices",
        [
            "--symbols",
            "00700",
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-29",
        ],
    ),
    ("baostock_universe", baostock_universe, "fetch_universe", []),
    ("eastmoney_spot", eastmoney_spot, "fetch_snapshot", []),
    (
        "pytdx_a_share",
        pytdx_a_share,
        "fetch_prices",
        [
            "--symbols",
            "000001",
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-29",
        ],
    ),
    (
        "yfinance_ohlcv",
        yfinance_ohlcv,
        "fetch_prices",
        [
            "--symbols",
            "AAPL",
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-29",
        ],
    ),
)


class FetchOutputPathSafetyTests(unittest.TestCase):
    def test_fetch_cli_help_discloses_distinct_output_requirement(self) -> None:
        for case_name, module, _provider_name, _common_args in FETCH_CLI_CASES:
            with self.subTest(cli=case_name):
                help_text = module.build_parser().format_help()
                self.assertIn("must differ from metadata", help_text)
                self.assertIn("must differ from", help_text)

    def test_fetch_clis_reject_output_metadata_aliases_before_provider_calls(
        self,
    ) -> None:
        for case_name, module, provider_name, common_args in FETCH_CLI_CASES:
            for alias_kind in ("direct", "relative", "symlink", "hardlink"):
                with self.subTest(cli=case_name, alias=alias_kind):
                    self.assert_output_metadata_alias_rejected(
                        module,
                        provider_name,
                        common_args,
                        alias_kind,
                    )

    def test_fetch_clis_reject_case_only_output_aliases_before_provider_calls(
        self,
    ) -> None:
        for case_name, module, provider_name, common_args in FETCH_CLI_CASES:
            with self.subTest(cli=case_name):
                with tempfile.TemporaryDirectory() as tmpdir:
                    root = Path(tmpdir)
                    output = root / "Prices.csv"
                    metadata_output = root / "prices.csv"

                    code, stdout, stderr, provider_calls = self.run_cli(
                        module,
                        provider_name,
                        common_args,
                        output,
                        metadata_output,
                    )

                self.assertEqual(2, code)
                self.assertEqual(0, provider_calls)
                self.assertEqual("", stdout)
                self.assertFalse(output.exists())
                self.assertFalse(metadata_output.exists())
                self.assertIn("code=invalid_argument", stderr)
                self.assertIn("output paths must be distinct", stderr)

    def test_fetch_clis_reject_output_directories_before_provider_calls(self) -> None:
        for case_name, module, provider_name, common_args in FETCH_CLI_CASES:
            for directory_role in ("output", "metadata"):
                with self.subTest(cli=case_name, directory_role=directory_role):
                    self.assert_directory_path_rejected(
                        module,
                        provider_name,
                        common_args,
                        directory_role,
                    )

    def assert_output_metadata_alias_rejected(
        self,
        module: object,
        provider_name: str,
        common_args: list[str],
        alias_kind: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "shared-output"
            original = b"existing output must remain intact\n"
            output.write_bytes(original)
            metadata_output = self.output_alias(output, root, alias_kind)

            code, stdout, stderr, provider_calls = self.run_cli(
                module,
                provider_name,
                common_args,
                output,
                metadata_output,
            )

            self.assertEqual(2, code)
            self.assertEqual(0, provider_calls)
            self.assertEqual("", stdout)
            self.assertEqual(original, output.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("output paths must be distinct", stderr)
            if alias_kind == "symlink":
                self.assertTrue(metadata_output.is_symlink())
            if alias_kind == "hardlink":
                self.assertTrue(os.path.samefile(output, metadata_output))

    def assert_directory_path_rejected(
        self,
        module: object,
        provider_name: str,
        common_args: list[str],
        directory_role: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "prices.csv"
            metadata_output = root / "metadata.json"
            output.write_bytes(b"stale prices must remain intact\n")
            metadata_output.write_bytes(b"stale metadata must remain intact\n")
            directory = root / f"{directory_role}-directory"
            directory.mkdir()
            if directory_role == "output":
                output = directory
            else:
                metadata_output = directory

            code, stdout, stderr, provider_calls = self.run_cli(
                module,
                provider_name,
                common_args,
                output,
                metadata_output,
            )

            self.assertEqual(2, code)
            self.assertEqual(0, provider_calls)
            self.assertEqual("", stdout)
            self.assertTrue(directory.is_dir())
            if directory_role == "output":
                self.assertEqual(
                    b"stale metadata must remain intact\n", metadata_output.read_bytes()
                )
            else:
                self.assertEqual(
                    b"stale prices must remain intact\n", output.read_bytes()
                )
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("output path must be a file, not a directory", stderr)

    @staticmethod
    def output_alias(output: Path, root: Path, alias_kind: str) -> Path:
        if alias_kind == "direct":
            return output
        if alias_kind == "relative":
            return Path(os.path.relpath(output, start=Path.cwd()))
        if alias_kind == "symlink":
            alias = root / "metadata-link"
            alias.symlink_to(output)
            return alias
        if alias_kind == "hardlink":
            alias = root / "metadata-hardlink"
            os.link(output, alias)
            return alias
        raise AssertionError(f"unexpected alias kind: {alias_kind}")

    @staticmethod
    def run_cli(
        module: object,
        provider_name: str,
        common_args: list[str],
        output: Path,
        metadata_output: Path,
    ) -> tuple[int, str, str, int]:
        stdout = StringIO()
        stderr = StringIO()
        args = [
            *common_args,
            "--output",
            str(output),
            "--metadata-output",
            str(metadata_output),
        ]
        with patch.object(
            module,
            provider_name,
            side_effect=AssertionError("provider called"),
        ) as provider:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = module.main(args)
        return code, stdout.getvalue(), stderr.getvalue(), provider.call_count


if __name__ == "__main__":
    unittest.main()
