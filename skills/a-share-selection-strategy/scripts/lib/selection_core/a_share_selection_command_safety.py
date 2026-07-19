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
# Free text has no schema, so this intentionally favors false positives over
# leaking a credential. Structured metadata may preserve only documented bool
# capability fields at its own boundary.
SENSITIVE_KEY_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["']?
        [A-Z0-9_-]*(?:
            ACCESS[_-]?KEY
            |API[_-]?KEY
            |BEARER[_-]?TOKEN
            |CLIENT[_-]?SECRET
            |COOKIE
            |CREDENTIAL
            |ID[_-]?TOKEN
            |PASSPHRASE
            |PASSWORD
            |PRIVATE[_-]?KEY
            |REFRESH[_-]?TOKEN
            |SECRET
            |SESSION(?:[_-]?ID)?
            |SIGNATURE
            |TOKEN
        )[A-Z0-9_-]*
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
TOKEN_CONFIGURED_FLAG_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        --TOKEN(?:[_-]?CONFIGURED|CONFIGURED)\b
        [ \t]+
    )
    (?P<value>
        "(?:\\.|[^"\\])*"
        |'(?:\\.|[^'\\])*'
        |(?!--)[^\s,;&}\]]+
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
QUOTED_COOKIE_QUOTED_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["'][A-Z0-9_-]*COOKIE[A-Z0-9_-]*["']
        \s*[:=]\s*
    )
    (?P<value>
        "(?:\\.|[^"\\])*"
        |'(?:\\.|[^'\\])*'
    )
    """
)
QUOTED_COOKIE_BARE_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["'][A-Z0-9_-]*COOKIE[A-Z0-9_-]*["']
        \s*[:=]
    )
    (?!\s*["'])
    (?P<spacing>\s*)
    (?:
        (?P<value_with_closing>[^\r\n]*?(?:\r?\n[ \t]+[^\r\n]*?)*)
        (?P<closing>[}\]]+)
        (?=\s*(?:,\s*["'][^"']+["']\s*[:=]|\r?\n|$))
        |
        (?P<value>[^\r\n]*?(?:\r?\n[ \t]+[^\r\n]*?)*)
        (?=\s*,\s*["'][^"']+["']\s*[:=]|\r?\n(?![ \t])|$)
    )
    """
)
UNQUOTED_COOKIE_HEADER_RE = re.compile(
    r"""(?ix)
    (?<!["'A-Z0-9_-])
    (?P<prefix>
        [A-Z0-9_-]*COOKIE[A-Z0-9_-]*
        \s*:\s*
    )
    (?P<value>[^\r\n]*(?:\r?\n[ \t]+[^\r\n]*)*)
    """
)
UNQUOTED_COOKIE_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    (?<!["'A-Z0-9_-])
    (?P<prefix>
        [A-Z0-9_-]*COOKIE[A-Z0-9_-]*
        \s*=\s*
    )
    (?P<value>
        [^\s;,\r\n]+(?:\s*=\s*[^\s;,\r\n]+)?
        (?:\s*[;,]\s*[^\s;,\r\n]+(?:\s*=\s*[^\s;,\r\n]+)?)*
        (?:\r?\n[ \t]+[^\r\n]*)*
    )
    """
)
AUTHORIZATION_RE = re.compile(
    r"(?i)\b(?P<prefix>(?:Proxy-)?Authorization\s*[:=]\s*)"
    r"(?P<value>[^\r\n]*?(?:\r?\n[ \t]+[^\r\n]*?)*)"
    r"(?=\s+(?:Proxy-)?Authorization\s*[:=]|\r?\n(?![ \t])|$)"
)
OPENAI_STYLE_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)
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
    "accesstoken",
    "apikey",
    "bearertoken",
    "clientsecret",
    "cookie",
    "credential",
    "idtoken",
    "passphrase",
    "password",
    "privatekey",
    "proxyauthorization",
    "refreshtoken",
    "secret",
    "sessionid",
    "setcookie",
    "signature",
    "token",
}
SENSITIVE_MAPPING_VALUE_KEYS = {
    "access_key",
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "bearer_token",
    "client_secret",
    "cookie",
    "credential",
    "credentials",
    "id_token",
    "key",
    "password",
    "passphrase",
    "private_key",
    "proxy_authorization",
    "refresh_token",
    "secret",
    "session",
    "session_id",
    "set_cookie",
    "sig",
    "signature",
    "token",
}
SENSITIVE_MAPPING_VALUE_KEY_COMPONENTS = {
    "authorization",
    "cookie",
    "credential",
    "password",
    "passphrase",
    "secret",
    "session",
    "signature",
    "token",
}
IDENTIFIER_CASE_BOUNDARY_RE = re.compile(
    r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])"
)
SENSITIVE_COMPACT_MAPPING_VALUE_KEYS = {
    key.replace("_", "") for key in SENSITIVE_MAPPING_VALUE_KEYS
}
SAFE_SENSITIVE_QUERY_KEY_NAMES = SENSITIVE_MAPPING_VALUE_KEYS | {
    "access_key_id",
    "x_amz_credential",
    "x_amz_security_token",
    "x_amz_signature",
    "x_api_key",
}
SAFE_SENSITIVE_QUERY_KEY_COMPACT_NAMES = {
    key.replace("_", "") for key in SAFE_SENSITIVE_QUERY_KEY_NAMES
}
SENSITIVE_COMMAND_FLAG_KEYS = SAFE_SENSITIVE_QUERY_KEY_NAMES | {
    "auth_token",
    "cookies",
    "secret_key",
    "session_token",
    "token_configured",
}
SENSITIVE_COMMAND_FLAG_COMPACT_NAMES = {
    key.replace("_", "") for key in SENSITIVE_COMMAND_FLAG_KEYS
}
SENSITIVE_EMBEDDED_COMMAND_FLAG_PREFIXES = {
    "accesskey",
    "accesstoken",
    "apikey",
    "bearertoken",
    "clientsecret",
    "cookie",
    "idtoken",
    "privatekey",
    "proxyauthorization",
    "refreshtoken",
    "secretkey",
    "sessionid",
    "sessiontoken",
    "setcookie",
    "authtoken",
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
        sensitive_flag, embedded_name = classify_sensitive_flag(flag)
        if sensitive_flag:
            sanitized_flag = f"--{REDACTED} flag" if embedded_name else flag
            if separator:
                sanitized.append(f"{sanitized_flag}={REDACTED}")
            else:
                sanitized.append(sanitized_flag)
                redact_next = True
            continue
        sanitized.append(sanitize_text(text))
    return sanitized


def classify_sensitive_flag(flag: str) -> tuple[bool, bool]:
    if not flag.startswith("--"):
        return False, False
    raw_key = flag.lstrip("-")
    normalized = normalize_query_key(raw_key)
    if normalized in SENSITIVE_COMMAND_FLAG_KEYS:
        return True, False
    compact = re.sub(r"[^a-z0-9]+", "", raw_key.lower())
    if compact in SENSITIVE_COMMAND_FLAG_COMPACT_NAMES:
        return True, False
    embedded = any(
        prefix in compact and compact != prefix
        for prefix in SENSITIVE_EMBEDDED_COMMAND_FLAG_PREFIXES
    )
    return embedded, embedded


def sanitize_text(text: str) -> str:
    sanitized = OPENAI_STYLE_KEY_RE.sub(REDACTED, text)
    sanitized = TOKEN_CONFIGURED_FLAG_VALUE_RE.sub(
        redact_sensitive_key_value,
        sanitized,
    )
    sanitized = QUOTED_AUTHORIZATION_RE.sub(redact_sensitive_key_value, sanitized)
    sanitized = QUOTED_COOKIE_QUOTED_VALUE_RE.sub(
        redact_sensitive_key_value,
        sanitized,
    )
    sanitized = QUOTED_COOKIE_BARE_VALUE_RE.sub(
        redact_cookie_bare_value,
        sanitized,
    )
    sanitized = UNQUOTED_COOKIE_HEADER_RE.sub(redact_cookie_header_value, sanitized)
    sanitized = UNQUOTED_COOKIE_ASSIGNMENT_RE.sub(
        redact_cookie_assignment_value,
        sanitized,
    )
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


def redact_cookie_header_value(match: re.Match[str]) -> str:
    return f"{match.group('prefix')}{REDACTED}"


def redact_cookie_bare_value(match: re.Match[str]) -> str:
    closing = match.group("closing") or ""
    return f"{match.group('prefix')}{match.group('spacing')}{REDACTED}{closing}"


def redact_cookie_assignment_value(match: re.Match[str]) -> str:
    if is_url_query_context(match):
        return match.group(0)
    return redact_cookie_header_value(match)


def is_url_query_context(match: re.Match[str]) -> bool:
    for url_match in URL_RE.finditer(match.string):
        if not url_match.start() <= match.start() < url_match.end():
            continue
        offset = match.start() - url_match.start()
        return offset > 0 and url_match.group(0)[offset - 1] in {"?", "&", "#"}
    return False


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
            sanitized_key = sanitize_query_key(key)
            sanitized_pairs.append((sanitized_key, REDACTED))
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


def sanitize_query_key(key: str) -> str:
    normalized = normalize_query_key(key)
    compact = re.sub(r"[^a-z0-9]+", "", key.lower())
    if (
        normalized in SAFE_SENSITIVE_QUERY_KEY_NAMES
        or compact in SAFE_SENSITIVE_QUERY_KEY_COMPACT_NAMES
    ):
        return key
    return f"{REDACTED} key"


def is_sensitive_query_key(key: str) -> bool:
    normalized = normalize_query_key(key)
    compact = re.sub(r"[^a-z0-9]+", "", key.lower())
    components = set(normalized.split("_"))
    return (
        normalized in SENSITIVE_QUERY_KEYS
        or normalized in SENSITIVE_MAPPING_VALUE_KEYS
        or compact in SENSITIVE_QUERY_KEYS
        or compact in SENSITIVE_COMPACT_MAPPING_VALUE_KEYS
        or bool(components & SENSITIVE_QUERY_KEY_COMPONENTS)
        or bool(components & SENSITIVE_MAPPING_VALUE_KEY_COMPONENTS)
        or any(phrase in normalized for phrase in SENSITIVE_QUERY_KEY_PHRASES)
        or any(phrase in compact for phrase in SENSITIVE_COMPACT_QUERY_KEY_PHRASES)
    )


def is_sensitive_mapping_value_key(key: object) -> bool:
    if not isinstance(key, str):
        return False
    normalized = normalize_query_key(key)
    compact = re.sub(r"[^a-z0-9]+", "", key.lower())
    return (
        normalized in SENSITIVE_MAPPING_VALUE_KEYS
        or compact in SENSITIVE_COMPACT_MAPPING_VALUE_KEYS
        or is_sensitive_query_key(key)
        or bool(set(normalized.split("_")) & SENSITIVE_MAPPING_VALUE_KEY_COMPONENTS)
    )


def sanitize_mapping_key(key: object) -> str:
    raw_key = str(key)
    sanitized = sanitize_text(raw_key)
    if sanitized != raw_key:
        return sanitized
    normalized = normalize_query_key(raw_key)
    if normalized in SENSITIVE_MAPPING_VALUE_KEYS or normalized == "token_configured":
        return sanitized
    if is_sensitive_mapping_value_key(raw_key):
        return f"{REDACTED} key"
    return sanitized


def normalize_query_key(key: str) -> str:
    separated = IDENTIFIER_CASE_BOUNDARY_RE.sub("_", key)
    return re.sub(r"[^a-z0-9]+", "_", separated.lower()).strip("_")
