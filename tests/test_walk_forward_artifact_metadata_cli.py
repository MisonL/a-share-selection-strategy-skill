from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_walk_forward_artifact_cli import build_run, call_cli  # noqa: E402


class WalkForwardArtifactMetadataCliTests(unittest.TestCase):
    def test_cli_rejects_dropped_invalid_rows_without_explicit_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            write_metadata(root, invalid_rows=10, dropped_invalid_rows=10, raw_non_trading_rows=10)

            code, _stdout, stderr = call_cli(root, root / "artifact_validation.json")

        self.assertEqual(3, code)
        self.assertIn("metadata_invalid_rows=10", stderr)

    def test_cli_allows_explicitly_dropped_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            write_metadata(root, invalid_rows=10, dropped_invalid_rows=10, raw_non_trading_rows=10)

            code, _stdout, stderr = call_cli(
                root,
                root / "artifact_validation.json",
                ["--allow-dropped-invalid-rows"],
            )

        self.assertEqual(0, code)
        self.assertEqual("", stderr)

    def test_cli_rejects_dropped_rows_without_invalid_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            write_metadata(root, invalid_rows=0, dropped_invalid_rows=10)

            code, _stdout, stderr = call_cli(
                root,
                root / "artifact_validation.json",
                ["--allow-dropped-invalid-rows"],
            )

        self.assertEqual(3, code)
        self.assertIn("metadata_invalid_rows=0 dropped_invalid_rows=10", stderr)

    def test_cli_uses_distinct_raw_invalid_rows_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = build_run(Path(tmpdir))
            write_metadata(root, invalid_rows=0, dropped_invalid_rows=0, raw_non_trading_rows=5)

            code, _stdout, stderr = call_cli(
                root,
                root / "artifact_validation.json",
                ["--allow-dropped-invalid-rows"],
            )

        self.assertEqual(3, code)
        self.assertIn("metadata_raw_invalid_rows=5 invalid_rows=0", stderr)


def write_metadata(root: Path, **updates: object) -> None:
    path = root / "metadata.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    metadata.update(updates)
    path.write_text(json.dumps(metadata), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
