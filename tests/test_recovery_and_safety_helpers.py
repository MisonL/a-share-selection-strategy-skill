from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.selection_core.a_share_selection_command_safety import (  # noqa: E402
    SENSITIVE_FLAG_NAMES,
    sanitize_command,
    sanitize_text,
)
from prepare_history_retry_symbols import build_retry_plan  # noqa: E402
from lib.runner.run_today_a_share_selection_parser import build_parser  # noqa: E402


class RecoveryAndSafetyHelperTests(unittest.TestCase):
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
                if flag.lower() not in SENSITIVE_FLAG_NAMES
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
            "partial_result=true",
            sources["eastmoney_spot"]["full_a_stop_conditions"],
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
