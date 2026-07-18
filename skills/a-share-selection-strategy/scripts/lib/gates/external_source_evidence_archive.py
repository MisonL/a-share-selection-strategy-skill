"""Build and verify compact archives for external-source probe evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Any


ARCHIVE_SCHEMA_VERSION = 1
ARCHIVE_DIRECTORY_MODE = 0o700
ARCHIVE_TYPE = "external_source_stability_compact_evidence"
ARCHIVE_CLAIM_BOUNDARY = (
    "control_plane_evidence_only_not_price_data_or_long_term_stability_proof"
)
SOURCE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def validate_archive_destination(
    archive_dir: Path,
    output_dir: Path,
    summary_output: Path,
) -> None:
    archive = resolve_new_archive_directory(archive_dir)
    output = output_dir.resolve()
    summary = summary_output.resolve()
    if paths_overlap(archive, output):
        raise ValueError("archive directory must not overlap --output-dir")
    if paths_overlap(archive, summary):
        raise ValueError("summary output must not overlap --archive-dir")


def resolve_new_archive_directory(archive_dir: Path) -> Path:
    """Resolve a fresh archive destination without following a leaf symlink."""
    if archive_dir.exists() or archive_dir.is_symlink():
        raise ValueError(f"archive directory must not already exist: {archive_dir}")
    archive = archive_dir.resolve()
    if archive.exists() or archive.is_symlink():
        raise ValueError(f"archive directory must not already exist: {archive}")
    return archive


def archive_evidence(manifest: dict[str, Any], archive_dir: Path) -> None:
    """Atomically persist only probe control-plane evidence, never price outputs."""
    archive = resolve_new_archive_directory(archive_dir)
    results = manifest.get("results")
    if not isinstance(results, list):
        raise ValueError("probe manifest results must be a list")

    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(
        tempfile.mkdtemp(prefix=f".{archive.name}.tmp-", dir=archive.parent)
    )
    try:
        os.chmod(temporary_dir, ARCHIVE_DIRECTORY_MODE)
        write_json(manifest, temporary_dir / "summary.json")
        source_records = [
            archive_result_evidence(result, sequence, temporary_dir)
            for sequence, result in enumerate(results, start=1)
        ]
        write_json(
            build_archive_manifest(temporary_dir, source_records),
            temporary_dir / "archive_manifest.json",
        )
        verify_archive_integrity(temporary_dir)
        temporary_dir.rename(archive)
    except Exception as exc:
        try:
            shutil.rmtree(temporary_dir)
        except OSError as cleanup_exc:
            raise RuntimeError(
                f"{exc}; temporary archive cleanup failed for {temporary_dir}: {cleanup_exc}"
            ) from exc
        raise


def archive_result_evidence(
    result: object,
    sequence: int,
    archive_dir: Path,
) -> dict[str, object]:
    if not isinstance(result, dict):
        raise ValueError("probe manifest result is invalid")
    source = source_name(result.get("source"), "probe manifest result source")
    result_dir = archive_dir / "results" / f"{sequence:03d}-{source}"
    result_dir.mkdir(parents=True, exist_ok=True, mode=ARCHIVE_DIRECTORY_MODE)
    metadata = archive_metadata_copy(result, result_dir, archive_dir)
    stdout = result_dir / "stdout.txt"
    stderr = result_dir / "stderr.txt"
    stdout.write_text(str(result.get("stdout", "")), encoding="utf-8")
    stderr.write_text(str(result.get("stderr", "")), encoding="utf-8")
    return {
        "result_index": sequence - 1,
        "source": source,
        "stdout": relative_archive_path(stdout, archive_dir),
        "stderr": relative_archive_path(stderr, archive_dir),
        "metadata": metadata,
    }


def archive_metadata_copy(
    result: dict[str, object],
    result_dir: Path,
    archive_dir: Path,
) -> str | None:
    metadata_output = Path(str(result.get("metadata_output", "")))
    if metadata_output.is_symlink():
        raise ValueError(f"metadata output must not be a symlink: {metadata_output}")
    if not metadata_output.is_file():
        return None
    metadata = result.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("probe manifest result metadata is invalid")
    destination = result_dir / "metadata.json"
    write_json(metadata, destination)
    return relative_archive_path(destination, archive_dir)


def build_archive_manifest(
    archive_dir: Path,
    source_records: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": ARCHIVE_SCHEMA_VERSION,
        "archive_type": ARCHIVE_TYPE,
        "claim_boundary": ARCHIVE_CLAIM_BOUNDARY,
        "source_records": source_records,
        "files": [
            archive_file_record(path, archive_dir)
            for path in sorted(archive_dir.rglob("*"))
            if path.is_file()
        ],
    }


def archive_file_record(path: Path, archive_dir: Path) -> dict[str, object]:
    if path.is_symlink():
        raise ValueError(f"archive payload must not be a symlink: {path}")
    return {
        "path": relative_archive_path(path, archive_dir),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def relative_archive_path(path: Path, archive_dir: Path) -> str:
    return path.relative_to(archive_dir).as_posix()


def paths_overlap(first: Path, second: Path) -> bool:
    return (
        first == second
        or first.is_relative_to(second)
        or second.is_relative_to(first)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive_integrity(archive_dir: Path) -> dict[str, object]:
    archive = verify_archive_directory(archive_dir)
    manifest = load_archive_manifest(archive)
    expected_paths = verify_payload_records(archive, manifest["files"])
    summary = load_archived_summary(archive, expected_paths)
    verify_source_records(manifest["source_records"], summary["results"], expected_paths)
    verify_archive_payload_tree(archive, expected_paths)
    return manifest


def verify_archive_directory(archive_dir: Path) -> Path:
    if archive_dir.is_symlink() or not archive_dir.is_dir():
        raise ValueError("archive directory is missing or unsafe")
    archive = archive_dir.resolve()
    if os.name == "posix" and stat.S_IMODE(archive.stat().st_mode) != ARCHIVE_DIRECTORY_MODE:
        raise ValueError("archive directory must be owner-only mode 0700")
    return archive


def load_archive_manifest(archive: Path) -> dict[str, object]:
    path = archive / "archive_manifest.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("archive manifest is missing or unsafe")
    manifest = load_json_object(path, "archive manifest root")
    if manifest.get("schema_version") != ARCHIVE_SCHEMA_VERSION:
        raise ValueError("archive manifest schema_version is invalid")
    if manifest.get("archive_type") != ARCHIVE_TYPE:
        raise ValueError("archive manifest archive_type is invalid")
    if manifest.get("claim_boundary") != ARCHIVE_CLAIM_BOUNDARY:
        raise ValueError("archive manifest claim_boundary is invalid")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("archive manifest files must be a non-empty list")
    source_records = manifest.get("source_records")
    if not isinstance(source_records, list):
        raise ValueError("archive manifest source_records must be a list")
    return manifest


def load_archived_summary(archive: Path, expected_paths: set[str]) -> dict[str, object]:
    if "summary.json" not in expected_paths:
        raise ValueError("archive manifest must include summary.json")
    summary = load_json_object(archive / "summary.json", "archived summary")
    if not isinstance(summary.get("results"), list):
        raise ValueError("archived summary results must be a list")
    return summary


def load_json_object(path: Path, label: str) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be an object")
    return data


def verify_payload_records(archive: Path, records: object) -> set[str]:
    if not isinstance(records, list):
        raise ValueError("archive manifest files must be a non-empty list")
    expected_paths: set[str] = set()
    for record in records:
        relative = verify_payload_record(archive, record, expected_paths)
        expected_paths.add(relative)
    return expected_paths


def verify_payload_record(
    archive: Path,
    record: object,
    expected_paths: set[str],
) -> str:
    if not isinstance(record, dict):
        raise ValueError("archive manifest file record is invalid")
    relative = safe_relative_path(record.get("path"), "archive manifest file path")
    if relative in expected_paths:
        raise ValueError("archive manifest contains duplicate payload paths")
    payload = archive / relative
    if not payload.is_file() or payload.is_symlink():
        raise ValueError(f"archive payload is missing or unsafe: {relative}")
    size = record.get("bytes")
    if type(size) is not int or size < 0 or payload.stat().st_size != size:
        raise ValueError(f"archive payload size mismatch: {relative}")
    digest = record.get("sha256")
    if not valid_sha256(digest):
        raise ValueError(f"archive payload hash record is invalid: {relative}")
    if sha256_file(payload) != digest:
        raise ValueError(f"archive payload hash mismatch: {relative}")
    return relative


def verify_source_records(
    source_records: object,
    results: object,
    expected_paths: set[str],
) -> None:
    if not isinstance(source_records, list) or not isinstance(results, list):
        raise ValueError("archive source records do not cover summary results")
    if len(source_records) != len(results):
        raise ValueError("archive source records do not cover summary results")
    for index, source_record in enumerate(source_records):
        verify_source_record(source_record, results, expected_paths, index)


def verify_source_record(
    source_record: object,
    results: list[object],
    expected_paths: set[str],
    expected_index: int,
) -> None:
    if not isinstance(source_record, dict):
        raise ValueError("archive source record is invalid")
    if source_record.get("result_index") != expected_index:
        raise ValueError("archive source result index is invalid")
    result = results[expected_index]
    if not isinstance(result, dict):
        raise ValueError("archived summary result is invalid")
    source = source_name(result.get("source"), "archived summary result source")
    if source_record.get("source") != source:
        raise ValueError("archive source record does not match summary result")
    prefix = f"results/{expected_index + 1:03d}-{source}"
    verify_source_path(source_record.get("stdout"), f"{prefix}/stdout.txt", expected_paths)
    verify_source_path(source_record.get("stderr"), f"{prefix}/stderr.txt", expected_paths)
    metadata = source_record.get("metadata")
    metadata_path = f"{prefix}/metadata.json"
    if metadata_path in expected_paths:
        verify_source_path(metadata, metadata_path, expected_paths)
    elif metadata is not None:
        raise ValueError("archive source metadata mapping is invalid")


def verify_source_path(value: object, expected: str, expected_paths: set[str]) -> None:
    if value != expected or expected not in expected_paths:
        raise ValueError("archive source payload mapping is invalid")


def verify_archive_payload_tree(archive: Path, expected_paths: set[str]) -> None:
    manifest_path = archive / "archive_manifest.json"
    actual_paths: set[str] = set()
    for path in archive.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"archive tree must not contain symlinks: {path}")
        if path.is_file() and path != manifest_path:
            actual_paths.add(relative_archive_path(path, archive))
    if expected_paths != actual_paths:
        raise ValueError("archive payload files do not match archive manifest")


def safe_relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} is invalid")
    relative = Path(value)
    normalized = relative.as_posix()
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or normalized != value
        or normalized == "."
    ):
        raise ValueError("archive manifest contains an unsafe payload path")
    return normalized


def source_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not SOURCE_NAME_RE.fullmatch(value):
        raise ValueError(f"{label} is invalid")
    return value


def valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == hashlib.sha256().digest_size * 2
        and all(character in "0123456789abcdef" for character in value)
    )
