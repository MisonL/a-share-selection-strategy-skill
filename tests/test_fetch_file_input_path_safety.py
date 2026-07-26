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

import fetch_baostock_a_share as baostock_a_share  # noqa: E402
import fetch_zzshare_a_share as zzshare_a_share  # noqa: E402


ALIAS_KINDS = ("direct", "relative", "symlink", "hardlink")
OUTPUT_ROLES = ("output", "metadata")


class FetchFileInputPathSafetyTests(unittest.TestCase):
    def test_baostock_rejects_file_input_aliases_before_reads_or_fetches(self) -> None:
        for input_option in ("--symbols-file", "--names-input"):
            for output_role in OUTPUT_ROLES:
                for alias_kind in ALIAS_KINDS:
                    with self.subTest(
                        input_option=input_option,
                        output_role=output_role,
                        alias_kind=alias_kind,
                    ):
                        self.assert_baostock_input_alias_rejected(
                            input_option,
                            output_role,
                            alias_kind,
                        )

    def test_zzshare_rejects_symbols_file_aliases_before_reads_or_fetches(self) -> None:
        for output_role in OUTPUT_ROLES:
            for alias_kind in ALIAS_KINDS:
                with self.subTest(output_role=output_role, alias_kind=alias_kind):
                    self.assert_zzshare_symbols_file_alias_rejected(
                        output_role,
                        alias_kind,
                    )

    def test_file_input_fetch_clis_reject_output_inside_directory_inputs(self) -> None:
        for case_name, module in self.fetch_cli_cases():
            with self.subTest(cli=case_name):
                self.assert_directory_input_child_rejected(module)

    def test_zzshare_rejects_checkpoint_aliases_before_fetches(self) -> None:
        for output_role in OUTPUT_ROLES:
            for alias_kind in ALIAS_KINDS:
                with self.subTest(output_role=output_role, alias_kind=alias_kind):
                    self.assert_zzshare_checkpoint_alias_rejected(
                        output_role,
                        alias_kind,
                    )

    def test_zzshare_rejects_unexpanded_home_shorthand_before_fetches(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoint"
            checkpoint_dir.mkdir()
            checkpoint_file = checkpoint_dir / "manifest.json"
            original = b"checkpoint artifact must remain intact\n"
            checkpoint_file.write_bytes(original)
            output_alias = root / "output-hardlink"
            os.link(checkpoint_file, output_alias)
            metadata_output = root / "metadata.json"
            metadata_original = b"stale metadata must remain intact\n"
            metadata_output.write_bytes(metadata_original)
            output_argument = Path("~") / output_alias.name
            checkpoint_argument = Path("~") / checkpoint_dir.name
            arguments = [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-29",
                "--output",
                str(output_argument),
                "--metadata-output",
                str(metadata_output),
                "--checkpoint-dir",
                str(checkpoint_argument),
                "--checkpoint-batch-size",
                "1",
                "--request-interval-seconds",
                "0",
            ]

            with patch.dict(os.environ, {"HOME": str(root)}):
                code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                    zzshare_a_share,
                    arguments,
                )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertEqual(original, checkpoint_file.read_bytes())
            self.assertEqual(metadata_original, metadata_output.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("path must not use unexpanded home shorthand", stderr)

    def test_zzshare_rejects_unexpanded_home_checkpoint_before_cleanup_or_fetches(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            checkpoint = home / "checkpoint"
            checkpoint.mkdir(parents=True)
            manifest = checkpoint / "manifest.json"
            manifest_original = b"checkpoint manifest must remain intact\n"
            manifest.write_bytes(manifest_original)
            output = root / "prices.csv"
            metadata_output = root / "metadata.json"
            output_original = b"stale prices must remain intact\n"
            metadata_original = b"stale metadata must remain intact\n"
            output.write_bytes(output_original)
            metadata_output.write_bytes(metadata_original)

            with patch.dict(os.environ, {"HOME": str(home)}):
                code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                    zzshare_a_share,
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-01",
                        "--end-date",
                        "2026-05-29",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata_output),
                        "--checkpoint-dir",
                        "~/checkpoint",
                        "--checkpoint-batch-size",
                        "1",
                        "--request-interval-seconds",
                        "0",
                    ],
                )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertEqual(manifest_original, manifest.read_bytes())
            self.assertEqual(output_original, output.read_bytes())
            self.assertEqual(metadata_original, metadata_output.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("path must not use unexpanded home shorthand", stderr)

    def test_file_input_fetch_clis_reject_output_metadata_aliases_before_fetches(
        self,
    ) -> None:
        for case_name, module in self.fetch_cli_cases():
            for alias_kind in ALIAS_KINDS:
                with self.subTest(cli=case_name, alias_kind=alias_kind):
                    self.assert_output_metadata_alias_rejected(module, alias_kind)

    def test_file_input_fetch_clis_reject_output_directories_before_fetches(
        self,
    ) -> None:
        for case_name, module in self.fetch_cli_cases():
            for output_role in OUTPUT_ROLES:
                with self.subTest(cli=case_name, output_role=output_role):
                    self.assert_output_directory_rejected(module, output_role)

    def test_file_input_fetch_clis_reject_case_only_input_aliases_before_reads(
        self,
    ) -> None:
        for case_name, module in self.fetch_cli_cases():
            with self.subTest(cli=case_name):
                with tempfile.TemporaryDirectory() as tmpdir:
                    root = Path(tmpdir)
                    input_path = root / "Symbols.txt"
                    original = b"000001\n"
                    input_path.write_bytes(original)
                    output = root / "symbols.txt"
                    metadata_output = root / "metadata.json"
                    arguments = [
                        "--symbols-file",
                        str(input_path),
                        "--start-date",
                        "2026-05-01",
                        "--end-date",
                        "2026-05-29",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata_output),
                    ]
                    if module is zzshare_a_share:
                        arguments.extend(["--request-interval-seconds", "0"])

                    code, stdout, stderr, fetch_calls, read_calls = (
                        self.run_rejected_cli(module, arguments)
                    )

                    self.assertEqual(2, code)
                    self.assertEqual("", stdout)
                    self.assertEqual(0, fetch_calls)
                    self.assertEqual(0, read_calls)
                    self.assertEqual(original, input_path.read_bytes())
                    self.assertFalse(metadata_output.exists())
                    self.assertIn("code=invalid_argument", stderr)
                    self.assertIn("output path must differ from input paths", stderr)

    def test_zzshare_rejects_new_output_paths_inside_checkpoint_directory(self) -> None:
        for output_role in OUTPUT_ROLES:
            with self.subTest(output_role=output_role):
                self.assert_zzshare_checkpoint_child_rejected(output_role)

    def test_zzshare_rejects_checkpoint_directory_symlink_before_any_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoint"
            checkpoint_dir.mkdir()
            external_directory = root / "external"
            external_directory.mkdir()
            checkpoint_artifact = external_directory / "part.csv"
            original = b"checkpoint artifact must remain intact\n"
            checkpoint_artifact.write_bytes(original)
            (checkpoint_dir / "linked-artifacts").symlink_to(
                external_directory,
                target_is_directory=True,
            )
            metadata_output = root / "metadata.json"

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                zzshare_a_share,
                [
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2026-05-01",
                    "--end-date",
                    "2026-05-29",
                    "--output",
                    str(checkpoint_artifact),
                    "--metadata-output",
                    str(metadata_output),
                    "--checkpoint-dir",
                    str(checkpoint_dir),
                    "--checkpoint-batch-size",
                    "1",
                    "--request-interval-seconds",
                    "0",
                ],
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertEqual(original, checkpoint_artifact.read_bytes())
            self.assertFalse(metadata_output.exists())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("protected directory must not contain symlinks", stderr)

    def test_zzshare_rejects_dangling_checkpoint_symlink_before_any_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoint"
            checkpoint_dir.mkdir()
            dangling_link = checkpoint_dir / "missing-artifacts"
            dangling_link.symlink_to(root / "missing-target", target_is_directory=True)
            output = root / "prices.csv"
            original = b"stale output must remain intact\n"
            output.write_bytes(original)
            metadata_output = root / "metadata.json"

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                zzshare_a_share,
                [
                    "--symbols",
                    "000001",
                    "--start-date",
                    "2026-05-01",
                    "--end-date",
                    "2026-05-29",
                    "--output",
                    str(output),
                    "--metadata-output",
                    str(metadata_output),
                    "--checkpoint-dir",
                    str(checkpoint_dir),
                    "--checkpoint-batch-size",
                    "1",
                    "--request-interval-seconds",
                    "0",
                ],
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertTrue(dangling_link.is_symlink())
            self.assertEqual(original, output.read_bytes())
            self.assertFalse(metadata_output.exists())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("protected directory must not contain symlinks", stderr)

    def test_zzshare_rejects_checkpoint_parent_symlinks_before_cleanup_or_fetches(
        self,
    ) -> None:
        for state in ("new", "existing"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                external = root / "external"
                external.mkdir()
                checkpoint_name = f"{state}-checkpoint"
                actual_checkpoint = external / checkpoint_name
                manifest = actual_checkpoint / "manifest.json"
                part = actual_checkpoint / "prices_part_00001.csv"
                manifest_original = b"checkpoint manifest must remain intact\n"
                part_original = b"checkpoint part must remain intact\n"
                if state == "existing":
                    actual_checkpoint.mkdir()
                    manifest.write_bytes(manifest_original)
                    part.write_bytes(part_original)
                checkpoint_link = root / "checkpoint-link"
                checkpoint_link.symlink_to(external, target_is_directory=True)
                output = root / "prices.csv"
                metadata_output = root / "metadata.json"
                output_original = b"stale prices must remain intact\n"
                metadata_original = b"stale metadata must remain intact\n"
                output.write_bytes(output_original)
                metadata_output.write_bytes(metadata_original)

                code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                    zzshare_a_share,
                    [
                        "--symbols",
                        "000001",
                        "--start-date",
                        "2026-05-01",
                        "--end-date",
                        "2026-05-29",
                        "--output",
                        str(output),
                        "--metadata-output",
                        str(metadata_output),
                        "--checkpoint-dir",
                        str(checkpoint_link / checkpoint_name),
                        "--checkpoint-batch-size",
                        "1",
                        "--request-interval-seconds",
                        "0",
                    ],
                )

                self.assertEqual(2, code)
                self.assertEqual("", stdout)
                self.assertEqual(0, fetch_calls)
                self.assertEqual(0, read_calls)
                self.assertEqual(output_original, output.read_bytes())
                self.assertEqual(metadata_original, metadata_output.read_bytes())
                self.assertIn("code=invalid_argument", stderr)
                self.assertIn("protected directory must not contain symlinks", stderr)
                if state == "new":
                    self.assertFalse(actual_checkpoint.exists())
                else:
                    self.assertEqual(manifest_original, manifest.read_bytes())
                    self.assertEqual(part_original, part.read_bytes())

    def test_file_input_fetch_help_discloses_path_boundaries(self) -> None:
        baostock_help = " ".join(baostock_a_share.build_parser().format_help().split())
        zzshare_help = " ".join(zzshare_a_share.build_parser().format_help().split())

        self.assertIn("must differ from metadata and file inputs", baostock_help)
        self.assertIn("must differ from prices and file inputs", baostock_help)
        self.assertIn(
            "must differ from metadata, file inputs, and checkpoints", zzshare_help
        )
        self.assertIn("must not contain prices or metadata outputs", zzshare_help)

    def assert_baostock_input_alias_rejected(
        self,
        input_option: str,
        output_role: str,
        alias_kind: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path, original = self.write_baostock_input(root, input_option)
            output, metadata_output, safe_path, safe_original = self.output_paths(
                root,
                input_path,
                output_role,
                alias_kind,
            )
            arguments = self.baostock_arguments(
                input_option,
                input_path,
                output,
                metadata_output,
            )

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                baostock_a_share,
                arguments,
            )

            self.assert_rejected_input_alias(
                code,
                stdout,
                stderr,
                fetch_calls,
                read_calls,
                input_path,
                original,
                safe_path,
                safe_original,
            )

    def assert_zzshare_symbols_file_alias_rejected(
        self,
        output_role: str,
        alias_kind: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "symbols.txt"
            original = b"000001\n"
            input_path.write_bytes(original)
            output, metadata_output, safe_path, safe_original = self.output_paths(
                root,
                input_path,
                output_role,
                alias_kind,
            )
            arguments = [
                "--symbols-file",
                str(input_path),
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-29",
                "--output",
                str(output),
                "--metadata-output",
                str(metadata_output),
                "--request-interval-seconds",
                "0",
            ]

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                zzshare_a_share,
                arguments,
            )

            self.assert_rejected_input_alias(
                code,
                stdout,
                stderr,
                fetch_calls,
                read_calls,
                input_path,
                original,
                safe_path,
                safe_original,
            )

    def assert_zzshare_checkpoint_alias_rejected(
        self,
        output_role: str,
        alias_kind: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoint"
            checkpoint_dir.mkdir()
            checkpoint_file = checkpoint_dir / "manifest.json"
            original = b'{"checkpoint": "must remain intact"}\n'
            checkpoint_file.write_bytes(original)
            output, metadata_output, safe_path, safe_original = self.output_paths(
                root,
                checkpoint_file,
                output_role,
                alias_kind,
            )
            arguments = [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-29",
                "--output",
                str(output),
                "--metadata-output",
                str(metadata_output),
                "--checkpoint-dir",
                str(checkpoint_dir),
                "--checkpoint-batch-size",
                "1",
                "--request-interval-seconds",
                "0",
            ]

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                zzshare_a_share,
                arguments,
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertEqual(original, checkpoint_file.read_bytes())
            self.assertEqual(safe_original, safe_path.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("output path must not overlap protected directories", stderr)

    def assert_directory_input_child_rejected(self, module: object) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_directory = root / "symbols-input"
            input_directory.mkdir()
            output = input_directory / "prices.csv"
            original = b"input-directory file must remain intact\n"
            output.write_bytes(original)
            metadata_output = root / "metadata.json"
            metadata_original = b"stale metadata must remain intact\n"
            metadata_output.write_bytes(metadata_original)
            arguments = [
                "--symbols-file",
                str(input_directory),
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-29",
                "--output",
                str(output),
                "--metadata-output",
                str(metadata_output),
            ]
            if module is zzshare_a_share:
                arguments.extend(["--request-interval-seconds", "0"])

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                module,
                arguments,
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertEqual(original, output.read_bytes())
            self.assertEqual(metadata_original, metadata_output.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("output path must differ from input paths", stderr)

    def assert_output_metadata_alias_rejected(
        self,
        module: object,
        alias_kind: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "shared-output.csv"
            original = b"shared output must remain intact\n"
            output.write_bytes(original)
            metadata_output = self.path_alias(output, root, alias_kind)

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                module,
                self.standard_arguments(output, metadata_output, module),
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertEqual(original, output.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("output paths must be distinct", stderr)

    def assert_output_directory_rejected(
        self, module: object, output_role: str
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "prices.csv"
            metadata_output = root / "metadata.json"
            output.write_bytes(b"stale prices must remain intact\n")
            metadata_output.write_bytes(b"stale metadata must remain intact\n")
            directory = root / f"{output_role}-directory"
            directory.mkdir()
            if output_role == "output":
                output = directory
                safe_path = metadata_output
                safe_original = metadata_output.read_bytes()
            else:
                metadata_output = directory
                safe_path = output
                safe_original = output.read_bytes()

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                module,
                self.standard_arguments(output, metadata_output, module),
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertTrue(directory.is_dir())
            self.assertEqual(safe_original, safe_path.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("output path must be a file, not a directory", stderr)

    def assert_zzshare_checkpoint_child_rejected(self, output_role: str) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoint"
            checkpoint_dir.mkdir()
            checkpoint_manifest = checkpoint_dir / "manifest.json"
            checkpoint_original = b"checkpoint artifact must remain intact\n"
            checkpoint_manifest.write_bytes(checkpoint_original)
            output = root / "prices.csv"
            metadata_output = root / "metadata.json"
            output.write_bytes(b"stale prices must remain intact\n")
            metadata_output.write_bytes(b"stale metadata must remain intact\n")
            protected_output = checkpoint_dir / f"{output_role}.csv"
            if output_role == "output":
                output = protected_output
                safe_path = metadata_output
                safe_original = metadata_output.read_bytes()
            else:
                metadata_output = protected_output
                safe_path = output
                safe_original = output.read_bytes()
            arguments = [
                "--symbols",
                "000001",
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-29",
                "--output",
                str(output),
                "--metadata-output",
                str(metadata_output),
                "--checkpoint-dir",
                str(checkpoint_dir),
                "--checkpoint-batch-size",
                "1",
                "--request-interval-seconds",
                "0",
            ]

            code, stdout, stderr, fetch_calls, read_calls = self.run_rejected_cli(
                zzshare_a_share,
                arguments,
            )

            self.assertEqual(2, code)
            self.assertEqual("", stdout)
            self.assertEqual(0, fetch_calls)
            self.assertEqual(0, read_calls)
            self.assertFalse(protected_output.exists())
            self.assertEqual(checkpoint_original, checkpoint_manifest.read_bytes())
            self.assertEqual(safe_original, safe_path.read_bytes())
            self.assertIn("code=invalid_argument", stderr)
            self.assertIn("output path must not overlap protected directories", stderr)

    @staticmethod
    def write_baostock_input(root: Path, input_option: str) -> tuple[Path, bytes]:
        if input_option == "--symbols-file":
            path = root / "symbols.txt"
            original = b"000001\n"
        else:
            path = root / "names.csv"
            original = b"symbol,name\n000001,Sample\n"
        path.write_bytes(original)
        return path, original

    @staticmethod
    def output_paths(
        root: Path,
        protected_path: Path,
        output_role: str,
        alias_kind: str,
    ) -> tuple[Path, Path, Path, bytes]:
        output = root / "prices.csv"
        metadata_output = root / "metadata.json"
        output.write_bytes(b"stale prices must remain intact\n")
        metadata_output.write_bytes(b"stale metadata must remain intact\n")
        alias = FetchFileInputPathSafetyTests.path_alias(
            protected_path,
            root,
            alias_kind,
        )
        if output_role == "output":
            return alias, metadata_output, metadata_output, metadata_output.read_bytes()
        return output, alias, output, output.read_bytes()

    @staticmethod
    def path_alias(target: Path, root: Path, alias_kind: str) -> Path:
        if alias_kind == "direct":
            return target
        if alias_kind == "relative":
            return Path(os.path.relpath(target, start=Path.cwd()))
        if alias_kind == "symlink":
            alias = root / "output-link"
            alias.symlink_to(target)
            return alias
        if alias_kind == "hardlink":
            alias = root / "output-hardlink"
            os.link(target, alias)
            return alias
        raise AssertionError(f"unexpected alias kind: {alias_kind}")

    @staticmethod
    def baostock_arguments(
        input_option: str,
        input_path: Path,
        output: Path,
        metadata_output: Path,
    ) -> list[str]:
        arguments = [
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-29",
            "--output",
            str(output),
            "--metadata-output",
            str(metadata_output),
        ]
        if input_option == "--symbols-file":
            return ["--symbols-file", str(input_path), *arguments]
        return ["--symbols", "000001", "--names-input", str(input_path), *arguments]

    @staticmethod
    def fetch_cli_cases() -> tuple[tuple[str, object], ...]:
        return (
            ("baostock", baostock_a_share),
            ("zzshare", zzshare_a_share),
        )

    @staticmethod
    def standard_arguments(
        output: Path,
        metadata_output: Path,
        module: object,
    ) -> list[str]:
        arguments = [
            "--symbols",
            "000001",
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-29",
            "--output",
            str(output),
            "--metadata-output",
            str(metadata_output),
        ]
        if module is zzshare_a_share:
            arguments.extend(["--request-interval-seconds", "0"])
        return arguments

    @staticmethod
    def run_rejected_cli(
        module: object,
        arguments: list[str],
    ) -> tuple[int, str, str, int, int]:
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(
                module,
                "fetch_prices",
                side_effect=AssertionError("fetch must not run"),
            ) as fetch_prices,
            patch.object(
                module,
                "read_symbols_file",
                side_effect=AssertionError("symbols file must not be read"),
            ) as read_symbols_file,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = module.main(arguments)
        return (
            code,
            stdout.getvalue(),
            stderr.getvalue(),
            fetch_prices.call_count,
            read_symbols_file.call_count,
        )

    def assert_rejected_input_alias(
        self,
        code: int,
        stdout: str,
        stderr: str,
        fetch_calls: int,
        read_calls: int,
        input_path: Path,
        original: bytes,
        safe_path: Path,
        safe_original: bytes,
    ) -> None:
        self.assertEqual(2, code)
        self.assertEqual("", stdout)
        self.assertEqual(0, fetch_calls)
        self.assertEqual(0, read_calls)
        self.assertEqual(original, input_path.read_bytes())
        self.assertEqual(safe_original, safe_path.read_bytes())
        self.assertIn("code=invalid_argument", stderr)
        self.assertIn("output path must differ from input paths", stderr)


if __name__ == "__main__":
    unittest.main()
