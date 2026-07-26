from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import lib.fetch.zzshare_a_share_checkpoint as checkpoint  # noqa: E402


def fingerprint(path: Path) -> dict[str, object]:
    return {
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def checkpoint_args(path: Path) -> object:
    return types.SimpleNamespace(
        checkpoint_dir=str(path),
        checkpoint_batch_size=1,
        resume_from_checkpoint=False,
        http_url="https://example.test",
        start_date="2026-07-01",
        end_date="2026-07-09",
        fields="all",
        adjust="qfq",
        limit=1000,
        max_pages=10,
        timeout_seconds=10.0,
        request_interval_seconds=0.0,
        max_concurrent_symbol_requests=1,
        max_rate_limit_sleep_seconds=120.0,
        max_429_events=3,
        max_runtime_seconds=900.0,
        non_trading_policy="fail",
        drop_invalid_rows=False,
    )


class ZzshareCheckpointIntegrityTests(unittest.TestCase):
    def test_completed_record_rejects_same_row_count_content_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            part = root / "prices_part_00001.csv"
            part.write_text(
                "symbol,date,close\n000001,2026-07-09,10.0\n",
                encoding="utf-8",
            )
            expected = fingerprint(part)
            part.write_text(
                "symbol,date,close\n000001,2026-07-09,99.0\n",
                encoding="utf-8",
            )
            state = {
                "dir": root,
                "manifest": {
                    "parts": [part.name],
                    "part_artifacts": {part.name: expected},
                    "symbols": {
                        "000001": {
                            "status": "completed",
                            "rows": 1,
                            "part": part.name,
                            "metadata": {"symbol": "000001", "rows": 1},
                        }
                    },
                },
                "part_symbol_cache": {},
                "part_fingerprint_cache": {},
                "part_integrity_cache": {},
                "integrity_issues": [],
            }

            record = checkpoint.completed_checkpoint_record(state, "000001")

        self.assertIsNone(record)
        self.assertEqual(
            "completed_record_part_fingerprint_mismatch",
            state["integrity_issues"][0]["issue"],
        )

    def test_flush_records_part_fingerprint_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state = checkpoint.prepare_checkpoint(checkpoint_args(root))
            self.assertIsNotNone(state)
            batch = checkpoint.empty_checkpoint_batch()
            rows = [{"symbol": "000001", "date": "2026-07-09", "close": 10.0}]
            checkpoint.append_checkpoint_record(
                state,
                batch,
                "000001",
                rows,
                {"symbol": "000001", "rows": 1},
                None,
                False,
            )

            checkpoint.flush_checkpoint_batch(
                state,
                batch,
                pd,
                ["symbol", "date", "close"],
            )
            saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            part = saved["parts"][0]
            actual = fingerprint(root / part)

        self.assertEqual(actual, saved["part_artifacts"][part])

    def test_prepare_checkpoint_rejects_unexpanded_home_shorthand(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            home.mkdir()
            literal_checkpoint = root / "~" / "checkpoint"
            literal_checkpoint.mkdir(parents=True)
            manifest = literal_checkpoint / "manifest.json"
            original = b"checkpoint manifest must remain intact\n"
            manifest.write_bytes(original)
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with self.assertRaisesRegex(
                    ValueError, "path must not use unexpanded home shorthand"
                ):
                    checkpoint.prepare_checkpoint(
                        checkpoint_args(Path("~") / "checkpoint")
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(original, manifest.read_bytes())

    def test_prepare_checkpoint_resets_verified_directory_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_dir = root / "checkpoint"
            checkpoint_dir.mkdir()
            old_part = checkpoint_dir / "prices_part_00001.csv"
            old_manifest = checkpoint_dir / "manifest.json"
            unrelated = checkpoint_dir / "notes.txt"
            old_part.write_text("symbol\n000001\n", encoding="utf-8")
            old_manifest.write_text('{"symbols":{}}\n', encoding="utf-8")
            unrelated.write_text("keep\n", encoding="utf-8")

            state = checkpoint.prepare_checkpoint(checkpoint_args(checkpoint_dir))

            self.assertIsNotNone(state)
            self.assertFalse(old_part.exists())
            self.assertTrue((checkpoint_dir / "manifest.json").is_file())
            self.assertEqual("keep\n", unrelated.read_text(encoding="utf-8"))

    def test_prepare_checkpoint_rejects_symlinked_parent_before_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            external = root / "external"
            checkpoint_target = external / "checkpoint"
            checkpoint_target.mkdir(parents=True)
            manifest = checkpoint_target / "manifest.json"
            part = checkpoint_target / "prices_part_00001.csv"
            manifest_original = b"checkpoint manifest must remain intact\n"
            part_original = b"checkpoint part must remain intact\n"
            manifest.write_bytes(manifest_original)
            part.write_bytes(part_original)
            checkpoint_link = root / "checkpoint-link"
            checkpoint_link.symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(
                ValueError, "protected directory must not contain symlinks"
            ):
                checkpoint.prepare_checkpoint(
                    checkpoint_args(checkpoint_link / checkpoint_target.name)
                )

            self.assertEqual(manifest_original, manifest.read_bytes())
            self.assertEqual(part_original, part.read_bytes())

    def test_reset_checkpoint_dir_rejects_symlinked_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            external = root / "external"
            checkpoint_target = external / "checkpoint"
            checkpoint_target.mkdir(parents=True)
            manifest = checkpoint_target / "manifest.json"
            part = checkpoint_target / "prices_part_00001.csv"
            manifest_original = b"checkpoint manifest must remain intact\n"
            part_original = b"checkpoint part must remain intact\n"
            manifest.write_bytes(manifest_original)
            part.write_bytes(part_original)
            checkpoint_link = root / "checkpoint-link"
            checkpoint_link.symlink_to(external, target_is_directory=True)

            with self.assertRaisesRegex(
                ValueError, "protected directory must not contain symlinks"
            ):
                checkpoint.reset_checkpoint_dir(
                    checkpoint_link / checkpoint_target.name
                )

            self.assertEqual(manifest_original, manifest.read_bytes())
            self.assertEqual(part_original, part.read_bytes())


if __name__ == "__main__":
    unittest.main()
