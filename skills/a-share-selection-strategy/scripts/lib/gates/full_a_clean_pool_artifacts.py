"""Fingerprint and resolve full-A provenance artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def artifact_fingerprints(
    paths: dict[str, Path], display_paths: dict[str, Path]
) -> dict[str, dict[str, Any]]:
    return {
        name: artifact_fingerprint(path, display_paths.get(name))
        for name, path in paths.items()
    }


def artifact_fingerprint(path: Path, display_path: Path | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"provenance artifact not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str((display_path or path).resolve()),
        "size_bytes": int(path.stat().st_size),
        "sha256": digest.hexdigest(),
    }


def artifact_identity_matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return all(
        expected.get(key) == actual.get(key)
        for key in ("path", "size_bytes", "sha256")
    )


def same_content_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(left.get(key) == right.get(key) for key in ("size_bytes", "sha256"))


def artifact_path_from(artifacts: dict[str, Any], name: str) -> Path:
    record = artifacts.get(name)
    if not isinstance(record, dict):
        raise ValueError(f"full-A provenance artifact is invalid: {name}")
    path = str(record.get("path", "")).strip()
    if not path:
        raise ValueError(f"full-A provenance artifact path is missing: {name}")
    return Path(path)
