from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import prepare_clean_history_pool  # noqa: E402
from lib.gates.clean_history_pool import derive_short_history_data  # noqa: E402
from lib.selection_core.a_share_selection_command_safety import (  # noqa: E402
    classify_sensitive_flag,
    sanitize_command,
    sanitize_text,
)
from prepare_clean_history_pool import build_clean_plan  # noqa: E402
from prepare_history_retry_symbols import build_retry_plan  # noqa: E402
from prepare_incremental_history_plan import build_incremental_plan  # noqa: E402
from lib.runner.run_today_a_share_selection_retry_plan import (  # noqa: E402
    build_retry_plan as build_internal_retry_plan,
)
from lib.gates.incremental_history_artifacts import (  # noqa: E402
    combine_csv,
    combine_metadata,
)
from lib.gates.incremental_history_execution import (  # noqa: E402
    execute_plan,
)
from lib.gates.incremental_history_merge import (  # noqa: E402
    validate_incremental_metadata,
    validate_provider_merge_contract,
)
from execute_incremental_history_plan import run_verified_merge  # noqa: E402
from lib.runner.run_today_a_share_selection_parser import build_parser  # noqa: E402


def incremental_execution_plan() -> dict[str, object]:
    return {
        "source": "incremental_history_plan",
        "claim_boundary": "incremental_history_plan_only_not_history_fetch_success",
        "target_end_date": "2026-07-09",
        "fetch_symbols": ["000001", "600000"],
        "fetch_buckets": [
            {
                "bucket_id": "fetch-001-delta-stale_history",
                "fetch_mode": "delta",
                "reason": "stale_history",
                "start_date": "2026-07-09",
                "end_date": "2026-07-09",
                "symbols": ["000001"],
                "symbol_count": 1,
            },
            {
                "bucket_id": "fetch-002-full-missing_history",
                "fetch_mode": "full",
                "reason": "missing_history",
                "start_date": "",
                "end_date": "2026-07-09",
                "symbols": ["600000"],
                "symbol_count": 1,
            },
        ],
    }


def incremental_execution_config(root: Path) -> dict[str, object]:
    output_dir = root / "execution"
    return {
        "plan_path": root / "plan.json",
        "provider": "zzshare",
        "full_start_date": "2024-01-01",
        "output_dir": output_dir,
        "prices_output": output_dir / "incremental_prices.csv",
        "metadata_output": output_dir / "incremental_metadata.json",
        "manifest_output": output_dir / "execution_manifest.json",
        "resume": False,
        "checkpoint_batch_size": 10,
        "zzshare_non_trading_policy": "drop",
        "zzshare_request_interval_seconds": 0.0,
        "zzshare_max_concurrent_symbol_requests": 1,
        "zzshare_max_rate_limit_sleep_seconds": 60.0,
        "zzshare_max_429_events": 5,
        "zzshare_max_runtime_seconds": 120.0,
        "zzshare_progress_interval": 10,
        "python_executable": sys.executable,
        "scripts_dir": SCRIPTS,
    }


def write_bucket_artifacts(command: list[str], *, rows: int) -> None:
    if rows == 0:
        return
    output = Path(command[command.index("--output") + 1])
    metadata = Path(command[command.index("--metadata-output") + 1])
    symbols_file = Path(command[command.index("--symbols-file") + 1])
    symbol = symbols_file.read_text(encoding="utf-8").strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"symbol,date,close\n{symbol},2026-07-09,10.0\n", encoding="utf-8"
    )
    metadata.write_text(
        json.dumps(
            {
                "source": "zzshare",
                "output_written": True,
                "metadata_output_written": True,
                "requested_symbols": [symbol],
                "symbols": [
                    {
                        "symbol": symbol,
                        "rows": 1,
                        "date_min": "2026-07-09",
                        "date_max": "2026-07-09",
                    }
                ],
                "failed_symbols": [],
                "empty_symbols": [],
                "possibly_truncated_symbols": [],
                "invalid_rows": 0,
            }
        ),
        encoding="utf-8",
    )


class RecoveryAndSafetyHelperTests(unittest.TestCase):
    def test_retry_cli_reexports_internal_retry_plan_contract(self) -> None:
        self.assertIs(build_retry_plan, build_internal_retry_plan)

    def test_pytdx_incremental_merge_requires_same_date_strict_companion(self) -> None:
        metadata = {
            "provider": "pytdx",
            "selection_ready": False,
            "merge_join_keys": ["symbol", "date"],
            "strict_fields_same_date_required": True,
        }

        with self.assertRaisesRegex(
            ValueError, "exact symbol/date strict companion fields are required"
        ):
            validate_provider_merge_contract(metadata)

    def test_pytdx_bucket_aggregation_preserves_fetch_metrics_and_capability(self) -> None:
        items = [
            {
                "symbols": [{"symbol": "000001", "rows": 2}],
                "raw_rows": 20,
                "requested_raw_rows": 32,
                "api_request_count": 1,
                "allowed_merge_fields": ["open", "close", "amount"],
                "merge_join_keys": ["symbol", "date"],
            }
        ]

        metadata = combine_metadata(
            {"fetch_symbols": ["000001"]}, items, "pytdx", rows=2
        )

        self.assertEqual(20, metadata["raw_rows"])
        self.assertEqual(32, metadata["requested_raw_rows"])
        self.assertEqual(18, metadata["overfetch_rows"])
        self.assertEqual(10.0, metadata["raw_to_output_ratio"])
        self.assertFalse(metadata["selection_ready"])
        self.assertEqual(["symbol", "date"], metadata["merge_join_keys"])

    def test_sanitize_command_redacts_sensitive_flags_and_urls(self) -> None:
        command = [
            "python",
            "tool.py",
            "--token",
            "placeholder-token-value",
            "--api-key=placeholder-api-key-value",
            "--http-url",
            "https://example.test/path?token=secret&x=1",
        ]

        sanitized = sanitize_command(command)

        self.assertEqual("[REDACTED]", sanitized[3])
        self.assertEqual("--api-key=[REDACTED]", sanitized[4])
        self.assertIn("token=%5BREDACTED%5D", sanitized[6])
        self.assertNotIn("placeholder-token-value", " ".join(sanitized))
        self.assertNotIn("placeholder-api-key-value", " ".join(sanitized))

    def test_sanitize_text_redacts_key_value_patterns(self) -> None:
        sanitized = sanitize_text(
            "ZZSHARE_TOKEN=placeholder-secret-value API_KEY=placeholder-api-key-value status=failed"
        )

        self.assertIn("ZZSHARE_TOKEN=[REDACTED]", sanitized)
        self.assertIn("API_KEY=[REDACTED]", sanitized)
        self.assertNotIn("placeholder-secret-value", sanitized)
        self.assertNotIn("placeholder-api-key-value", sanitized)

    def test_sanitize_text_redacts_json_and_header_secret_patterns(self) -> None:
        sanitized = sanitize_text(
            '"token": "placeholder-json-token" '
            "'password': 'placeholder-json-password' "
            "X-API-Key: placeholder-header-key "
            '"Authorization": "Bearer placeholder-json-bearer" '
            "'Proxy-Authorization': 'Basic placeholder-json-basic'"
        )

        self.assertIn('"token": "[REDACTED]"', sanitized)
        self.assertIn("'password': '[REDACTED]'", sanitized)
        self.assertIn("X-API-Key: [REDACTED]", sanitized)
        self.assertIn('"Authorization": "[REDACTED]"', sanitized)
        self.assertIn("'Proxy-Authorization': '[REDACTED]'", sanitized)
        self.assertNotIn("placeholder-json-token", sanitized)
        self.assertNotIn("placeholder-json-password", sanitized)
        self.assertNotIn("placeholder-header-key", sanitized)
        self.assertNotIn("placeholder-json-bearer", sanitized)
        self.assertNotIn("placeholder-json-basic", sanitized)

    def test_sanitize_text_redacts_authorization_bearer_header(self) -> None:
        sanitized = sanitize_text(
            "request failed Authorization: Bearer placeholder-bearer-token status=401"
        )

        self.assertIn("Authorization: Bearer [REDACTED]", sanitized)
        self.assertNotIn("placeholder-bearer-token", sanitized)

    def test_sanitize_text_redacts_authorization_bearer_assignment(self) -> None:
        sanitized = sanitize_text(
            "request failed Authorization=Bearer placeholder-bearer-token status=401"
        )

        self.assertIn("Authorization=Bearer [REDACTED]", sanitized)
        self.assertNotIn("placeholder-bearer-token", sanitized)

    def test_sanitize_text_redacts_bare_authorization_value(self) -> None:
        sanitized = sanitize_text(
            "request failed Authorization: placeholder-secret status=401"
        )

        self.assertIn("Authorization: [REDACTED]", sanitized)
        self.assertNotIn("placeholder-secret", sanitized)

    def test_sanitize_text_redacts_non_bearer_authorization_values(self) -> None:
        sanitized = sanitize_text(
            "Authorization: Basic placeholder-basic-secret "
            "Proxy-Authorization: Token placeholder-token-secret "
            "Authorization=ApiKey placeholder-api-key-secret"
        )

        self.assertIn("Authorization: Basic [REDACTED]", sanitized)
        self.assertIn("Proxy-Authorization: Token [REDACTED]", sanitized)
        self.assertIn("Authorization=ApiKey [REDACTED]", sanitized)
        self.assertNotIn("placeholder-basic-secret", sanitized)
        self.assertNotIn("placeholder-token-secret", sanitized)
        self.assertNotIn("placeholder-api-key-secret", sanitized)

    def test_sanitize_text_redacts_multi_part_authorization_values(self) -> None:
        sanitized = sanitize_text(
            'Authorization: Digest username="alice", response="secret-response", '
            'nonce="placeholder-nonce"\n'
            "Authorization: AWS4-HMAC-SHA256 "
            "Credential=AKIAEXAMPLE/20260705/us-east-1/service/aws4_request, "
            "SignedHeaders=host;x-amz-date, Signature=secret-signature"
        )

        self.assertIn("Authorization: Digest [REDACTED]", sanitized)
        self.assertIn("Authorization: AWS4-HMAC-SHA256 [REDACTED]", sanitized)
        self.assertNotIn("secret-response", sanitized)
        self.assertNotIn("placeholder-nonce", sanitized)
        self.assertNotIn("AKIAEXAMPLE", sanitized)
        self.assertNotIn("secret-signature", sanitized)

    def test_sanitize_text_redacts_wrapped_authorization_values(self) -> None:
        sanitized = sanitize_text(
            "Authorization: Bearer placeholder-token\n  continuation-secret\nstatus=401"
        )

        self.assertIn("Authorization: Bearer [REDACTED]\nstatus=401", sanitized)
        self.assertNotIn("placeholder-token", sanitized)
        self.assertNotIn("continuation-secret", sanitized)

    def test_sanitize_text_redacts_embedded_url_query_secret(self) -> None:
        sanitized = sanitize_text(
            "request failed url=https://example.test/path?token=placeholder-token&x=1"
        )

        self.assertIn("token=%5BREDACTED%5D", sanitized)
        self.assertIn("x=1", sanitized)
        self.assertNotIn("placeholder-token", sanitized)

    def test_sanitize_text_redacts_encoded_and_repeated_url_query_secrets(self) -> None:
        sanitized = sanitize_text(
            "url=https://example.test/path?api%5Fkey=placeholder-key&"
            "ToKeN=placeholder-token&token=&x=1&token=second-placeholder"
        )

        self.assertIn("api_key=%5BREDACTED%5D", sanitized)
        self.assertIn("ToKeN=%5BREDACTED%5D", sanitized)
        self.assertEqual(4, sanitized.count("%5BREDACTED%5D"))
        self.assertIn("x=1", sanitized)
        self.assertNotIn("placeholder-key", sanitized)
        self.assertNotIn("placeholder-token", sanitized)
        self.assertNotIn("second-placeholder", sanitized)

    def test_sanitize_text_redacts_signed_url_query_credentials(self) -> None:
        sanitized = sanitize_text(
            "url=https://example.test/signed?"
            "X-Amz-Signature=placeholder-signature&"
            "X-Amz-Credential=placeholder-credential&"
            "access_key_id=placeholder-access-key&"
            "accessKeyId=placeholder-camel-access-key&"
            "sig=placeholder-short-signature&"
            "x=1"
        )

        self.assertIn("X-Amz-Signature=%5BREDACTED%5D", sanitized)
        self.assertIn("X-Amz-Credential=%5BREDACTED%5D", sanitized)
        self.assertIn("access_key_id=%5BREDACTED%5D", sanitized)
        self.assertIn("accessKeyId=%5BREDACTED%5D", sanitized)
        self.assertIn("sig=%5BREDACTED%5D", sanitized)
        self.assertIn("x=1", sanitized)
        self.assertNotIn("placeholder-signature", sanitized)
        self.assertNotIn("placeholder-credential", sanitized)
        self.assertNotIn("placeholder-access-key", sanitized)
        self.assertNotIn("placeholder-camel-access-key", sanitized)
        self.assertNotIn("placeholder-short-signature", sanitized)

    def test_sanitize_text_redacts_encoded_nested_url_credentials(self) -> None:
        sanitized = sanitize_text(
            "url=https://example.test/login?"
            "redirect_uri=https%3A%2F%2Fapp.example%2Fcallback%3F"
            "access_token%3Dplaceholder-access-token%26state%3Dok&x=1"
        )

        self.assertIn("redirect_uri=", sanitized)
        self.assertIn("x=1", sanitized)
        self.assertIn("access_token%3D%255BREDACTED%255D", sanitized)
        self.assertNotIn("placeholder-access-token", sanitized)
        self.assertNotIn("access_token%3Dplaceholder-access-token", sanitized)

    def test_sanitize_text_redacts_url_fragment_credentials(self) -> None:
        sanitized = sanitize_text(
            "redirect=https://callback.example/auth#"
            "access_token=placeholder-access-token&"
            "id_token=placeholder-id-token&state=ok"
        )

        self.assertIn("#access_token=%5BREDACTED%5D", sanitized)
        self.assertIn("id_token=%5BREDACTED%5D", sanitized)
        self.assertIn("state=ok", sanitized)
        self.assertNotIn("placeholder-access-token", sanitized)
        self.assertNotIn("placeholder-id-token", sanitized)

    def test_sanitize_text_redacts_spa_route_fragment_credentials(self) -> None:
        sanitized = sanitize_text(
            "redirect=https://app.example/#/callback?"
            "access_token=placeholder-access-token&"
            "id_token=placeholder-id-token&state=ok"
        )

        self.assertIn("#/callback?access_token=%5BREDACTED%5D", sanitized)
        self.assertIn("id_token=%5BREDACTED%5D", sanitized)
        self.assertIn("state=ok", sanitized)
        self.assertNotIn("placeholder-access-token", sanitized)
        self.assertNotIn("placeholder-id-token", sanitized)

    def test_sanitize_text_preserves_non_sensitive_url_key_values(self) -> None:
        sanitized = sanitize_text(
            "doc=https://example.test/path?preview#section "
            "anchor=https://docs.example/#access_token-docs "
            "route=https://app.example/#/oauth/token-help"
        )

        self.assertEqual(
            "doc=https://example.test/path?preview#section "
            "anchor=https://docs.example/#access_token-docs "
            "route=https://app.example/#/oauth/token-help",
            sanitized,
        )

    def test_sanitize_text_redacts_signed_key_value_credentials(self) -> None:
        sanitized = sanitize_text(
            "X-Amz-Signature=placeholder-signature "
            "X-Amz-Credential=placeholder-credential "
            "access_key_id=placeholder-access-key "
            "accessKeyId=placeholder-camel-access-key "
            "status=failed"
        )

        self.assertIn("X-Amz-Signature=[REDACTED]", sanitized)
        self.assertIn("X-Amz-Credential=[REDACTED]", sanitized)
        self.assertIn("access_key_id=[REDACTED]", sanitized)
        self.assertIn("accessKeyId=[REDACTED]", sanitized)
        self.assertIn("status=failed", sanitized)
        self.assertNotIn("placeholder-signature", sanitized)
        self.assertNotIn("placeholder-credential", sanitized)
        self.assertNotIn("placeholder-access-key", sanitized)
        self.assertNotIn("placeholder-camel-access-key", sanitized)

    def test_sanitize_text_redacts_multiline_log_secrets(self) -> None:
        sanitized = sanitize_text(
            "\n".join(
                [
                    "stdout: API_KEY=placeholder-api-key TOKEN=placeholder-token",
                    "stderr: Authorization: Bearer placeholder-bearer",
                    "url: https://user:placeholder-password@example.test/path?secret=value",
                ]
            )
        )

        self.assertIn("API_KEY=[REDACTED]", sanitized)
        self.assertIn("TOKEN=[REDACTED]", sanitized)
        self.assertIn("Authorization: Bearer [REDACTED]", sanitized)
        self.assertIn(
            "https://[REDACTED]@example.test/path?secret=%5BREDACTED%5D", sanitized
        )
        self.assertNotIn("placeholder-api-key", sanitized)
        self.assertNotIn("placeholder-token", sanitized)
        self.assertNotIn("placeholder-bearer", sanitized)
        self.assertNotIn("placeholder-password", sanitized)

    def test_sanitize_text_redacts_url_userinfo(self) -> None:
        sanitized = sanitize_text(
            "request failed url=https://user:placeholder-password@example.test/path"
        )

        self.assertIn("https://[REDACTED]@example.test/path", sanitized)
        self.assertNotIn("user:placeholder-password", sanitized)

    def test_runner_sensitive_flags_are_registered_for_redaction(self) -> None:
        parser = build_parser()
        sensitive_terms = (
            "token",
            "api-key",
            "api_key",
            "secret",
            "password",
            "bearer",
        )
        sensitive_flags = sorted(
            option
            for action in parser._actions
            for option in action.option_strings
            if any(term in option.lower() for term in sensitive_terms)
        )

        self.assertEqual(
            [],
            [
                flag
                for flag in sensitive_flags
                if not classify_sensitive_flag(flag)[0]
            ],
        )

    def test_build_retry_plan_uses_failed_empty_and_truncated_symbols(self) -> None:
        selected = {
            "selected_symbols": ["000001", "000002", "600000", "300001"],
        }
        metadata = {
            "failed_symbols": [{"symbol": "000002", "error": "timeout"}],
            "empty_symbols": ["600000"],
            "possibly_truncated_symbols": ["300001"],
            "invalid_symbols": ["000999"],
        }

        plan = build_retry_plan(
            selected_data=selected,
            metadata=metadata,
            include_clean_selected=False,
        )

        self.assertEqual(["000002", "600000", "300001"], plan["retry_symbols"])
        self.assertEqual(["000001"], plan["clean_selected_symbols"])
        self.assertEqual(
            "retry_plan_only_not_full_market_completion_or_history_fetch_success",
            plan["claim_boundary"],
        )

    def test_build_retry_plan_does_not_invent_retry_symbols_when_clean(self) -> None:
        plan = build_retry_plan(
            selected_data={"selected_symbols": ["000001", "000002"]},
            metadata={"failed_symbols": [], "empty_symbols": []},
            include_clean_selected=False,
        )

        self.assertEqual([], plan["retry_symbols"])
        self.assertEqual(["000001", "000002"], plan["clean_selected_symbols"])
        self.assertEqual(0, plan["retry_symbol_count"])

    def test_build_retry_plan_includes_unprocessed_symbols(self) -> None:
        plan = build_retry_plan(
            selected_data={"selected_symbols": ["000001", "000002"]},
            metadata={
                "failed_symbols": [],
                "empty_symbols": [],
                "possibly_truncated_symbols": [],
                "unprocessed_symbols": ["000002"],
            },
            include_clean_selected=False,
        )

        self.assertEqual(["000002"], plan["retry_symbols"])
        self.assertEqual(["000002"], plan["retry_reasons"]["unprocessed_symbols"])
        self.assertEqual(["000001"], plan["clean_selected_symbols"])

    def test_clean_plan_records_unprocessed_symbols(self) -> None:
        plan = build_clean_plan(
            metadata={
                "source": "zzshare",
                "unprocessed_symbols": ["600000"],
            },
            short_data={"symbols": []},
            ttl_days=7,
        )

        self.assertEqual(["600000"], plan["remove_symbols"])
        self.assertEqual(
            ["600000"],
            plan["reason_symbols"]["unprocessed_fetch"],
        )

    def test_incremental_merge_rejects_unprocessed_symbols(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "incremental history metadata has unprocessed_symbols",
        ):
            validate_incremental_metadata(
                {
                    "output_written": True,
                    "metadata_output_written": True,
                    "requested_symbols": ["600000"],
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "possibly_truncated_symbols": [],
                    "unprocessed_symbols": ["600000"],
                },
                ["600000"],
            )

    def test_incremental_merge_rejects_unknown_partial_result_semantics(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "incremental history metadata partial_result_semantics is invalid",
        ):
            validate_incremental_metadata(
                {
                    "output_written": True,
                    "metadata_output_written": True,
                    "requested_symbols": ["600000"],
                    "failed_symbols": [],
                    "empty_symbols": [],
                    "possibly_truncated_symbols": [],
                    "unprocessed_symbols": [],
                    "partial_result_semantics": "unknown",
                },
                ["600000"],
            )

    def test_incremental_merge_requires_semantics_for_no_trading_updates(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "incremental no-trading updates require partial_result_semantics",
        ):
            validate_incremental_metadata(
                {
                    "provider": "baostock",
                    "output_written": True,
                    "metadata_output_written": True,
                    "requested_symbols": ["600000"],
                    "failed_symbols": [],
                    "empty_symbols": ["600000"],
                    "non_trading_only_empty_symbols": ["600000"],
                    "no_trading_update_symbols": ["600000"],
                    "possibly_truncated_symbols": [],
                    "unprocessed_symbols": [],
                    "raw_symbols": [
                        {
                            "symbol": "600000",
                            "rows": 1,
                            "date_min": "2026-07-09",
                            "date_max": "2026-07-09",
                        }
                    ],
                },
                ["600000"],
                target="2026-07-09",
            )

    def test_build_retry_plan_excludes_unselected_metadata_symbols(self) -> None:
        plan = build_retry_plan(
            selected_data={"selected_symbols": ["000001", "000002"]},
            metadata={
                "failed_symbols": ["000002", "999999"],
                "empty_symbols": [{"symbol": "600000"}],
            },
            include_clean_selected=False,
        )

        self.assertEqual(["000002"], plan["retry_symbols"])
        self.assertEqual(["600000", "999999"], plan["unexpected_metadata_symbols"])
        self.assertEqual(2, plan["unexpected_metadata_symbol_count"])

    def test_prepare_history_retry_symbols_cli_writes_json_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = root / "selected_symbols.json"
            metadata = root / "history_metadata.json"
            output = root / "retry_plan.json"
            text_output = root / "nested" / "retry" / "retry_symbols.txt"
            selected.write_text(
                json.dumps({"selected_symbols": ["000001", "000002"]}) + "\n",
                encoding="utf-8",
            )
            metadata.write_text(
                json.dumps({"failed_symbols": ["000002"], "empty_symbols": []}) + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_history_retry_symbols.py"),
                    "--selected-symbols",
                    str(selected),
                    "--history-metadata",
                    str(metadata),
                    "--output",
                    str(output),
                    "--symbols-output",
                    str(text_output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            plan = json.loads(output.read_text(encoding="utf-8"))
            text = text_output.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("OK: retry_symbols=1", result.stdout)
        self.assertEqual(["000002"], plan["retry_symbols"])
        self.assertEqual("000002\n", text)

    def test_prepare_history_retry_symbols_cli_can_include_clean_selected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = root / "selected_symbols.json"
            metadata = root / "history_metadata.json"
            output = root / "retry_plan.json"
            text_output = root / "retry_symbols.txt"
            selected.write_text(
                json.dumps({"selected_symbols": ["000001", "000002", "600000"]}) + "\n",
                encoding="utf-8",
            )
            metadata.write_text(
                json.dumps(
                    {
                        "failed_symbols": ["000002"],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_history_retry_symbols.py"),
                    "--selected-symbols",
                    str(selected),
                    "--history-metadata",
                    str(metadata),
                    "--output",
                    str(output),
                    "--symbols-output",
                    str(text_output),
                    "--include-clean-selected",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            plan = json.loads(output.read_text(encoding="utf-8"))
            text = text_output.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("OK: retry_symbols=3", result.stdout)
        self.assertEqual(["000002", "000001", "600000"], plan["retry_symbols"])
        self.assertEqual(["000001", "600000"], plan["clean_selected_symbols"])
        self.assertEqual(3, plan["retry_symbol_count"])
        self.assertTrue(plan["include_clean_selected"])
        self.assertEqual("000002,000001,600000\n", text)

    def test_prepare_history_retry_symbols_cli_rejects_output_input_collision(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selected = root / "selected_symbols.json"
            metadata = root / "history_metadata.json"
            selected_text = json.dumps({"selected_symbols": ["000001"]}) + "\n"
            selected.write_text(selected_text, encoding="utf-8")
            metadata.write_text(
                json.dumps({"failed_symbols": ["000001"]}) + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_history_retry_symbols.py"),
                    "--selected-symbols",
                    str(selected),
                    "--history-metadata",
                    str(metadata),
                    "--output",
                    str(selected),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("output path must not overwrite input", result.stderr)
            self.assertEqual(selected_text, selected.read_text(encoding="utf-8"))

    def test_prepare_clean_history_pool_cli_filters_empty_and_short_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            short = root / "short_history_symbols.json"
            output = root / "clean" / "prices.csv"
            metadata_output = root / "clean" / "history_metadata.json"
            metadata_alias = root / "clean" / "metadata.json"
            report_output = root / "clean" / "clean_history_report.json"
            prices.write_text(
                "\n".join(
                    [
                        "symbol,date,close",
                        "000001,2026-07-08,10.0",
                        "000001,2026-07-09,10.2",
                        "001220,2026-07-09,6.1",
                        "600000,2026-07-09,8.8",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            metadata.write_text(
                json.dumps(
                    {
                        "source": "zzshare",
                        "real_market_data": True,
                        "rows": 4,
                        "symbol_count": 3,
                        "requested_symbols": ["000001", "001220", "600000"],
                        "empty_symbols": ["600000"],
                        "failed_symbols": [],
                        "possibly_truncated_symbols": [],
                        "symbols": [
                            {"symbol": "000001", "rows": 2},
                            {"symbol": "001220", "rows": 1},
                            {"symbol": "600000", "rows": 0},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            short.write_text(
                json.dumps(
                    {
                        "symbols": [
                            {
                                "symbol": "001220",
                                "rows": 1,
                                "min_history_rows": 120,
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_clean_history_pool.py"),
                    "--prices-input",
                    str(prices),
                    "--history-metadata",
                    str(metadata),
                    "--short-history",
                    str(short),
                    "--output",
                    str(output),
                    "--metadata-output",
                    str(metadata_output),
                    "--metadata-alias-output",
                    str(metadata_alias),
                    "--report-output",
                    str(report_output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            clean_text = output.read_text(encoding="utf-8")
            clean_metadata = json.loads(metadata_output.read_text(encoding="utf-8"))
            alias_metadata = json.loads(
                metadata_alias.read_text(encoding="utf-8")
            )
            report = json.loads(report_output.read_text(encoding="utf-8"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("OK: clean_symbols=1", result.stdout)
        self.assertIn("000001", clean_text)
        self.assertNotIn("001220", clean_text)
        self.assertNotIn("600000", clean_text)
        self.assertEqual(2, clean_metadata["clean_pool_removed_symbol_count"])
        self.assertEqual(clean_metadata, alias_metadata)
        self.assertEqual(["001220", "600000"], report["removed_symbols"])
        self.assertEqual(2, len(report["skip_records"]))
        self.assertEqual(
            "clean_history_pool_from_existing_artifacts_not_full_market_proof",
            report["claim_boundary"],
        )

    def test_prepare_clean_history_pool_derives_and_publishes_short_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            output = root / "clean" / "prices.csv"
            metadata_output = root / "clean" / "history_metadata.json"
            report_output = root / "clean" / "clean_history_report.json"
            short_output = root / "clean" / "short_history_symbols.json"
            prices.write_text(
                "symbol,date,close\n"
                "000001,2026-07-08,10.0\n"
                "000001,2026-07-09,10.2\n"
                "001220,2026-07-09,6.1\n",
                encoding="utf-8",
            )
            metadata.write_text(
                json.dumps(
                    {
                        "source": "baostock",
                        "rows": 3,
                        "symbol_count": 2,
                        "requested_symbols": ["000001", "001220"],
                        "empty_symbols": [],
                        "failed_symbols": [],
                        "possibly_truncated_symbols": [],
                        "unprocessed_symbols": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_clean_history_pool.py"),
                    "--prices-input",
                    str(prices),
                    "--history-metadata",
                    str(metadata),
                    "--short-history-output",
                    str(short_output),
                    "--min-history-rows",
                    "2",
                    "--output",
                    str(output),
                    "--metadata-output",
                    str(metadata_output),
                    "--report-output",
                    str(report_output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            short_data = json.loads(short_output.read_text(encoding="utf-8"))
            report = json.loads(report_output.read_text(encoding="utf-8"))
            clean_metadata = json.loads(metadata_output.read_text(encoding="utf-8"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, short_data["short_history_symbol_count"])
        self.assertEqual(
            {
                "symbol": "001220",
                "rows": 1,
                "min_history_rows": 2,
                "date_min": "2026-07-09",
                "date_max": "2026-07-09",
            },
            short_data["symbols"][0],
        )
        self.assertEqual(str(prices), short_data["source_prices"])
        self.assertEqual(str(short_output), report["short_history"])
        self.assertEqual(["001220"], report["reason_symbols"]["short_history"])
        self.assertEqual(["001220"], clean_metadata["clean_pool_removed_symbols"])

    def test_prepare_clean_history_pool_requires_paired_short_history_options(self) -> None:
        parser = prepare_clean_history_pool.build_parser()
        base = [
            "--prices-input",
            "prices.csv",
            "--history-metadata",
            "metadata.json",
            "--output",
            "clean.csv",
            "--metadata-output",
            "clean.json",
            "--report-output",
            "report.json",
        ]

        args = parser.parse_args(base + ["--short-history-output", "short.json"])
        with self.assertRaisesRegex(ValueError, "requires --min-history-rows"):
            prepare_clean_history_pool.validate_short_history_options(args)
        args = parser.parse_args(base + ["--min-history-rows", "120"])
        with self.assertRaisesRegex(ValueError, "requires --short-history-output"):
            prepare_clean_history_pool.validate_short_history_options(args)
        args = parser.parse_args(
            base
            + [
                "--short-history-output",
                "short.json",
                "--min-history-rows",
                "120",
                "--incremental-plan",
                "plan.json",
                "--incremental-prices",
                "delta.csv",
                "--incremental-metadata",
                "delta.json",
            ]
        )
        with self.assertRaisesRegex(ValueError, "persisted effective history artifact"):
            prepare_clean_history_pool.validate_short_history_options(args)

    def test_derive_short_history_uses_supported_numeric_date_format(self) -> None:
        result = derive_short_history_data(
            pd.DataFrame(
                {
                    "symbol": ["001220"],
                    "date": [20260714],
                }
            ),
            120,
            Path("prices.parquet"),
        )

        self.assertEqual("2026-07-14", result["symbols"][0]["date_min"])
        self.assertEqual("2026-07-14", result["symbols"][0]["date_max"])

    def test_derive_short_history_rejects_duplicate_symbol_dates(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate symbol/date"):
            derive_short_history_data(
                pd.DataFrame(
                    {
                        "symbol": ["001220", "001220"],
                        "date": ["2026-07-14", "2026-07-14"],
                    }
                ),
                120,
                Path("prices.parquet"),
            )

    def test_prepare_clean_history_pool_rejects_duplicate_metadata_alias_output(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            clean = root / "clean"
            prices.write_text("symbol,date,close\n000001,2026-07-09,10.0\n", encoding="utf-8")
            metadata.write_text('{"symbols":[]}\n', encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_clean_history_pool.py"),
                    "--prices-input",
                    str(prices),
                    "--history-metadata",
                    str(metadata),
                    "--output",
                    str(clean / "prices.csv"),
                    "--metadata-output",
                    str(clean / "history_metadata.json"),
                    "--metadata-alias-output",
                    str(clean / "metadata.json"),
                    "--report-output",
                    str(clean / "metadata.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("duplicate output path", result.stderr)

    def test_prepare_clean_history_pool_rejects_missing_symbol_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "metadata.json"
            prices.write_text("date,close\n2026-07-09,10.0\n", encoding="utf-8")
            metadata.write_text('{"symbols":[]}\n', encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_clean_history_pool.py"),
                    "--prices-input",
                    str(prices),
                    "--history-metadata",
                    str(metadata),
                    "--output",
                    str(root / "clean" / "prices.csv"),
                    "--metadata-output",
                    str(root / "clean" / "history_metadata.json"),
                    "--report-output",
                    str(root / "clean" / "clean_history_report.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("prices input missing symbol column", result.stderr)

    def test_prepare_clean_history_pool_merges_verified_incremental_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            plan = root / "incremental_plan.json"
            delta = root / "delta.csv"
            delta_metadata = root / "delta_metadata.json"
            clean = root / "clean"
            prices.write_text(
                "\n".join(
                    [
                        "symbol,date,close",
                        "000001,2026-07-08,10.0",
                        "000001,2026-07-09,10.1",
                        "600000,2026-07-08,8.0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            metadata.write_text(
                json.dumps(
                    {
                        "source": "zzshare",
                        "output_written": True,
                        "metadata_output_written": True,
                        "symbols": [
                            {"symbol": "000001", "rows": 2, "date_max": "2026-07-09"},
                            {"symbol": "600000", "rows": 1, "date_max": "2026-07-08"},
                        ],
                        "empty_symbols": [],
                        "failed_symbols": [],
                        "possibly_truncated_symbols": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            plan.write_text(
                json.dumps(
                    {
                        "source": "incremental_history_plan",
                        "claim_boundary": (
                            "incremental_history_plan_only_not_history_fetch_success"
                        ),
                        "target_end_date": "2026-07-09",
                        "fetch_symbols": ["600000"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            delta.write_text(
                "symbol,date,close\n600000,2026-07-09,8.8\n",
                encoding="utf-8",
            )
            delta_metadata.write_text(
                json.dumps(
                    {
                        "source": "zzshare",
                        "requested_symbols": ["600000"],
                        "output_written": True,
                        "metadata_output_written": True,
                        "invalid_rows": 0,
                        "failed_symbols": [],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": [],
                        "symbols": [
                            {"symbol": "600000", "rows": 1, "date_max": "2026-07-09"}
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_clean_history_pool.py"),
                    "--prices-input",
                    str(prices),
                    "--history-metadata",
                    str(metadata),
                    "--incremental-plan",
                    str(plan),
                    "--incremental-prices",
                    str(delta),
                    "--incremental-metadata",
                    str(delta_metadata),
                    "--output",
                    str(clean / "prices.csv"),
                    "--metadata-output",
                    str(clean / "history_metadata.json"),
                    "--report-output",
                    str(clean / "clean_history_report.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            output_rows = (clean / "prices.csv").read_text(encoding="utf-8")
            merged_metadata = json.loads(
                (clean / "history_metadata.json").read_text(encoding="utf-8")
            )
            report = json.loads(
                (clean / "clean_history_report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("incremental_merged_symbols=1", result.stdout)
        self.assertIn("600000,2026-07-09,8.8", output_rows)
        self.assertEqual(4, merged_metadata["rows"])
        self.assertEqual("2026-07-08", merged_metadata["date_min"])
        self.assertEqual("2026-07-09", merged_metadata["date_max"])
        self.assertEqual("2026-07-09", merged_metadata["end_date"])
        self.assertGreaterEqual(
            report["incremental_merge"]["merge_duration_seconds"], 0.0
        )
        self.assertGreaterEqual(
            report["incremental_merge"]["merge_input_rows_per_second"], 0.0
        )
        self.assertEqual(1, merged_metadata["incremental_merge_planned_symbol_count"])
        self.assertEqual(
            "incremental_history_merge_from_verified_artifacts_not_full_market_proof",
            merged_metadata["incremental_merge_claim_boundary"],
        )
        self.assertEqual(1, report["incremental_merge"]["planned_symbol_count"])

    def test_prepare_clean_history_pool_rejects_incomplete_incremental_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            prices.write_text("symbol,date,close\n000001,2026-07-09,10.0\n", encoding="utf-8")
            metadata.write_text('{"symbols":[]}\n', encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_clean_history_pool.py"),
                    "--prices-input",
                    str(prices),
                    "--history-metadata",
                    str(metadata),
                    "--incremental-plan",
                    str(root / "incremental_plan.json"),
                    "--output",
                    str(root / "clean" / "prices.csv"),
                    "--metadata-output",
                    str(root / "clean" / "history_metadata.json"),
                    "--report-output",
                    str(root / "clean" / "clean_history_report.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("--incremental-plan", result.stderr)

    def test_prepare_clean_history_pool_rejects_incremental_fetch_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            prices = root / "prices.csv"
            metadata = root / "history_metadata.json"
            plan = root / "incremental_plan.json"
            delta = root / "delta.csv"
            delta_metadata = root / "delta_metadata.json"
            clean = root / "clean"
            prices.write_text("symbol,date,close\n600000,2026-07-08,8.0\n", encoding="utf-8")
            metadata.write_text('{"symbols":[{"symbol":"600000"}]}\n', encoding="utf-8")
            plan.write_text(
                json.dumps(
                    {
                        "source": "incremental_history_plan",
                        "claim_boundary": (
                            "incremental_history_plan_only_not_history_fetch_success"
                        ),
                        "target_end_date": "2026-07-09",
                        "fetch_symbols": ["600000"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            delta.write_text("symbol,date,close\n600000,2026-07-09,8.8\n", encoding="utf-8")
            delta_metadata.write_text(
                json.dumps(
                    {
                        "requested_symbols": ["600000"],
                        "output_written": True,
                        "metadata_output_written": True,
                        "failed_symbols": ["600000"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_clean_history_pool.py"),
                    "--prices-input",
                    str(prices),
                    "--history-metadata",
                    str(metadata),
                    "--incremental-plan",
                    str(plan),
                    "--incremental-prices",
                    str(delta),
                    "--incremental-metadata",
                    str(delta_metadata),
                    "--output",
                    str(clean / "prices.csv"),
                    "--metadata-output",
                    str(clean / "history_metadata.json"),
                    "--report-output",
                    str(clean / "clean_history_report.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("incremental history metadata has failed_symbols", result.stderr)

    def test_prepare_incremental_history_plan_cli_classifies_missing_and_stale_symbols(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            spot = root / "spot.csv"
            prices = root / "prices.csv"
            metadata = root / "metadata.json"
            output = root / "incremental.json"
            symbols = root / "incremental_symbols.txt"
            spot.write_text(
                "symbol,name\n000001,Alpha\n300001,New\n600000,Stale\n",
                encoding="utf-8",
            )
            prices.write_text(
                "symbol,date,close\n"
                "000001,2026-07-09,10.0\n"
                "600000,2026-07-08,8.0\n",
                encoding="utf-8",
            )
            metadata.write_text(
                json.dumps(
                    {
                        "symbols": [
                            {"symbol": "000001", "date_max": "20260709"},
                            {"symbol": "600000", "date_max": "20260708"},
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_incremental_history_plan.py"),
                    "--spot-input",
                    str(spot),
                    "--history-metadata",
                    str(metadata),
                    "--prices-input",
                    str(prices),
                    "--min-history-rows",
                    "1",
                    "--target-end-date",
                    "2026-07-09",
                    "--output",
                    str(output),
                    "--symbols-output",
                    str(symbols),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            plan = json.loads(output.read_text(encoding="utf-8"))
            symbol_text = symbols.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["300001", "600000"], plan["fetch_symbols"])
        self.assertEqual(["300001"], plan["missing_symbols"])
        self.assertEqual(["600000"], plan["stale_symbols"])
        self.assertEqual(["000001"], plan["up_to_date_symbols"])
        self.assertEqual("2026-07-08", plan["fetch_records"][1]["current_date_max"])
        self.assertEqual("", plan["fetch_records"][0]["suggested_start_date"])
        self.assertEqual(
            "2026-07-09",
            plan["fetch_records"][1]["suggested_start_date"],
        )
        self.assertEqual("mixed_delta_and_missing", plan["history_refresh_mode"])
        self.assertEqual(1, plan["delta_fetch_symbol_count"])
        self.assertEqual(1, plan["full_fetch_symbol_count"])
        self.assertEqual(["2026-07-09"], plan["suggested_fetch_start_dates"])
        self.assertEqual("", plan["suggested_fetch_start_date"])
        self.assertEqual("2026-07-09", plan["suggested_fetch_end_date"])
        self.assertEqual(
            {"missing_history": 1, "stale_history": 1},
            plan["fetch_reason_counts"],
        )
        self.assertEqual(2, plan["fetch_bucket_count"])
        self.assertGreater(plan["plan_duration_seconds"], 0.0)
        self.assertGreater(plan["plan_symbols_per_second"], 0.0)
        self.assertEqual(
            ["300001", "600000"],
            sorted(
                symbol
                for bucket in plan["fetch_buckets"]
                for symbol in bucket["symbols"]
            ),
        )
        self.assertEqual("300001\n600000\n", symbol_text)
        self.assertIn("claim_boundary=incremental_history_plan_only", result.stdout)

    def test_prepare_incremental_plan_treats_short_actual_history_as_full_fetch(
        self,
    ) -> None:
        incremental = build_incremental_plan(
            ["001220", "600000"],
            {
                "symbols": [
                    {"symbol": "001220", "rows": 2, "date_max": "2026-07-09"},
                    {"symbol": "600000", "rows": 120, "date_max": "2026-07-09"},
                ]
            },
            "2026-07-09",
            price_stats={
                "001220": {
                    "rows": 2,
                    "date_min": "2026-07-08",
                    "date_max": "2026-07-09",
                },
                "600000": {
                    "rows": 120,
                    "date_min": "2026-01-01",
                    "date_max": "2026-07-09",
                },
            },
            min_history_rows=120,
        )

        self.assertEqual(["001220"], incremental["fetch_symbols"])
        self.assertEqual(["001220"], incremental["short_history_symbols"])
        self.assertEqual("short_history_recovery", incremental["fetch_records"][0]["reason"])
        self.assertEqual("full", incremental["fetch_records"][0]["fetch_mode"])
        self.assertEqual(120, incremental["min_history_rows"])

    def test_prepare_incremental_plan_rejects_prices_metadata_drift(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "history prices rows do not match metadata"
        ):
            build_incremental_plan(
                ["000001"],
                {
                    "symbols": [
                        {"symbol": "000001", "rows": 120, "date_max": "2026-07-09"}
                    ]
                },
                "2026-07-09",
                price_stats={
                    "000001": {
                        "rows": 119,
                        "date_min": "2026-01-02",
                        "date_max": "2026-07-09",
                    }
                },
                min_history_rows=120,
            )

    def test_prepare_incremental_plan_refetches_rate_limited_unprocessed_symbol(
        self,
    ) -> None:
        incremental = build_incremental_plan(
            ["000001"],
            {
                "symbols": [
                    {"symbol": "000001", "rows": 120, "date_max": "2026-07-09"}
                ],
                "partial_result": True,
                "rate_limit_budget_exhausted": True,
                "unprocessed_symbols": ["000001"],
            },
            "2026-07-09",
        )

        self.assertEqual(["000001"], incremental["fetch_symbols"])
        self.assertEqual(
            "metadata_unprocessed_fetch",
            incremental["fetch_records"][0]["reason"],
        )
        self.assertEqual([], incremental["up_to_date_symbols"])

    def test_prepare_incremental_plan_accepts_audited_clean_pool_partial_result(
        self,
    ) -> None:
        incremental = build_incremental_plan(
            ["000001", "600000"],
            {
                "source_scope": "clean_history_pool",
                "symbols": [
                    {"symbol": "000001", "rows": 120, "date_max": "2026-07-09"}
                ],
                "partial_result": True,
                "rate_limit_budget_exhausted": True,
                "clean_pool_removed_symbol_count": 1,
                "clean_pool_reason_counts": {"unprocessed_fetch": 1},
            },
            "2026-07-09",
        )

        self.assertEqual(["600000"], incremental["fetch_symbols"])
        self.assertEqual("missing_history", incremental["fetch_records"][0]["reason"])

    def test_prepare_incremental_plan_rejects_duplicate_symbol_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate symbol metadata"):
            build_incremental_plan(
                ["000001"],
                {
                    "symbols": [
                        {"symbol": "000001", "rows": 1, "date_max": "2026-07-09"},
                        {"symbol": "000001", "rows": 1, "date_max": "2026-07-09"},
                    ]
                },
                "2026-07-09",
            )

    def test_prepare_incremental_plan_rejects_inconsistent_quality_counts(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "invalid_rows and dropped_invalid_rows do not match",
        ):
            build_incremental_plan(
                ["000001"],
                {
                    "symbols": [
                        {"symbol": "000001", "rows": 120, "date_max": "2026-07-09"}
                    ],
                    "invalid_rows": 1,
                    "dropped_invalid_rows": 2,
                },
                "2026-07-09",
            )

    def test_prepare_incremental_plan_treats_empty_metadata_as_full_fetch(
        self,
    ) -> None:
        incremental = build_incremental_plan(
            ["301583", "600000"],
            {
                "symbols": [
                    {"symbol": "301583", "rows": 0, "date_max": ""},
                    {"symbol": "600000", "rows": 10, "date_max": "2026-07-08"},
                ]
            },
            "2026-07-09",
        )

        empty_record, stale_record = incremental["fetch_records"]
        self.assertEqual("empty_or_missing_history", empty_record["reason"])
        self.assertEqual("full", empty_record["fetch_mode"])
        self.assertEqual("", empty_record["suggested_start_date"])
        self.assertEqual("stale_history", stale_record["reason"])
        self.assertEqual("delta", stale_record["fetch_mode"])
        self.assertEqual(["301583"], incremental["empty_history_symbols"])
        self.assertEqual(1, incremental["full_fetch_symbol_count"])
        self.assertEqual(1, incremental["delta_fetch_symbol_count"])
        self.assertEqual(
            {"empty_or_missing_history": 1, "stale_history": 1},
            incremental["fetch_reason_counts"],
        )
        bucket_symbols = [
            symbol
            for bucket in incremental["fetch_buckets"]
            for symbol in bucket["symbols"]
        ]
        self.assertEqual(incremental["fetch_symbols"], sorted(bucket_symbols))
        self.assertEqual(
            incremental["fetch_symbol_count"],
            sum(bucket["symbol_count"] for bucket in incremental["fetch_buckets"]),
        )

    def test_prepare_incremental_history_plan_rejects_impossible_metadata_date(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "date must be YYYY-MM-DD"):
            build_incremental_plan(
                ["000001"],
                {"symbols": [{"symbol": "000001", "date_max": "2026-02-30"}]},
                "2026-07-09",
            )

    def test_clean_and_incremental_plan_helpers_expose_claim_boundaries(self) -> None:
        clean_plan = build_clean_plan(
            {"source": "zzshare", "empty_symbols": ["600000"]},
            {"symbols": [{"symbol": "001220"}]},
            ttl_days=3,
        )
        incremental = build_incremental_plan(
            ["000001", "600000"],
            {"symbols": [{"symbol": "000001", "date_max": "2026-07-09"}]},
            "2026-07-09",
        )

        self.assertEqual(["001220", "600000"], clean_plan["remove_symbols"])
        self.assertEqual(2, len(clean_plan["skip_records"]))
        self.assertEqual(["600000"], incremental["fetch_symbols"])
        self.assertEqual("full_for_missing_only", incremental["history_refresh_mode"])
        self.assertEqual(
            "incremental_history_plan_only_not_history_fetch_success",
            incremental["claim_boundary"],
        )

    def test_prepare_incremental_history_plan_reports_delta_only_window(self) -> None:
        incremental = build_incremental_plan(
            ["000001", "600000"],
            {
                "symbols": [
                    {"symbol": "000001", "date_max": "2026-07-08"},
                    {"symbol": "600000", "date_max": "2026-07-08"},
                ]
            },
            "2026-07-09",
        )

        self.assertEqual("delta_only", incremental["history_refresh_mode"])
        self.assertEqual(2, incremental["delta_fetch_symbol_count"])
        self.assertEqual(0, incremental["full_fetch_symbol_count"])
        self.assertEqual("2026-07-09", incremental["suggested_fetch_start_date"])
        self.assertEqual(["2026-07-09"], incremental["suggested_fetch_start_dates"])
        self.assertEqual("2026-07-09", incremental["suggested_fetch_end_date"])

    def test_prepare_incremental_history_plan_uses_earliest_delta_start(self) -> None:
        incremental = build_incremental_plan(
            ["000001", "600000"],
            {
                "symbols": [
                    {"symbol": "000001", "date_max": "2026-07-08"},
                    {"symbol": "600000", "date_max": "2026-07-03"},
                ]
            },
            "2026-07-09",
        )

        self.assertEqual("delta_only", incremental["history_refresh_mode"])
        self.assertEqual("2026-07-04", incremental["suggested_fetch_start_date"])
        self.assertEqual(
            ["2026-07-04", "2026-07-09"],
            incremental["suggested_fetch_start_dates"],
        )

    def test_incremental_execution_aggregates_verified_bucket_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)
            calls = []

            def executor(command: list[str]) -> int:
                calls.append(command)
                write_bucket_artifacts(command, rows=1)
                return 0

            manifest = execute_plan(plan, config, executor)
            metadata = json.loads(config["metadata_output"].read_text(encoding="utf-8"))
            prices = config["prices_output"].read_text(encoding="utf-8")

        self.assertEqual("complete", manifest["status"])
        self.assertEqual(2, len(calls))
        self.assertIn("--symbols-file", calls[0])
        self.assertIn("--symbols-file", calls[1])
        self.assertIn("2026-07-09", calls[0])
        self.assertIn("2024-01-01", calls[1])
        self.assertEqual(2, metadata["symbol_count"])
        self.assertEqual(2, metadata["rows"])
        self.assertEqual(0, metadata["overfetch_rows"])
        self.assertEqual(3, len(prices.strip().splitlines()))
        self.assertEqual(2, manifest["executed_bucket_count"])
        self.assertEqual(0, manifest["reused_bucket_count"])
        self.assertEqual(2, manifest["executed_symbol_count"])
        self.assertGreaterEqual(manifest["execution_duration_seconds"], 0.0)

    def test_incremental_execution_stops_and_records_invalid_bucket_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)
            calls = []

            def executor(command: list[str]) -> int:
                calls.append(command)
                if len(calls) == 1:
                    write_bucket_artifacts(command, rows=0)
                return 0

            manifest = execute_plan(plan, config, executor)
            saved = json.loads(config["manifest_output"].read_text(encoding="utf-8"))

        self.assertEqual("partial", manifest["status"])
        self.assertEqual(1, len(calls))
        self.assertEqual("failed", manifest["buckets"][0]["status"])
        self.assertIn("bucket artifacts missing", manifest["buckets"][0]["error"])
        self.assertEqual(manifest["failed_bucket_id"], saved["failed_bucket_id"])

    def test_incremental_execution_rejects_header_only_bucket_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)

            def executor(command: list[str]) -> int:
                output = Path(command[command.index("--output") + 1])
                metadata = Path(command[command.index("--metadata-output") + 1])
                symbols_file = Path(command[command.index("--symbols-file") + 1])
                symbol = symbols_file.read_text(encoding="utf-8").strip()
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text("symbol,date,close\n", encoding="utf-8")
                metadata.write_text(
                    json.dumps(
                        {
                            "source": "zzshare",
                            "output_written": True,
                            "metadata_output_written": True,
                            "requested_symbols": [symbol],
                            "symbols": [{"symbol": symbol, "rows": 0}],
                            "failed_symbols": [],
                            "empty_symbols": [],
                            "possibly_truncated_symbols": [],
                            "invalid_rows": 0,
                        }
                    ),
                    encoding="utf-8",
                )
                return 0

            manifest = execute_plan(plan, config, executor)

        self.assertEqual("partial", manifest["status"])
        self.assertIn("bucket prices is empty", manifest["buckets"][0]["error"])

    def test_incremental_execution_rejects_bucket_csv_metadata_row_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)

            def executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                metadata_path = Path(command[command.index("--metadata-output") + 1])
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["symbols"][0]["rows"] = 2
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
                return 0

            manifest = execute_plan(plan, config, executor)

        self.assertEqual("partial", manifest["status"])
        self.assertIn("bucket metadata rows do not match prices", manifest["buckets"][0]["error"])

    def test_incremental_execution_cli_requires_full_start_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = root / "plan.json"
            plan.write_text(json.dumps(incremental_execution_plan()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "execute_incremental_history_plan.py"),
                    "--plan",
                    str(plan),
                    "--provider",
                    "zzshare",
                    "--output-dir",
                    str(root / "execution"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("--full-start-date is required", result.stderr)

    def test_incremental_execution_resume_reuses_verified_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)
            first_calls = []

            def first_executor(command: list[str]) -> int:
                first_calls.append(command)
                write_bucket_artifacts(command, rows=1)
                return 0

            execute_plan(plan, config, first_executor)
            config["resume"] = True
            second_calls = []
            manifest = execute_plan(plan, config, second_calls.append)

        self.assertEqual(2, len(first_calls))
        self.assertEqual(
            "drop",
            first_calls[0][first_calls[0].index("--non-trading-policy") + 1],
        )
        self.assertEqual(
            "0.0",
            first_calls[0][first_calls[0].index("--request-interval-seconds") + 1],
        )
        self.assertEqual(
            "120.0",
            first_calls[0][first_calls[0].index("--max-runtime-seconds") + 1],
        )
        self.assertEqual("drop", manifest["zzshare_non_trading_policy"])
        self.assertEqual(120.0, manifest["zzshare_max_runtime_seconds"])
        self.assertEqual([], second_calls)
        self.assertEqual("complete", manifest["status"])
        self.assertEqual(0, manifest["executed_bucket_count"])
        self.assertEqual(2, manifest["reused_bucket_count"])
        self.assertEqual(0.0, manifest["current_run_fetch_duration_seconds"])
        self.assertTrue(all(item["reused"] for item in manifest["buckets"]))
        self.assertTrue(
            all(not item["executed_this_run"] for item in manifest["buckets"])
        )

    def test_incremental_execution_resume_refetches_changed_bucket_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)

            def first_executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                return 0

            execute_plan(plan, config, first_executor)
            first_bucket = config["output_dir"] / "buckets" / plan["fetch_buckets"][0]["bucket_id"]
            prices = first_bucket / "prices.csv"
            prices.write_text(
                prices.read_text(encoding="utf-8").replace("10.0", "11.0"),
                encoding="utf-8",
            )
            config["resume"] = True
            calls = []

            def resume_executor(command: list[str]) -> int:
                calls.append(command)
                write_bucket_artifacts(command, rows=1)
                return 0

            manifest = execute_plan(plan, config, resume_executor)

        self.assertEqual(1, len(calls))
        self.assertEqual("complete", manifest["status"])
        self.assertTrue(manifest["buckets"][0]["executed_this_run"])
        self.assertTrue(manifest["buckets"][1]["reused"])

    def test_incremental_combine_csv_preserves_existing_output_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "first.csv"
            second = root / "second.csv"
            output = root / "combined.csv"
            first.write_text("symbol,date\n000001,2026-07-09\n", encoding="utf-8")
            second.write_text("symbol,close\n600000,10.0\n", encoding="utf-8")
            output.write_text("stable\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "columns differ"):
                combine_csv([first, second], output)

            self.assertEqual("stable\n", output.read_text(encoding="utf-8"))

    def test_incremental_execution_resume_rejects_provider_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)

            def executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                return 0

            execute_plan(plan, config, executor)
            config["resume"] = True
            config["provider"] = "pytdx"

            with self.assertRaisesRegex(
                ValueError, "resume manifest execution contract does not match"
            ):
                execute_plan(plan, config, executor)

    def test_incremental_execution_resume_rejects_contract_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)

            def executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                return 0

            execute_plan(plan, config, executor)
            config["resume"] = True
            config["zzshare_non_trading_policy"] = "keep"

            with self.assertRaisesRegex(
                ValueError, "resume manifest execution contract does not match"
            ):
                execute_plan(plan, config, executor)

    def test_incremental_execution_rejects_bucket_provider_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = incremental_execution_plan()
            config = incremental_execution_config(root)

            def executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                metadata_path = Path(command[command.index("--metadata-output") + 1])
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                metadata["source"] = "pytdx"
                metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
                return 0

            manifest = execute_plan(plan, config, executor)

        self.assertEqual("partial", manifest["status"])
        self.assertIn(
            "bucket metadata provider does not match execution contract",
            manifest["buckets"][0]["error"],
        )

    def test_incremental_execution_outputs_pass_verified_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan_data = incremental_execution_plan()
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan_data), encoding="utf-8")
            config = incremental_execution_config(root)
            config["plan_path"] = plan_path

            def executor(command: list[str]) -> int:
                write_bucket_artifacts(command, rows=1)
                return 0

            execute_plan(plan_data, config, executor)
            base_prices = root / "base.csv"
            base_metadata = root / "base_metadata.json"
            base_prices.write_text(
                "symbol,date,close\n000001,2026-07-08,9.8\n600000,2026-07-08,8.8\n",
                encoding="utf-8",
            )
            base_metadata.write_text(
                json.dumps(
                    {
                        "symbols": [
                            {"symbol": "000001", "rows": 1},
                            {"symbol": "600000", "rows": 1},
                        ],
                        "failed_symbols": [],
                        "empty_symbols": [],
                        "possibly_truncated_symbols": [],
                    }
                ),
                encoding="utf-8",
            )
            args = SimpleNamespace(
                base_prices=str(base_prices),
                base_metadata=str(base_metadata),
                merged_output=str(root / "merged.csv"),
                merged_metadata_output=str(root / "merged_metadata.json"),
                merge_report_output=str(root / "merge_report.json"),
            )
            run_verified_merge(args, config)
            merged = Path(args.merged_output).read_text(encoding="utf-8")
            report = json.loads(Path(args.merge_report_output).read_text(encoding="utf-8"))

        self.assertIn("000001,2026-07-09,10.0", merged)
        self.assertIn("600000,2026-07-09,10.0", merged)
        self.assertEqual(2, report["incremental_merge"]["planned_symbol_count"])

    def test_data_source_registry_is_machine_readable(self) -> None:
        registry = json.loads(
            (SKILL_ROOT / "configs/data_sources.json").read_text(encoding="utf-8")
        )
        sources = registry["sources"]

        self.assertEqual(
            "capability_registry_only_not_runtime_source_selection_or_stability_proof",
            registry["claim_boundary"],
        )
        self.assertEqual(
            "ZZSHARE_TOKEN",
            sources["zzshare_history"]["token_environment_variable"],
        )
        self.assertIn(
            "partial_result_true",
            sources["eastmoney_spot"][
                "full_a_recovery_or_reporting_conditions"
            ],
        )
        self.assertNotIn(
            "partial_result_true",
            sources["eastmoney_spot"]["full_a_hard_stop_conditions"],
        )
        self.assertEqual(
            "not_a_share_full_market_path",
            sources["yfinance"]["full_a_role"],
        )

    def test_data_source_registry_primary_fields_have_code_or_doc_evidence(
        self,
    ) -> None:
        registry = json.loads(
            (SKILL_ROOT / "configs/data_sources.json").read_text(encoding="utf-8")
        )
        docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                SKILL_ROOT / "instructions/full-a-strict-workflow.md",
                SKILL_ROOT / "instructions/runbook.md",
                SKILL_ROOT / "references/script-reference.md",
            ]
        )

        for source, metadata in registry["sources"].items():
            with self.subTest(source=source):
                script = (SCRIPTS / metadata["entry"]).read_text(encoding="utf-8")
                evidence = script + "\n" + docs
                for field in metadata["primary_fields"]:
                    self.assertIn(field, evidence)


if __name__ == "__main__":
    unittest.main()
