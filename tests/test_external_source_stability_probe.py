from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import probe_external_source_stability as probe  # noqa: E402
from lib.gates import external_source_evidence_archive as archive  # noqa: E402
from lib.fetch.pytdx_a_share import DEFAULT_HOST, DEFAULT_PORT  # noqa: E402


class ExternalSourceStabilityProbeTests(unittest.TestCase):
    def test_probe_accepts_all_sources_and_keeps_long_term_claim_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=FakeExecutor(),
            )

        summary = manifest["summary"]
        self.assertEqual(7, summary["total_runs"])
        self.assertEqual(7, summary["passed_runs"])
        self.assertEqual(True, summary["all_sources_all_iterations_passed"])
        self.assertEqual("not_proven", summary["long_term_stability_claim"])
        self.assertEqual(
            "current_window_parameters_network_only",
            summary["short_window_claim_boundary"],
        )
        self.assertEqual({}, summary["sources"]["akshare"]["observation_failed_checks"])
        self.assertEqual([], probe.strict_errors(manifest))

    def test_print_summary_keeps_long_term_claim_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=FakeExecutor(),
            )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            probe.print_summary(manifest)

        self.assertIn("all_sources_all_iterations_passed=True", stdout.getvalue())
        self.assertIn("long_term_stability_claim=not_proven", stdout.getvalue())
        self.assertIn(
            "short_window_claim_boundary=current_window_parameters_network_only",
            stdout.getvalue(),
        )

    def test_akshare_fallback_is_observation_not_hard_failure(self) -> None:
        metadata = akshare_metadata(fallback=True)
        checks = probe.source_checks("akshare", metadata)

        hist_provider = [item for item in checks if item["name"] == "hist_provider_clean"][0]
        self.assertEqual(False, hist_provider["passed"])
        self.assertEqual(False, hist_provider["required"])
        self.assertEqual([], [item for item in probe.required_checks(checks) if not item["passed"]])
        source_result = {"source": "akshare", "checks": checks, "passed": True}
        summary = probe.build_summary({"iterations": 1, "results": [source_result]})
        self.assertEqual({"hist_provider_clean": 1}, summary["sources"]["akshare"]["observation_failed_checks"])

    def test_akshare_probe_command_keeps_fallback_as_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            specs = {
                spec.name: spec
                for spec in probe.source_specs(args, output / "runs" / "iteration-1")
            }

        self.assertNotIn("--fail-on-fetch-error", specs["akshare"].command)
        self.assertIn("--retry-interval-seconds", specs["eastmoney_spot"].command)

    def test_pytdx_probe_defaults_and_explicit_endpoint_are_forwarded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            defaults = probe.build_parser().parse_args(
                ["--output-dir", str(output / "runs"), "--summary-output", str(output / "summary.json")]
            )
            self.assertEqual(DEFAULT_HOST, defaults.pytdx_host)
            self.assertEqual(DEFAULT_PORT, defaults.pytdx_port)
            default_specs = {
                spec.name: spec
                for spec in probe.source_specs(defaults, output / "runs" / "iteration-default")
            }

            args = args_for(output)
            args.pytdx_host = "198.51.100.42"
            args.pytdx_port = 7710
            specs = {
                spec.name: spec
                for spec in probe.source_specs(args, output / "runs" / "iteration-1")
            }

        default_command = default_specs["pytdx"].command
        self.assertEqual(DEFAULT_HOST, default_command[default_command.index("--host") + 1])
        self.assertEqual(str(DEFAULT_PORT), default_command[default_command.index("--port") + 1])

        command = specs["pytdx"].command
        self.assertEqual("198.51.100.42", command[command.index("--host") + 1])
        self.assertEqual("7710", command[command.index("--port") + 1])

    def test_baostock_adjustflag_must_match_requested_adjust(self) -> None:
        command = ["python", "fetch_baostock_a_share.py", "--adjust", "2"]
        metadata = valid_metadata("baostock")

        mismatch = probe.source_checks("baostock", metadata, command)
        adjust_check = [item for item in mismatch if item["name"] == "adjustflag_matches_request"][0]
        self.assertEqual(False, adjust_check["passed"])

        metadata["adjustflag"] = "2"
        matched = probe.source_checks("baostock", metadata, command)
        adjust_check = [item for item in matched if item["name"] == "adjustflag_matches_request"][0]
        self.assertEqual(True, adjust_check["passed"])

    def test_baostock_adjustflag_missing_value_does_not_raise(self) -> None:
        command = ["python", "fetch_baostock_a_share.py", "--adjust"]
        metadata = valid_metadata("baostock")

        checks = probe.source_checks("baostock", metadata, command)
        adjust_check = [item for item in checks if item["name"] == "adjustflag_matches_request"][0]

        self.assertEqual(False, adjust_check["passed"])

    def test_zzshare_limit_and_truncation_checks_are_required(self) -> None:
        command = [
            "python",
            "fetch_zzshare_a_share.py",
            "--limit",
            "500",
            "--max-pages",
            "3",
        ]
        metadata = valid_metadata("zzshare")
        metadata["limit"] = 500
        metadata["max_pages"] = 3

        checks = probe.source_checks("zzshare", metadata, command)
        by_name = {item["name"]: item for item in checks}

        self.assertEqual(True, by_name["limit_matches_request"]["passed"])
        self.assertEqual(True, by_name["max_pages_matches_request"]["passed"])
        self.assertEqual(True, by_name["possibly_truncated_symbols_empty"]["passed"])

        metadata["possibly_truncated_symbols"] = ["000001"]
        failed_checks = probe.source_checks("zzshare", metadata, command)
        by_name = {item["name"]: item for item in failed_checks}

        self.assertEqual(False, by_name["possibly_truncated_symbols_empty"]["passed"])
        self.assertIn(
            by_name["possibly_truncated_symbols_empty"],
            probe.required_checks(failed_checks),
        )

    def test_pytdx_disclosure_checks_are_required(self) -> None:
        command = ["python", "fetch_pytdx_a_share.py", "--max-pages", "1"]
        metadata = valid_metadata("pytdx")

        checks = probe.source_checks("pytdx", metadata, command)
        by_name = {item["name"]: item for item in checks}

        self.assertEqual(True, by_name["missing_provider_fields_disclosed"]["passed"])
        self.assertEqual(True, by_name["license_boundary_disclosed"]["passed"])
        self.assertIn(
            by_name["missing_provider_fields_disclosed"],
            probe.required_checks(checks),
        )

        metadata["missing_provider_fields"] = ["name"]
        failed_checks = probe.source_checks("pytdx", metadata, command)
        by_name = {item["name"]: item for item in failed_checks}
        self.assertEqual(False, by_name["missing_provider_fields_disclosed"]["passed"])

    def test_cli_returns_strict_error_when_required_source_fails(self) -> None:
        original_run = probe.run_command
        probe.run_command = FakeExecutor(fail_sources={"yfinance"})
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir)
                code = probe.main(
                    [
                        "--output-dir",
                        str(output / "runs"),
                        "--summary-output",
                        str(output / "summary.json"),
                        "--iterations",
                        "1",
                    ]
                )
                summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        finally:
            probe.run_command = original_run

        self.assertEqual(3, code)
        self.assertEqual(False, summary["summary"]["sources"]["yfinance"]["all_passed"])
        self.assertEqual("not_proven", summary["summary"]["long_term_stability_claim"])
        self.assertEqual(
            "current_window_parameters_network_only",
            summary["summary"]["short_window_claim_boundary"],
        )

    def test_probe_records_command_timeout_as_failed_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            args.command_timeout_seconds = 1.0
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=TimeoutExecutor("yfinance"),
            )

        yfinance = [item for item in manifest["results"] if item["source"] == "yfinance"][0]
        self.assertEqual(124, yfinance["returncode"])
        self.assertIn("timed out", yfinance["stderr"])
        self.assertEqual(False, yfinance["passed"])
        self.assertEqual(["yfinance_passed_runs=0 runs=1"], probe.strict_errors(manifest))

    def test_parser_rejects_non_finite_timeout_and_interval_values(self) -> None:
        parser = probe.build_parser()
        required = ["--output-dir", "runs", "--summary-output", "summary.json"]
        options = [
            "--eastmoney-timeout-seconds",
            "--eastmoney-retry-interval-seconds",
            "--eastmoney-request-interval-seconds",
            "--baostock-universe-retry-interval-seconds",
            "--pytdx-timeout-seconds",
            "--yfinance-timeout-seconds",
            "--command-timeout-seconds",
            "--zzshare-timeout-seconds",
            "--zzshare-request-interval-seconds",
        ]
        for option in options:
            for value in ("nan", "inf", "-inf"):
                with self.subTest(option=option, value=value), self.assertRaises(SystemExit):
                    with redirect_stderr(io.StringIO()):
                        parser.parse_args([*required, option, value])

    def test_command_timeout_rejects_mutated_non_finite_values(self) -> None:
        args = args_for(Path("/tmp"))
        for value in (float("nan"), float("inf"), float("-inf"), -0.1):
            with self.subTest(value=value):
                args.command_timeout_seconds = value
                with self.assertRaisesRegex(ValueError, "finite non-negative"):
                    probe.command_timeout(args)

    def test_archive_contains_control_plane_evidence_not_price_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=FakeExecutor(),
            )
            first_result = manifest["results"][0]
            price_output = Path(str(first_result["output"]))
            price_output.parent.mkdir(parents=True, exist_ok=True)
            price_output.write_text("date,close\n2026-01-01,1\n", encoding="utf-8")
            archive_dir = output / "durable-evidence"

            probe.archive_evidence(manifest, archive_dir)

            archived_manifest = json.loads((archive_dir / "summary.json").read_text(encoding="utf-8"))
            integrity_manifest = archive.verify_archive_integrity(archive_dir)
            first_archive = archive_dir / "results" / "001-eastmoney_spot"
            self.assertEqual("not_proven", archived_manifest["long_term_stability_claim"])
            self.assertEqual(manifest["summary"], archived_manifest["summary"])
            self.assertEqual(archive.ARCHIVE_SCHEMA_VERSION, integrity_manifest["schema_version"])
            self.assertEqual(
                archive.ARCHIVE_DIRECTORY_MODE,
                stat.S_IMODE(archive_dir.stat().st_mode),
            )
            files = integrity_manifest["files"]
            self.assertTrue(all(len(record["sha256"]) == 64 for record in files))
            self.assertIn("summary.json", {record["path"] for record in files})
            self.assertEqual(7, len(integrity_manifest["source_records"]))
            self.assertEqual(0, integrity_manifest["source_records"][0]["result_index"])
            self.assertTrue((first_archive / "metadata.json").is_file())
            self.assertEqual("eastmoney_spot ok", (first_archive / "stdout.txt").read_text(encoding="utf-8"))
            self.assertEqual("", (first_archive / "stderr.txt").read_text(encoding="utf-8"))
            self.assertFalse(any(path.suffix in {".csv", ".parquet", ".pq"} for path in archive_dir.rglob("*")))

    def test_archive_integrity_rejects_tampered_missing_and_extra_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            args = args_for(output)
            manifest = probe.initial_manifest(args)
            probe.run_probe(
                args,
                output_dir=output / "runs",
                manifest=manifest,
                executor=FakeExecutor(),
            )
            archive_dir = output / "durable-evidence"
            probe.archive_evidence(manifest, archive_dir)
            payload = archive_dir / "results" / "001-eastmoney_spot" / "stdout.txt"

            payload.write_text("X" * len(payload.read_text(encoding="utf-8")), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                archive.verify_archive_integrity(archive_dir)

            probe.archive_evidence(manifest, output / "fresh-evidence")
            fresh_archive = output / "fresh-evidence"
            (fresh_archive / "results" / "001-eastmoney_spot" / "stdout.txt").unlink()
            with self.assertRaisesRegex(ValueError, "missing or unsafe"):
                archive.verify_archive_integrity(fresh_archive)

            probe.archive_evidence(manifest, output / "extra-evidence")
            extra_archive = output / "extra-evidence"
            (extra_archive / "unexpected.txt").write_text("extra", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "do not match"):
                archive.verify_archive_integrity(extra_archive)

    def test_archive_integrity_rejects_non_object_manifest_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive_dir = root / "evidence"
            archive_dir.mkdir(mode=archive.ARCHIVE_DIRECTORY_MODE)
            (archive_dir / "archive_manifest.json").write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "root must be an object"):
                archive.verify_archive_integrity(archive_dir)

            if os.name == "posix":
                probe.archive_evidence(probe.initial_manifest(args_for(root)), root / "safe-evidence")
                safe_archive = root / "safe-evidence"
                target = safe_archive / "results" / "001-eastmoney_spot" / "stdout.txt"
                (safe_archive / "unexpected-link").symlink_to(target)
                with self.assertRaisesRegex(ValueError, "must not contain symlinks"):
                    archive.verify_archive_integrity(safe_archive)

    def test_archive_integrity_rejects_missing_metadata_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifest = probe.initial_manifest(args_for(root))
            probe.run_probe(
                args_for(root),
                output_dir=root / "runs",
                manifest=manifest,
                executor=FakeExecutor(),
            )
            archive_dir = root / "evidence"
            probe.archive_evidence(manifest, archive_dir)
            manifest_path = archive_dir / "archive_manifest.json"
            index = json.loads(manifest_path.read_text(encoding="utf-8"))
            index["source_records"][0]["metadata"] = None
            manifest_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "archive source payload mapping"):
                archive.verify_archive_integrity(archive_dir)

    def test_archive_rejects_dangling_symlink_destination_before_probe(self) -> None:
        if os.name != "posix":
            self.skipTest("creating a dangling symlink is POSIX-specific")
        original_run = probe.run_command
        probe.run_command = fail_if_called
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                archive_dir = root / "durable-evidence"
                redirected = root / "redirected" / "archive"
                archive_dir.symlink_to(redirected)

                with self.assertRaisesRegex(ValueError, "must not already exist"):
                    archive.validate_archive_destination(
                        archive_dir,
                        root / "runs",
                        root / "summary.json",
                    )
                with self.assertRaisesRegex(ValueError, "must not already exist"):
                    archive.archive_evidence(
                        probe.initial_manifest(args_for(root)),
                        archive_dir,
                    )

                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = probe.main(
                        [
                            "--output-dir",
                            str(root / "runs"),
                            "--summary-output",
                            str(root / "summary.json"),
                            "--archive-dir",
                            str(archive_dir),
                        ]
                    )

                self.assertEqual(2, code)
                self.assertIn("code=archive_failed", stderr.getvalue())
                self.assertTrue(archive_dir.is_symlink())
                self.assertFalse(redirected.exists())
                self.assertTrue((root / "summary.json").is_file())
        finally:
            probe.run_command = original_run

    def test_archive_failure_reports_temporary_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive_dir = root / "durable-evidence"
            manifest = probe.initial_manifest(args_for(root))
            with (
                patch.object(
                    archive,
                    "build_archive_manifest",
                    side_effect=ValueError("simulated archive build failure"),
                ),
                patch.object(
                    archive.shutil,
                    "rmtree",
                    side_effect=OSError("simulated cleanup failure"),
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "simulated archive build failure; temporary archive cleanup failed",
                ) as raised,
            ):
                archive.archive_evidence(manifest, archive_dir)

        self.assertIsInstance(raised.exception.__cause__, ValueError)
        self.assertFalse(archive_dir.exists())

    def test_source_record_redacts_persisted_command_output_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spec = probe.SourceSpec(
                name="yfinance",
                command=[
                    "python",
                    "fetch_yfinance_ohlcv.py",
                    "--token",
                    "probe-secret-token",
                    "--privateKey",
                    "probe-secret-private-command",
                    "--clientsecret",
                    "probe-secret-compact-client-command",
                    "--refreshtoken=probe-secret-compact-refresh-command",
                    "--sessionid",
                    "probe-secret-compact-session-command",
                    "--setcookie=probe-secret-compact-cookie-command",
                    "--secretkey",
                    "probe-secret-compact-secret-key-command",
                    "--authtoken=probe-secret-compact-auth-token-command",
                    "--sessiontoken",
                    "probe-secret-compact-session-token-command",
                    "--clientSecretprobe-secret-command-flag",
                    "probe-secret-embedded-command-value",
                    "--http-url=https://example.test/data?api_key=probe-secret-key&privateKey=probe-secret-private-url&sessionId=probe-secret-session-url&clientSecretprobesecretvalue=probe-secret-query-key&set_cookie=probe-secret-query-cookie",
                ],
                metadata_path=root / "metadata.json",
                output_path=root / "prices.csv",
            )
            metadata = valid_metadata("yfinance")
            metadata["provider_error"] = (
                "Authorization: Bearer probe-secret-bearer\n"
                "Cookie: session=probe-secret-cookie-session; "
                "theme=probe-secret-cookie-theme\n"
                "set_cookie: session=probe-secret-snake-cookie-session; "
                "theme=probe-secret-snake-cookie-theme\n"
                "  continuation=probe-secret-snake-cookie-continuation"
                "\n\"Cookie\": session=probe-secret-quoted-cookie-session; "
                "theme=probe-secret-quoted-cookie-theme, \"safe\": \"retained\""
            )
            metadata["Authorization"] = "Bearer probe-secret-header"
            metadata["api_key"] = "probe-secret-api-key"
            metadata["clientSecret"] = "probe-secret-client-secret"
            metadata["PrivateKey"] = "probe-secret-private-key"
            metadata["set_cookie"] = "probe-secret-metadata-set-cookie"
            metadata["cookies"] = "probe-secret-metadata-cookies"
            metadata["clientSecretprobesecretvalue"] = "probe-secret-metadata-key"
            metadata["Authorization: Bearer probe-secret-metadata-key"] = "metadata"
            metadata["api_key_probe-secret-metadata-key"] = "metadata"
            metadata["nested"] = {
                "url": "https://example.test/?token=probe-secret-url",
                "token": "probe-secret-nested-token",
                "bearerToken": "probe-secret-bearer-token",
                "refreshToken": "probe-secret-refresh-token",
                "sessionId": "probe-secret-session-id",
            }
            result = subprocess.CompletedProcess(
                spec.command,
                0,
                stdout=(
                    "API_KEY=probe-secret-stdout "
                    "privateKey=probe-secret-private-stdout "
                    "--tokenConfigured true "
                    "Cookie=session=probe-secret-cookie-assignment; "
                    "theme=probe-secret-cookie-assignment-theme\n"
                    "cookies=one=probe-secret-stdout-cookie-one, "
                    "two=probe-secret-stdout-cookie-two\n"
                    "Cookie=session=probe-secret-stdout-ampersand-one&"
                    "probe-secret-stdout-ampersand-two\n"
                    "\"cookies\": one=probe-secret-stdout-quoted-cookie-one, "
                    "two=probe-secret-stdout-quoted-cookie-two, \"safe\": \"retained\""
                ),
                stderr=(
                    "password=probe-secret-stderr "
                    "sessionId=probe-secret-session-stderr "
                    "--token_configured false "
                    "Set-Cookie: refresh=probe-secret-set-cookie; HttpOnly\n"
                    "Set_Cookie: refresh=probe-secret-stderr-snake-cookie; HttpOnly\n"
                    "'Set_Cookie': refresh=probe-secret-stderr-quoted-cookie; "
                    "theme=probe-secret-stderr-quoted-cookie-theme, 'safe': 'retained'"
                ),
            )

            spec.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            record = probe.source_record(spec, result, metadata)
            self.assertIn("--tokenConfigured [REDACTED]", record["stdout"])
            self.assertIn("--token_configured [REDACTED]", record["stderr"])
            archive_dir = root / "durable-evidence"
            archive.archive_evidence({"results": [record]}, archive_dir)

            persisted = (archive_dir / "summary.json").read_text(encoding="utf-8")
            archived_metadata = (archive_dir / "results" / "001-yfinance" / "metadata.json").read_text(
                encoding="utf-8"
            )

        for secret in (
            "probe-secret-token",
            "probe-secret-private-command",
            "probe-secret-compact-client-command",
            "probe-secret-compact-refresh-command",
            "probe-secret-compact-session-command",
            "probe-secret-compact-cookie-command",
            "probe-secret-compact-secret-key-command",
            "probe-secret-compact-auth-token-command",
            "probe-secret-compact-session-token-command",
            "probe-secret-command-flag",
            "probe-secret-embedded-command-value",
            "probe-secret-key",
            "probe-secret-private-url",
            "probe-secret-session-url",
            "clientSecretprobesecretvalue",
            "probe-secret-query-key",
            "probe-secret-query-cookie",
            "probe-secret-bearer",
            "probe-secret-cookie-session",
            "probe-secret-cookie-theme",
            "probe-secret-header",
            "probe-secret-api-key",
            "probe-secret-client-secret",
            "probe-secret-private-key",
            "probe-secret-metadata-set-cookie",
            "probe-secret-metadata-cookies",
            "probe-secret-metadata-key",
            "probe-secret-metadata-key",
            "probe-secret-url",
            "probe-secret-nested-token",
            "probe-secret-bearer-token",
            "probe-secret-refresh-token",
            "probe-secret-session-id",
            "probe-secret-stdout",
            "probe-secret-private-stdout",
            "probe-secret-cookie-assignment",
            "probe-secret-cookie-assignment-theme",
            "probe-secret-stdout-cookie-one",
            "probe-secret-stdout-cookie-two",
            "probe-secret-stdout-ampersand-one",
            "probe-secret-stdout-ampersand-two",
            "probe-secret-stderr",
            "probe-secret-session-stderr",
            "probe-secret-set-cookie",
            "probe-secret-stderr-snake-cookie",
            "probe-secret-snake-cookie-session",
            "probe-secret-snake-cookie-theme",
            "probe-secret-snake-cookie-continuation",
            "probe-secret-quoted-cookie-session",
            "probe-secret-quoted-cookie-theme",
            "probe-secret-stdout-quoted-cookie-one",
            "probe-secret-stdout-quoted-cookie-two",
            "probe-secret-stderr-quoted-cookie",
            "probe-secret-stderr-quoted-cookie-theme",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, persisted)
                self.assertNotIn(secret, archived_metadata)
        self.assertIn("[REDACTED]", persisted)
        self.assertIn("[REDACTED]", archived_metadata)

    def test_sanitize_persisted_mapping_redacts_key_names_and_preserves_collisions(self) -> None:
        first = {
            "Authorization: Bearer probe-secret-beta": "beta",
            "Authorization: Bearer probe-secret-alpha": "alpha",
            "api_key_probe-secret-beta": "beta",
            "api_key_probe-secret-alpha": "alpha",
            "token": "probe-secret-token-value",
            "token_configured": False,
            "x-api-key": "probe-secret-api-key-value",
            "auth_token": "probe-secret-auth-token-value",
            "nested": {"api_key": "probe-secret-nested-value"},
        }
        second = dict(reversed(list(first.items())))

        first_sanitized = probe.sanitize_persisted_value(first)
        second_sanitized = probe.sanitize_persisted_value(second)

        self.assertEqual(first_sanitized, second_sanitized)
        authorization_keys = sorted(
            key for key in first_sanitized if key.startswith("Authorization: Bearer")
        )
        self.assertEqual(
            [
                "Authorization: Bearer [REDACTED]",
                "Authorization: Bearer [REDACTED] [duplicate 2]",
            ],
            authorization_keys,
        )
        self.assertEqual(
            {"[REDACTED]"},
            {first_sanitized[key] for key in authorization_keys},
        )
        encoded_key_names = sorted(
            key for key in first_sanitized if key.startswith("[REDACTED] key")
        )
        self.assertEqual(
            [
                "[REDACTED] key",
                "[REDACTED] key [duplicate 2]",
                "[REDACTED] key [duplicate 3]",
                "[REDACTED] key [duplicate 4]",
            ],
            encoded_key_names,
        )
        self.assertEqual(
            {"[REDACTED]"},
            {first_sanitized[key] for key in encoded_key_names},
        )
        self.assertEqual("[REDACTED]", first_sanitized["token"])
        self.assertEqual(False, first_sanitized["token_configured"])
        self.assertEqual("[REDACTED]", first_sanitized["nested"]["api_key"])
        self.assertEqual(
            {"token_configured": "[REDACTED]"},
            probe.sanitize_persisted_value(
                {"token_configured": "probe-secret-invalid-status"}
            ),
        )
        for secret in (
            "probe-secret-alpha",
            "probe-secret-beta",
            "api_key_probe-secret-alpha",
            "api_key_probe-secret-beta",
            "probe-secret-token-value",
            "probe-secret-invalid-status",
            "probe-secret-api-key-value",
            "probe-secret-auth-token-value",
            "probe-secret-nested-value",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, str(first_sanitized))

    def test_cli_omits_archive_when_archive_dir_is_not_requested(self) -> None:
        original_run = probe.run_command
        probe.run_command = FakeExecutor()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir)
                code = probe.main(
                    [
                        "--output-dir",
                        str(output / "runs"),
                        "--summary-output",
                        str(output / "summary.json"),
                        "--iterations",
                        "1",
                    ]
                )
                self.assertEqual(0, code)
                self.assertEqual([output / "runs", output / "summary.json"], sorted(output.iterdir()))
        finally:
            probe.run_command = original_run

    def test_cli_rejects_existing_or_overlapping_archive_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            existing = output / "existing-archive"
            existing.mkdir()
            for archive_dir in (
                output / "runs",
                output / "runs" / "archive",
                output / "summary.json" / "archive",
                existing,
            ):
                with self.subTest(archive_dir=archive_dir):
                    stderr = io.StringIO()
                    with redirect_stderr(stderr):
                        code = probe.main(
                            [
                                "--output-dir",
                                str(output / "runs"),
                                "--summary-output",
                                str(output / "summary.json"),
                                "--archive-dir",
                                str(archive_dir),
                            ]
                        )
                    self.assertEqual(2, code)
                    self.assertIn("code=archive_failed", stderr.getvalue())
                    self.assertTrue((output / "summary.json").is_file())

    def test_cli_returns_explicit_error_when_archive_write_fails(self) -> None:
        original_run = probe.run_command
        original_archive = probe.archive_evidence
        probe.run_command = FakeExecutor()
        probe.archive_evidence = fail_archive
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir)
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = probe.main(
                        [
                            "--output-dir",
                            str(output / "runs"),
                            "--summary-output",
                            str(output / "summary.json"),
                            "--archive-dir",
                            str(output / "durable-evidence"),
                            "--iterations",
                            "1",
                        ]
                    )
                self.assertEqual(2, code)
                self.assertIn("code=archive_failed", stderr.getvalue())
                self.assertTrue((output / "summary.json").is_file())
        finally:
            probe.run_command = original_run
            probe.archive_evidence = original_archive

    def test_cli_rejects_summary_output_inside_archive_before_probe(self) -> None:
        original_run = probe.run_command
        probe.run_command = fail_if_called
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir)
                archive_dir = output / "durable-evidence"
                summary_output = archive_dir / "summary.json"
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = probe.main(
                        [
                            "--output-dir",
                            str(output / "runs"),
                            "--summary-output",
                            str(summary_output),
                            "--archive-dir",
                            str(archive_dir),
                            "--iterations",
                            "1",
                        ]
                    )
                self.assertEqual(2, code)
                self.assertIn("summary output must not overlap", stderr.getvalue())
                self.assertIn("output_written=false", stderr.getvalue())
                self.assertFalse(summary_output.exists())
                self.assertFalse(archive_dir.exists())
        finally:
            probe.run_command = original_run

    def test_cli_rejects_archive_inside_summary_output_before_probe(self) -> None:
        original_run = probe.run_command
        probe.run_command = fail_if_called
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir)
                summary_output = output / "summary-dir"
                archive_dir = summary_output / "evidence"
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = probe.main(
                        [
                            "--output-dir",
                            str(output / "runs"),
                            "--summary-output",
                            str(summary_output),
                            "--archive-dir",
                            str(archive_dir),
                            "--iterations",
                            "1",
                        ]
                    )
                self.assertEqual(2, code)
                self.assertIn("summary output must not overlap", stderr.getvalue())
                self.assertIn("output_written=false", stderr.getvalue())
                self.assertFalse(summary_output.exists())
                self.assertFalse(archive_dir.exists())
        finally:
            probe.run_command = original_run

    def test_cli_preserves_probe_failure_when_summary_write_fails(self) -> None:
        original_run_probe = probe.run_probe
        original_write_json = probe.write_json
        probe.run_probe = fail_probe
        probe.write_json = fail_write_json
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output = Path(tmpdir)
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = probe.main(
                        [
                            "--output-dir",
                            str(output / "runs"),
                            "--summary-output",
                            str(output / "summary.json"),
                            "--iterations",
                            "1",
                        ]
                    )
                self.assertEqual(2, code)
                self.assertIn("code=probe_failed", stderr.getvalue())
                self.assertIn("message=simulated probe failure", stderr.getvalue())
                self.assertIn("output_written=false", stderr.getvalue())
                self.assertIn("summary_write_error=simulated summary write failure", stderr.getvalue())
        finally:
            probe.run_probe = original_run_probe
            probe.write_json = original_write_json


class FakeExecutor:
    def __init__(self, fail_sources: set[str] | None = None) -> None:
        self.fail_sources = fail_sources or set()

    def __call__(
        self,
        command: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        source = source_from_command(command)
        metadata_path = metadata_path_from_command(command)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if source in self.fail_sources:
            metadata_path.write_text(json.dumps(failed_metadata(source), ensure_ascii=False), encoding="utf-8")
            return subprocess.CompletedProcess(command, 3, stdout="", stderr=f"{source} failed")
        metadata_path.write_text(json.dumps(valid_metadata(source), ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=f"{source} ok", stderr="")


class TimeoutExecutor:
    def __init__(self, source: str) -> None:
        self.source = source

    def __call__(
        self,
        command: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        source = source_from_command(command)
        if source == self.source:
            raise subprocess.TimeoutExpired(command, timeout or 0)
        metadata_path = metadata_path_from_command(command)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(valid_metadata(source), ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout=f"{source} ok", stderr="")


def fail_archive(manifest: dict[str, object], archive_dir: Path) -> None:
    raise OSError("simulated archive failure")


def fail_if_called(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
    raise AssertionError("probe executor must not run after archive preflight failure")


def fail_probe(*_args: object, **_kwargs: object) -> None:
    raise OSError("simulated probe failure")


def fail_write_json(*_args: object, **_kwargs: object) -> None:
    raise OSError("simulated summary write failure")


def source_from_command(command: list[str]) -> str:
    script = Path(command[1]).name
    if script == "fetch_eastmoney_a_share_spot.py":
        return "eastmoney_spot"
    if script == "fetch_baostock_a_share_universe.py":
        return "baostock_universe"
    if script == "fetch_akshare_a_share.py":
        return "akshare"
    if script == "fetch_pytdx_a_share.py":
        return "pytdx"
    if script == "fetch_yfinance_ohlcv.py":
        return "yfinance"
    if script == "fetch_baostock_a_share.py":
        return "baostock"
    if script == "fetch_zzshare_a_share.py":
        return "zzshare"
    raise AssertionError(f"unknown command: {command}")


def metadata_path_from_command(command: list[str]) -> Path:
    index = command.index("--metadata-output")
    return Path(command[index + 1])


def valid_metadata(source: str) -> dict[str, object]:
    if source == "eastmoney_spot":
        return {
            "source": "eastmoney",
            "raw_items": 100,
            "filtered_items": 100,
            "partial_result": False,
            "output_written": True,
            "metadata_output_written": True,
        }
    if source == "baostock_universe":
        return {
            "source": "baostock",
            "raw_items": 2,
            "filtered_items": 2,
            "symbol_count": 2,
            "partial_result": False,
            "output_written": True,
            "metadata_output_written": True,
            "resolved_snapshot_date": "2026-07-09",
            "lookback_days": 7,
        }
    if source == "akshare":
        return akshare_metadata(fallback=False)
    if source == "pytdx":
        return {
            "source": "pytdx",
            "requested_symbols": ["000001"],
            "rows": 5,
            "symbol_count": 1,
            "failed_symbols": [],
            "empty_symbols": [],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "timeout_seconds": 10.0,
            "max_pages": 1,
            "token_configured": False,
            "license_claim_boundary": (
                "pypi_license_unknown_readme_personal_research_boundary"
            ),
            "missing_provider_fields": ["turn", "tradestatus", "isST", "name"],
        }
    if source == "yfinance":
        return {
            "source": "yfinance",
            "requested_symbols": ["AAPL", "MSFT"],
            "rows": 4,
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "timeout_seconds": 10.0,
            "adjustment": "auto_adjust_false_close",
            "symbols": [
                {"symbol": "AAPL", "rows": 2, "date_max": "2026-05-29"},
                {"symbol": "MSFT", "rows": 2, "date_max": "2026-05-29"},
            ],
        }
    if source == "baostock":
        return {
            "source": "baostock",
            "requested_symbols": ["000001", "600000"],
            "rows": 4,
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "non_trading_rows": 0,
            "tradestatus_missing_rows": 0,
            "adjustflag": "3",
        }
    if source == "zzshare":
        return {
            "source": "zzshare",
            "requested_symbols": ["000001", "600000"],
            "rows": 4,
            "symbol_count": 2,
            "failed_symbols": [],
            "empty_symbols": [],
            "invalid_rows": 0,
            "dropped_invalid_rows": 0,
            "non_trading_rows": 0,
            "tradestatus_missing_rows": 0,
            "possibly_truncated_symbols": [],
            "fields": "all",
            "limit": 1000,
            "max_pages": 10,
            "token_configured": False,
            "symbols": [
                {"symbol": "000001", "rows": 2, "date_max": "2026-05-29"},
                {"symbol": "600000", "rows": 2, "date_max": "2026-05-29"},
            ],
        }
    raise AssertionError(source)


def akshare_metadata(*, fallback: bool) -> dict[str, object]:
    return {
        "source": "akshare",
        "requested_symbols": ["000001"],
        "rows": 2,
        "symbol_count": 1,
        "failed_symbols": [],
        "empty_symbols": [],
        "invalid_rows": 0,
        "dropped_invalid_rows": 0,
        "fallback_errors": [{"symbol": "000001", "error": "hist failed"}] if fallback else [],
        "symbols": [{"symbol": "000001", "rows": 2, "provider": "stock_zh_a_daily"}],
    }


def failed_metadata(source: str) -> dict[str, object]:
    return {
        "source": source,
        "requested_symbols": ["BAD"],
        "rows": 0,
        "symbol_count": 0,
        "failed_symbols": [{"symbol": "BAD", "error": "failed"}],
        "empty_symbols": ["BAD"],
    }


def args_for(output: Path) -> object:
    return probe.build_parser().parse_args(
        [
            "--output-dir",
            str(output / "runs"),
            "--summary-output",
            str(output / "summary.json"),
            "--iterations",
            "1",
        ]
    )


if __name__ == "__main__":
    unittest.main()
