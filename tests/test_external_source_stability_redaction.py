from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "a-share-selection-strategy" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import probe_external_source_stability as probe  # noqa: E402
from lib.selection_core.a_share_selection_command_safety import (  # noqa: E402
    classify_sensitive_flag,
    is_sensitive_mapping_value_key,
    normalize_query_key,
    sanitize_command,
    sanitize_text,
)


class ExternalSourceStabilityRedactionTests(unittest.TestCase):
    def test_camel_case_and_acronym_sensitive_keys_are_recognized(self) -> None:
        expected_normalized = {
            "clientSecret": "client_secret",
            "PrivateKey": "private_key",
            "bearerToken": "bearer_token",
            "refreshToken": "refresh_token",
            "sessionId": "session_id",
            "tokenConfigured": "token_configured",
            "APIKey": "api_key",
            "IDToken": "id_token",
            "OAuthToken": "o_auth_token",
            "AWSSecretAccessKey": "aws_secret_access_key",
        }

        for key, normalized in expected_normalized.items():
            with self.subTest(key=key):
                self.assertEqual(normalized, normalize_query_key(key))
                self.assertTrue(is_sensitive_mapping_value_key(key))

    def test_persisted_mapping_redacts_camel_case_sensitive_values(self) -> None:
        values = {
            "clientSecret": "probe-secret-client-secret",
            "PrivateKey": "probe-secret-private-key",
            "bearerToken": "probe-secret-bearer-token",
            "refreshToken": "probe-secret-refresh-token",
            "sessionId": "probe-secret-session-id",
            "tokenConfigured": False,
        }

        sanitized = probe.sanitize_persisted_value(values)

        self.assertEqual(False, sanitized["tokenConfigured"])
        self.assertEqual(
            {"tokenConfigured": True},
            probe.sanitize_persisted_value({"tokenConfigured": True}),
        )
        self.assertEqual(
            {"TokenConfigured": True},
            probe.sanitize_persisted_value({"TokenConfigured": True}),
        )
        self.assertEqual(
            {"[REDACTED]"},
            {
                sanitized[key]
                for key in [
                    "clientSecret",
                    "PrivateKey",
                    "bearerToken",
                    "refreshToken",
                    "sessionId",
                ]
            },
        )
        self.assertEqual(
            {"tokenConfigured": "[REDACTED]"},
            probe.sanitize_persisted_value(
                {"tokenConfigured": "probe-secret-invalid-status"}
            ),
        )
        for secret in (
            "probe-secret-client-secret",
            "probe-secret-private-key",
            "probe-secret-bearer-token",
            "probe-secret-refresh-token",
            "probe-secret-session-id",
            "probe-secret-invalid-status",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, str(sanitized))

    def test_only_structured_bool_token_configured_preserves_capability_state(
        self,
    ) -> None:
        self.assertEqual(
            "tokenConfigured=[REDACTED] token_configured=[REDACTED]",
            sanitize_text("tokenConfigured=true token_configured=false"),
        )
        self.assertEqual(
            "--tokenConfigured [REDACTED] "
            "--token_configured [REDACTED] "
            "--token-configured [REDACTED]",
            sanitize_text(
                "--tokenConfigured true "
                "--token_configured false "
                "--token-configured probe-secret-free-text"
            ),
        )
        self.assertEqual(
            {"tokenConfigured": True, "token_configured": False},
            probe.sanitize_persisted_value(
                {"tokenConfigured": True, "token_configured": False}
            ),
        )
        self.assertEqual(
            {
                "tokenConfigured": "[REDACTED]",
                "token_configured": "[REDACTED]",
            },
            probe.sanitize_persisted_value(
                {
                    "tokenConfigured": "probe-secret-not-a-bool",
                    "token_configured": "probe-secret-not-a-bool-either",
                }
            ),
        )

    def test_command_redacts_token_configured_capability_flags(self) -> None:
        command = [
            "tool",
            "--tokenConfigured",
            "true",
            "--token_configured",
            "false",
            "--token-configured=true",
            "--tokenConfigured=false",
        ]

        self.assertEqual(
            [
                "tool",
                "--tokenConfigured",
                "[REDACTED]",
                "--token_configured",
                "[REDACTED]",
                "--token-configured=[REDACTED]",
                "--tokenConfigured=[REDACTED]",
            ],
            sanitize_command(command),
        )

    def test_persisted_mapping_redacts_embedded_credential_key_names(self) -> None:
        values = {
            "apiKey_probe-secret-key-name": "probe-secret-api-value",
            "clientSecret_probe-secret-client-name": "probe-secret-client-value",
            "clientSecretprobesecretvalue": "probe-secret-unseparated-value",
        }

        sanitized = probe.sanitize_persisted_value(values)

        self.assertEqual(
            [
                "[REDACTED] key",
                "[REDACTED] key [duplicate 2]",
                "[REDACTED] key [duplicate 3]",
            ],
            sorted(sanitized),
        )
        self.assertEqual({"[REDACTED]"}, set(sanitized.values()))
        for secret in (
            "probe-secret-key-name",
            "probe-secret-api-value",
            "probe-secret-client-name",
            "probe-secret-client-value",
            "probesecretvalue",
            "probe-secret-unseparated-value",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, str(sanitized))

    def test_command_redacts_normalized_separated_sensitive_flags(self) -> None:
        command = [
            "tool",
            "--private-key",
            "probe-secret-private-key",
            "--privateKey",
            "probe-secret-private-key-camel",
            "--refreshToken",
            "probe-secret-refresh-token",
            "--session-id",
            "probe-secret-session-id",
            "--cookie",
            "probe-secret-cookie",
            "--session-timeout",
            "10",
        ]

        sanitized = sanitize_command(command)

        self.assertEqual(
            [
                "tool",
                "--private-key",
                "[REDACTED]",
                "--privateKey",
                "[REDACTED]",
                "--refreshToken",
                "[REDACTED]",
                "--session-id",
                "[REDACTED]",
                "--cookie",
                "[REDACTED]",
                "--session-timeout",
                "10",
            ],
            sanitized,
        )

    def test_command_redacts_compact_standard_sensitive_flags(self) -> None:
        flag_names = (
            "clientsecret",
            "privatekey",
            "sessionid",
            "refreshtoken",
            "bearertoken",
            "setcookie",
            "apikey",
            "secret-key",
            "secretkey",
            "auth-token",
            "authtoken",
            "session-token",
            "sessiontoken",
        )
        command = ["tool"]
        expected = ["tool"]
        secrets = []
        for flag_name in flag_names:
            separated_secret = f"probe-secret-{flag_name}-separated"
            assigned_secret = f"probe-secret-{flag_name}-assigned"
            command.extend(
                [
                    f"--{flag_name}",
                    separated_secret,
                    f"--{flag_name}={assigned_secret}",
                ]
            )
            expected.extend(
                [
                    f"--{flag_name}",
                    "[REDACTED]",
                    f"--{flag_name}=[REDACTED]",
                ]
            )
            secrets.extend([separated_secret, assigned_secret])

        sanitized = sanitize_command(command)

        self.assertEqual(expected, sanitized)
        for flag_name in flag_names:
            with self.subTest(flag_name=flag_name):
                self.assertEqual(
                    (True, False),
                    classify_sensitive_flag(f"--{flag_name}"),
                )
        for secret in secrets:
            with self.subTest(secret=secret):
                self.assertNotIn(secret, " ".join(sanitized))

    def test_command_masks_embedded_sensitive_flag_names(self) -> None:
        command = [
            "tool",
            "--clientSecretprobe-secret-in-flag",
            "probe-secret-command-value",
            "--privateKeyprobe-secret-in-flag=probe-secret-command-equals-value",
            "--secretKeyprobe-secret-in-flag",
            "probe-secret-secret-key-command-value",
            "--AWSSecretAccessKey",
            "probe-secret-aws-access-key",
        ]

        sanitized = sanitize_command(command)

        self.assertEqual(
            [
                "tool",
                "--[REDACTED] flag",
                "[REDACTED]",
                "--[REDACTED] flag=[REDACTED]",
                "--[REDACTED] flag",
                "[REDACTED]",
                "--[REDACTED] flag",
                "[REDACTED]",
            ],
            sanitized,
        )
        self.assertEqual((True, True), classify_sensitive_flag("--clientSecretvalue"))
        self.assertEqual((True, True), classify_sensitive_flag("--secretKeyvalue"))
        self.assertEqual((True, True), classify_sensitive_flag("--AWSSecretAccessKey"))
        self.assertEqual((False, False), classify_sensitive_flag("--session-timeout"))
        self.assertEqual((False, False), classify_sensitive_flag("clientSecret"))
        for secret in (
            "probe-secret-in-flag",
            "probe-secret-command-value",
            "probe-secret-command-equals-value",
            "probe-secret-secret-key-command-value",
            "probe-secret-aws-access-key",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, " ".join(sanitized))

    def test_command_preserves_sensitive_named_position_and_next_flag(self) -> None:
        command = ["tool", "token", "--safe", "retained"]

        self.assertEqual(command, sanitize_command(command))

    def test_metadata_masks_sensitive_key_names_preserved_in_url_queries(self) -> None:
        sanitized = probe.sanitize_persisted_value(
            {
                "ToKeN": "probe-secret-token",
                "accessKeyId": "probe-secret-access-key-id",
                "X-Amz-Credential": "probe-secret-credential",
            }
        )

        self.assertEqual(
            {
                "[REDACTED] key": "[REDACTED]",
                "[REDACTED] key [duplicate 2]": "[REDACTED]",
                "[REDACTED] key [duplicate 3]": "[REDACTED]",
            },
            sanitized,
        )

    def test_text_and_urls_redact_camel_case_sensitive_key_values(self) -> None:
        text = (
            "privateKey=probe-secret-private-key "
            '"sessionId": "probe-secret-session-id" '
            "passphrase=probe-secret-passphrase "
            "Cookie=probe-secret-cookie "
            "url=https://example.test/?privateKey=probe-secret-private-url&"
            "sessionId=probe-secret-session-url&"
            "clientSecretprobesecretvalue=probe-secret-unseparated-url&"
            "ToKeN=probe-secret-token-url&"
            "accessKeyId=probe-secret-access-key-id-url&"
            "X-Amz-Credential=probe-secret-credential-url"
        )

        sanitized = sanitize_text(text)

        self.assertIn("privateKey=[REDACTED]", sanitized)
        self.assertIn('"sessionId": "[REDACTED]"', sanitized)
        self.assertIn("passphrase=[REDACTED]", sanitized)
        self.assertIn("Cookie=[REDACTED]", sanitized)
        self.assertIn("privateKey=%5BREDACTED%5D", sanitized)
        self.assertIn("sessionId=%5BREDACTED%5D", sanitized)
        self.assertIn("ToKeN=%5BREDACTED%5D", sanitized)
        self.assertIn("accessKeyId=%5BREDACTED%5D", sanitized)
        self.assertIn("X-Amz-Credential=%5BREDACTED%5D", sanitized)
        self.assertIn(
            "%5BREDACTED%5D+key=%5BREDACTED%5D",
            sanitized,
        )
        self.assertNotIn("clientSecretprobesecretvalue", sanitized)
        for secret in (
            "probe-secret-private-key",
            "probe-secret-session-id",
            "probe-secret-passphrase",
            "probe-secret-cookie",
            "probe-secret-private-url",
            "probe-secret-session-url",
            "probe-secret-unseparated-url",
            "probe-secret-token-url",
            "probe-secret-access-key-id-url",
            "probe-secret-credential-url",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, sanitized)

    def test_uppercase_url_scheme_uses_structured_cookie_query_redaction(self) -> None:
        text = "HTTPS://example.test/?set_cookie=probe-secret-upper-url&safe=retained"

        sanitized = sanitize_text(text)

        self.assertIn("set_cookie=%5BREDACTED%5D", sanitized)
        self.assertIn("safe=retained", sanitized)
        self.assertNotIn("probe-secret-upper-url", sanitized)

    def test_cookie_assignment_after_url_delimiter_is_not_misclassified_as_query(self) -> None:
        text = "https://example.test/?safe=retained] Cookie=probe-secret-after-url"

        sanitized = sanitize_text(text)

        self.assertIn("safe=retained]", sanitized)
        self.assertIn("Cookie=[REDACTED]", sanitized)
        self.assertNotIn("probe-secret-after-url", sanitized)

    def test_cookie_headers_redact_every_cookie_value_on_the_line(self) -> None:
        text = (
            "Cookie: session=probe-secret-session; theme=probe-secret-theme\n"
            "Set-Cookie: refresh=probe-secret-refresh; HttpOnly; Secure\n"
            "Cookie=session=probe-secret-assignment; theme=probe-secret-assignment-theme "
            "url=https://example.test/safe\n"
            "Cookie=one=probe-secret-comma, two=probe-secret-comma-two\n"
            "Cookie=session=probe-secret-ampersand-one&probe-secret-ampersand-two\n"
            "set_cookie: one=probe-secret-snake-one; two=probe-secret-snake-two\n"
            "Set_Cookie: one=probe-secret-pascal-snake-one; two=probe-secret-pascal-snake-two\n"
            "cookies=one=probe-secret-plural-one, two=probe-secret-plural-two\n"
            "url=https://example.test/?set_cookie=probe-secret-query-cookie&safe=retained\n"
            '"Cookie": "csrf=probe-secret-csrf; locale=probe-secret-locale", '
            '"safe": "retained"'
        )

        sanitized = sanitize_text(text)

        self.assertEqual(
            "Cookie: [REDACTED]\n"
            "Set-Cookie: [REDACTED]\n"
            "Cookie=[REDACTED] url=https://example.test/safe\n"
            "Cookie=[REDACTED]\n"
            "Cookie=[REDACTED]\n"
            "set_cookie: [REDACTED]\n"
            "Set_Cookie: [REDACTED]\n"
            "cookies=[REDACTED]\n"
            "url=https://example.test/?set_cookie=%5BREDACTED%5D&safe=retained\n"
            '"Cookie": "[REDACTED]", "safe": "retained"',
            sanitized,
        )
        for secret in (
            "probe-secret-session",
            "probe-secret-theme",
            "probe-secret-refresh",
            "probe-secret-assignment",
            "probe-secret-assignment-theme",
            "probe-secret-comma",
            "probe-secret-comma-two",
            "probe-secret-ampersand-one",
            "probe-secret-ampersand-two",
            "probe-secret-snake-one",
            "probe-secret-snake-two",
            "probe-secret-pascal-snake-one",
            "probe-secret-pascal-snake-two",
            "probe-secret-plural-one",
            "probe-secret-plural-two",
            "probe-secret-query-cookie",
            "probe-secret-csrf",
            "probe-secret-locale",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, sanitized)

    def test_quoted_cookie_keys_redact_unquoted_values(self) -> None:
        text = (
            '"Cookie": csrf=probe-secret-json-csrf^suffix; '
            'locale=probe-secret-json-locale, "safe": "retained"\n'
            "'Set-Cookie': session=probe-secret-json-session; "
            "theme=probe-secret-json-theme, 'safe': 'retained'\n"
            '"cookies": one=probe-secret-json-one, '
            'two=probe-secret-json-two, "safe": "retained"'
        )

        sanitized = sanitize_text(text)

        self.assertEqual(
            '"Cookie": [REDACTED], "safe": "retained"\n'
            "'Set-Cookie': [REDACTED], 'safe': 'retained'\n"
            '"cookies": [REDACTED], "safe": "retained"',
            sanitized,
        )
        for secret in (
            "probe-secret-json-csrf^suffix",
            "probe-secret-json-locale",
            "probe-secret-json-session",
            "probe-secret-json-theme",
            "probe-secret-json-one",
            "probe-secret-json-two",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, sanitized)

    def test_quoted_cookie_keys_preserve_closing_mapping_delimiters(self) -> None:
        text = (
            '{"Cookie": "probe-secret-closing-quoted"}\n'
            "{'Set_Cookie': probe-secret-closing-unquoted]"
            "probe-secret-after-bracket}\n"
            '{"cookies": "one=probe-secret-closing-one, '
            'two=probe-secret-closing-two"}'
        )

        sanitized = sanitize_text(text)

        self.assertEqual(
            '{"Cookie": "[REDACTED]"}\n'
            "{'Set_Cookie': [REDACTED]}\n"
            '{"cookies": "[REDACTED]"}',
            sanitized,
        )
        for secret in (
            "probe-secret-closing-quoted",
            "probe-secret-closing-unquoted",
            "probe-secret-after-bracket",
            "probe-secret-closing-one",
            "probe-secret-closing-two",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, sanitized)

    def test_cookie_headers_redact_folded_lines(self) -> None:
        text = (
            "Cookie: session=probe-secret-folded-session\r\n"
            "  theme=probe-secret-folded-theme\r\n"
            "Set-Cookie: refresh=probe-secret-folded-refresh\r\n"
            "\tHttpOnly; Secure\r\n"
            "set_cookie: session=probe-secret-folded-snake-session\n"
            "  theme=probe-secret-folded-snake-theme\n"
            "cookies=one=probe-secret-folded-assignment-one\r\n"
            "\ttwo=probe-secret-folded-assignment-two\r\n"
            "next=safe"
        )

        sanitized = sanitize_text(text)

        self.assertEqual(
            "Cookie: [REDACTED]\r\n"
            "Set-Cookie: [REDACTED]\r\n"
            "set_cookie: [REDACTED]\n"
            "cookies=[REDACTED]\r\n"
            "next=safe",
            sanitized,
        )
        for secret in (
            "probe-secret-folded-session",
            "probe-secret-folded-theme",
            "probe-secret-folded-refresh",
            "probe-secret-folded-snake-session",
            "probe-secret-folded-snake-theme",
            "probe-secret-folded-assignment-one",
            "probe-secret-folded-assignment-two",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, sanitized)


if __name__ == "__main__":
    unittest.main()
