"""Command and log redaction helpers for persisted run artifacts."""

from __future__ import annotations

if __name__ == "__main__":
    import sys
    from pathlib import Path

    _SCRIPT_PATH = Path(__file__).resolve()
    _SCRIPTS_DIR = next(
        parent for parent in _SCRIPT_PATH.parents if parent.name == "scripts"
    )
    sys.path.insert(0, str(_SCRIPTS_DIR))
    from lib.a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)


import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


REDACTED = "[REDACTED]"
SENSITIVE_FLAG_NAMES = {
    "--api-key",
    "--apikey",
    "--authorization",
    "--bearer-token",
    "--client-secret",
    "--password",
    "--secret",
    "--token",
}
SENSITIVE_KEY_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["']?
        [A-Z0-9_-]*(?:ACCESS[_-]?KEY|API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|SIGNATURE)[A-Z0-9_-]*
        ["']?
        \s*[:=]\s*
    )
    (?P<value>
        "(?:\\.|[^"\\])*"
        |'(?:\\.|[^'\\])*'
        |[^\s&,}]+
    )
    """
)
QUOTED_AUTHORIZATION_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["'](?:Proxy-)?Authorization["']
        \s*[:=]\s*
    )
    (?P<value>
        "(?:\\.|[^"\\])*"
        |'(?:\\.|[^'\\])*'
    )
    """
)
AUTHORIZATION_RE = re.compile(
    r"(?i)\b(?P<prefix>(?:Proxy-)?Authorization\s*[:=]\s*)"
    r"(?P<value>[^\r\n]*?(?:\r?\n[ \t]+[^\r\n]*?)*)"
    r"(?=\s+(?:Proxy-)?Authorization\s*[:=]|\r?\n(?![ \t])|$)"
)
OPENAI_STYLE_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
URL_RE = re.compile(r"https?://[^\s]+")
KNOWN_AUTHORIZATION_SCHEMES = {
    "apikey",
    "aws4-hmac-sha256",
    "basic",
    "bearer",
    "digest",
    "dpop",
    "mac",
    "negotiate",
    "ntlm",
    "token",
}
SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "key",
    "password",
    "secret",
    "sig",
    "token",
}
SENSITIVE_QUERY_KEY_COMPONENTS = {
    "credential",
    "password",
    "secret",
    "signature",
    "token",
}
SENSITIVE_QUERY_KEY_PHRASES = {
    "access_key",
    "api_key",
}
SENSITIVE_COMPACT_QUERY_KEY_PHRASES = {
    "accesskey",
    "apikey",
}


def sanitize_command(command: list[Any]) -> list[str]:
    sanitized = []
    redact_next = False
    for part in command:
        text = str(part)
        if redact_next:
            sanitized.append(REDACTED)
            redact_next = False
            continue
        flag, separator, value = text.partition("=")
        normalized = flag.lower()
        if normalized in SENSITIVE_FLAG_NAMES:
            if separator:
                sanitized.append(f"{flag}={REDACTED}")
            else:
                sanitized.append(text)
                redact_next = True
            continue
        sanitized.append(sanitize_text(text))
    return sanitized


def sanitize_text(text: str) -> str:
    sanitized = OPENAI_STYLE_KEY_RE.sub(REDACTED, text)
    sanitized = QUOTED_AUTHORIZATION_RE.sub(redact_sensitive_key_value, sanitized)
    sanitized = AUTHORIZATION_RE.sub(
        redact_authorization_value,
        sanitized,
    )
    sanitized = SENSITIVE_KEY_VALUE_RE.sub(redact_sensitive_key_value, sanitized)
    return sanitize_urls(sanitized)


def redact_authorization_value(match: re.Match[str]) -> str:
    value = match.group("value").lstrip()
    scheme, separator, _rest = value.partition(" ")
    if separator and scheme.lower() in KNOWN_AUTHORIZATION_SCHEMES:
        return f"{match.group('prefix')}{scheme} {REDACTED}"
    return f"{match.group('prefix')}{REDACTED}"


def redact_sensitive_key_value(match: re.Match[str]) -> str:
    value = match.group("value")
    quote = value[:1] if value[:1] in {"'", '"'} and value[-1:] == value[:1] else ""
    if quote:
        return f"{match.group('prefix')}{quote}{REDACTED}{quote}"
    return f"{match.group('prefix')}{REDACTED}"


def sanitize_urls(text: str) -> str:
    if "://" not in text:
        return text
    return URL_RE.sub(lambda match: sanitize_single_url(match.group(0)), text)


def sanitize_single_url(text: str) -> str:
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    netloc = sanitize_url_netloc(parts.netloc)
    query = sanitize_url_key_values(parts.query)
    fragment = sanitize_url_fragment_key_values(parts.fragment)
    if netloc == parts.netloc and query == parts.query and fragment == parts.fragment:
        return text
    return urlunsplit((parts.scheme, netloc, parts.path, query, fragment))


def sanitize_url_key_values(text: str) -> str:
    pairs = parse_qsl(text, keep_blank_values=True)
    if not pairs:
        return text
    sanitized_pairs = []
    changed = False
    for key, value in pairs:
        if is_sensitive_query_key(key):
            sanitized_pairs.append((key, REDACTED))
            changed = True
            continue
        sanitized_value = sanitize_nested_query_value(value)
        sanitized_pairs.append((key, sanitized_value))
        if sanitized_value != value:
            changed = True
    if not changed:
        return text
    return urlencode(sanitized_pairs)


def sanitize_nested_query_value(value: str) -> str:
    sanitized = sanitize_urls(value) if "://" in value else value
    if has_leading_key_value(sanitized):
        sanitized = sanitize_url_key_values(sanitized)
    return sanitized


def sanitize_url_fragment_key_values(text: str) -> str:
    # urlsplit passes the fragment without "#"; urlunsplit restores it.
    if has_leading_key_value(text):
        return sanitize_url_key_values(text)
    route, separator, query = text.partition("?")
    if not separator:
        return text
    sanitized_query = sanitize_url_key_values(query)
    if sanitized_query == query:
        return text
    return f"{route}{separator}{sanitized_query}"


def has_leading_key_value(text: str) -> bool:
    if "=" not in text:
        return False
    key = text.split("=", 1)[0]
    return bool(key) and not any(separator in key for separator in "/?#")


def sanitize_url_netloc(netloc: str) -> str:
    if "@" not in netloc:
        return netloc
    _userinfo, host = netloc.rsplit("@", 1)
    if not host:
        return netloc
    return f"{REDACTED}@{host}"


def is_sensitive_query_key(key: str) -> bool:
    normalized = normalize_query_key(key)
    compact = re.sub(r"[^a-z0-9]+", "", key.lower())
    components = set(normalized.split("_"))
    return (
        normalized in SENSITIVE_QUERY_KEYS
        or bool(components & SENSITIVE_QUERY_KEY_COMPONENTS)
        or any(phrase in normalized for phrase in SENSITIVE_QUERY_KEY_PHRASES)
        or any(phrase in compact for phrase in SENSITIVE_COMPACT_QUERY_KEY_PHRASES)
    )


def normalize_query_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
