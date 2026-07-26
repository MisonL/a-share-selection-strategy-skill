from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import prepare_clean_history_pool as clean_history_pool_cli  # noqa: E402
import prepare_history_retry_symbols as retry_symbols  # noqa: E402
import prepare_incremental_history_plan as incremental_plan  # noqa: E402
from lib.gates.a_share_selection_output_safety import prepare_output_paths  # noqa: E402


class HistoryArtifactOutputPathSafetyTests(unittest.TestCase):
    def test_prepare_output_paths_allows_new_protected_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "prices.csv"
            protected_directory = root / "checkpoint"

            prepared = prepare_output_paths(
                [output],
                [],
                protected_directories=[protected_directory],
            )

            self.assertEqual((output,), prepared)
            self.assertFalse(protected_directory.exists())

    def test_prepare_output_paths_allows_temp_directory_system_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output = root / "prices.csv"
            protected_directory = root / "checkpoint"

            prepared = prepare_output_paths(
                [output],
                [],
                protected_directories=[protected_directory],
            )

            self.assertEqual((output,), prepared)
            self.assertFalse(protected_directory.exists())

    def test_prepare_output_paths_rejects_unexpanded_home_output_before_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            home.mkdir()
            literal_output = root / "~" / "prices.csv"
            literal_output.parent.mkdir()
            original = b"literal output must remain intact\n"
            literal_output.write_bytes(original)
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {"HOME": str(home)}):
                    with self.assertRaisesRegex(
                        ValueError, "path must not use unexpanded home shorthand"
                    ):
                        prepare_output_paths([Path("~") / "prices.csv"], [])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(original, literal_output.read_bytes())

    def test_prepare_output_paths_rejects_unexpanded_home_input_before_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            home.mkdir()
            (home / "prices.csv").write_text("symbol\n000001\n", encoding="utf-8")
            output = root / "output.csv"
            original = b"stale output must remain intact\n"
            output.write_bytes(original)

            with patch.dict(os.environ, {"HOME": str(home)}):
                with self.assertRaisesRegex(
                    ValueError, "path must not use unexpanded home shorthand"
                ):
                    prepare_output_paths([output], [Path("~") / "prices.csv"])

            self.assertEqual(original, output.read_bytes())

    def test_prepare_output_paths_rejects_unexpanded_home_protected_directory_before_cleanup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            home.mkdir()
            output = root / "output.csv"
            original = b"stale output must remain intact\n"
            output.write_bytes(original)

            with patch.dict(os.environ, {"HOME": str(home)}):
                with self.assertRaisesRegex(
                    ValueError, "path must not use unexpanded home shorthand"
                ):
                    prepare_output_paths(
                        [output],
                        [],
                        protected_directories=[Path("~") / "checkpoint"],
                    )

            self.assertEqual(original, output.read_bytes())

    def test_prepare_output_paths_rejects_protected_directory_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            target_directory = root / "checkpoint-target"
            target_directory.mkdir()
            protected_directory = root / "checkpoint"
            protected_directory.symlink_to(target_directory, target_is_directory=True)
            output = root / "prices.csv"
            original = b"stale output must remain intact\n"
            output.write_bytes(original)

            with self.assertRaisesRegex(
                ValueError, "protected directory must not contain symlinks"
            ):
                prepare_output_paths(
                    [output],
                    [],
                    protected_directories=[protected_directory],
                )

            self.assertTrue(protected_directory.is_symlink())
            self.assertTrue(target_directory.is_dir())
            self.assertEqual(original, output.read_bytes())

    def test_prepare_output_paths_rejects_dangling_symlink_in_protected_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            protected_directory = root / "checkpoint"
            protected_directory.mkdir()
            dangling_link = protected_directory / "missing-artifacts"
            dangling_link.symlink_to(root / "missing-target", target_is_directory=True)
            output = root / "prices.csv"
            original = b"stale output must remain intact\n"
            output.write_bytes(original)

            with self.assertRaisesRegex(
                ValueError, "protected directory must not contain symlinks"
            ):
                prepare_output_paths(
                    [output],
                    [],
                    protected_directories=[protected_directory],
                )

            self.assertTrue(dangling_link.is_symlink())
            self.assertEqual(original, output.read_bytes())

    def test_prepare_output_paths_rejects_symlinked_parent_of_new_protected_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            external = root / "external"
            external.mkdir()
            link = root / "checkpoint-link"
            link.symlink_to(external, target_is_directory=True)
            protected_directory = link / "new-checkpoint"
            output = root / "prices.csv"
            original = b"stale output must remain intact\n"
            output.write_bytes(original)

            with self.assertRaisesRegex(
                ValueError, "protected directory must not contain symlinks"
            ):
                prepare_output_paths(
                    [output],
                    [],
                    protected_directories=[protected_directory],
                )

            self.assertFalse((external / "new-checkpoint").exists())
            self.assertEqual(original, output.read_bytes())

    def test_prepare_output_paths_rejects_symlinked_parent_of_existing_protected_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            external = root / "external"
            protected_target = external / "existing-checkpoint"
            protected_target.mkdir(parents=True)
            manifest = protected_target / "manifest.json"
            part = protected_target / "prices_part_00001.csv"
            manifest_original = b"checkpoint manifest must remain intact\n"
            part_original = b"checkpoint part must remain intact\n"
            manifest.write_bytes(manifest_original)
            part.write_bytes(part_original)
            link = root / "checkpoint-link"
            link.symlink_to(external, target_is_directory=True)
            output = root / "prices.csv"
            output_original = b"stale output must remain intact\n"
            output.write_bytes(output_original)

            with self.assertRaisesRegex(
                ValueError, "protected directory must not contain symlinks"
            ):
                prepare_output_paths(
                    [output],
                    [],
                    protected_directories=[link / protected_target.name],
                )

            self.assertEqual(manifest_original, manifest.read_bytes())
            self.assertEqual(part_original, part.read_bytes())
            self.assertEqual(output_original, output.read_bytes())

    def test_prepare_output_paths_preserves_protected_directory_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            protected_directory = root / "checkpoint"
            protected_directory.mkdir()
            output = protected_directory / "stale.json"
            original = b"protected output must remain intact\n"
            output.write_bytes(original)

            with self.assertRaisesRegex(
                ValueError, "output path must not overlap protected directories"
            ):
                prepare_output_paths(
                    [output],
                    [],
                    protected_directories=[protected_directory],
                )

            self.assertEqual(original, output.read_bytes())

    def test_retry_plan_rejects_hardlink_to_input_before_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = root / "selected_symbols.json"
            metadata = root / "history_metadata.json"
            selected_original = b'{"selected_symbols":["000001"]}\n'
            metadata_original = b'{"failed_symbols":[]}\n'
            selected.write_bytes(selected_original)
            metadata.write_bytes(metadata_original)
            output = root / "retry_plan.json"
            os.link(selected, output)
            symbols_output = root / "retry_symbols.txt"
            symbols_original = b"safe retry output\n"
            symbols_output.write_bytes(symbols_original)

            with patch.object(retry_symbols, "read_json") as read_json:
                with self.assertRaisesRegex(
                    ValueError, "output path must differ from input paths"
                ):
                    retry_symbols.main(
                        [
                            "--selected-symbols",
                            str(selected),
                            "--history-metadata",
                            str(metadata),
                            "--output",
                            str(output),
                            "--symbols-output",
                            str(symbols_output),
                        ]
                    )

            self.assertFalse(read_json.called)
            self.assertEqual(selected_original, selected.read_bytes())
            self.assertEqual(metadata_original, metadata.read_bytes())
            self.assertEqual(symbols_original, symbols_output.read_bytes())
            self.assertTrue(os.path.samefile(selected, output))

    def test_incremental_plan_rejects_hardlink_to_input_before_readers_or_pandas(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "universe.csv"
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            spot_original = b"symbol\n000001\n"
            prices_original = b"symbol,date\n000001,2026-07-01\n"
            metadata_original = b'{"symbols":[]}\n'
            spot.write_bytes(spot_original)
            prices.write_bytes(prices_original)
            metadata.write_bytes(metadata_original)
            output = root / "incremental_plan.json"
            os.link(prices, output)
            symbols_output = root / "fetch_symbols.txt"
            symbols_original = b"safe symbols output\n"
            symbols_output.write_bytes(symbols_original)

            with (
                patch.object(incremental_plan, "read_universe_symbols") as read_spot,
                patch.object(incremental_plan, "read_price_stats") as read_prices,
                patch.object(incremental_plan, "read_json") as read_metadata,
                patch.object(incremental_plan, "pandas_module") as pandas_loader,
            ):
                with self.assertRaisesRegex(
                    ValueError, "output path must differ from input paths"
                ):
                    incremental_plan.main(
                        [
                            "--spot-input",
                            str(spot),
                            "--prices-input",
                            str(prices),
                            "--history-metadata",
                            str(metadata),
                            "--target-end-date",
                            "2026-07-24",
                            "--output",
                            str(output),
                            "--symbols-output",
                            str(symbols_output),
                        ]
                    )

            self.assertFalse(read_spot.called)
            self.assertFalse(read_prices.called)
            self.assertFalse(read_metadata.called)
            self.assertFalse(pandas_loader.called)
            self.assertEqual(spot_original, spot.read_bytes())
            self.assertEqual(prices_original, prices.read_bytes())
            self.assertEqual(metadata_original, metadata.read_bytes())
            self.assertEqual(symbols_original, symbols_output.read_bytes())
            self.assertTrue(os.path.samefile(prices, output))

    def test_clean_pool_rejects_hardlink_to_input_before_readers_or_pandas(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            prices_original = b"symbol,date,close\n000001,2026-07-01,10.0\n"
            metadata_original = b'{"symbols":[]}\n'
            prices.write_bytes(prices_original)
            metadata.write_bytes(metadata_original)
            output = root / "clean_prices.csv"
            os.link(prices, output)
            metadata_output = root / "clean_metadata.json"
            report_output = root / "clean_report.json"
            metadata_output_original = b"safe metadata output\n"
            report_output_original = b"safe report output\n"
            metadata_output.write_bytes(metadata_output_original)
            report_output.write_bytes(report_output_original)

            with (
                patch.object(clean_history_pool_cli, "read_json") as read_json,
                patch.object(clean_history_pool_cli, "read_frame") as read_frame,
            ):
                with self.assertRaisesRegex(
                    ValueError, "output path must differ from input paths"
                ):
                    clean_history_pool_cli.main(
                        [
                            "--prices-input",
                            str(prices),
                            "--history-metadata",
                            str(metadata),
                            "--output",
                            str(output),
                            "--metadata-output",
                            str(metadata_output),
                            "--report-output",
                            str(report_output),
                        ]
                    )

            self.assertFalse(read_json.called)
            self.assertFalse(read_frame.called)
            self.assertEqual(prices_original, prices.read_bytes())
            self.assertEqual(metadata_original, metadata.read_bytes())
            self.assertEqual(metadata_output_original, metadata_output.read_bytes())
            self.assertEqual(report_output_original, report_output.read_bytes())
            self.assertTrue(os.path.samefile(prices, output))

    def test_retry_plan_rejects_hardlinked_outputs_before_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = root / "selected_symbols.json"
            metadata = root / "history_metadata.json"
            selected_original = b'{"selected_symbols":["000001"]}\n'
            metadata_original = b'{"failed_symbols":[]}\n'
            selected.write_bytes(selected_original)
            metadata.write_bytes(metadata_original)
            output = root / "retry_plan.json"
            output_original = b"existing output must remain intact\n"
            output.write_bytes(output_original)
            symbols_output = root / "retry_symbols.txt"
            os.link(output, symbols_output)

            with patch.object(retry_symbols, "read_json") as read_json:
                with self.assertRaisesRegex(
                    ValueError, "output paths must be distinct"
                ):
                    retry_symbols.main(
                        [
                            "--selected-symbols",
                            str(selected),
                            "--history-metadata",
                            str(metadata),
                            "--output",
                            str(output),
                            "--symbols-output",
                            str(symbols_output),
                        ]
                    )

            self.assertFalse(read_json.called)
            self.assertEqual(selected_original, selected.read_bytes())
            self.assertEqual(metadata_original, metadata.read_bytes())
            self.assertEqual(output_original, output.read_bytes())
            self.assertTrue(os.path.samefile(output, symbols_output))


if __name__ == "__main__":
    unittest.main()
