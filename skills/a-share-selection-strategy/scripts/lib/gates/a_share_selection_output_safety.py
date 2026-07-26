"""Filesystem guards for public CLI outputs that must fail closed."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Iterable


def validate_output_paths(
    outputs: Iterable[Path],
    inputs: Iterable[Path],
    *,
    protected_directories: Iterable[Path] = (),
) -> tuple[Path, ...]:
    output_paths = tuple(outputs)
    input_paths = tuple(inputs)
    protected_directory_paths = tuple(protected_directories)
    if not output_paths:
        raise ValueError("at least one output path is required")
    reject_unexpanded_home_shorthand(
        (*output_paths, *input_paths, *protected_directory_paths)
    )
    validate_distinct_outputs(output_paths)
    validate_output_input_paths(output_paths, input_paths)
    validate_protected_directories(output_paths, protected_directory_paths)
    return output_paths


def validate_distinct_outputs(output_paths: tuple[Path, ...]) -> None:
    for index, output in enumerate(output_paths):
        if output.expanduser().is_dir():
            raise ValueError("output path must be a file, not a directory")
        for previous_output in output_paths[:index]:
            if output_paths_collide(output, previous_output):
                raise ValueError("output paths must be distinct")


def validate_output_input_paths(
    output_paths: tuple[Path, ...],
    input_paths: tuple[Path, ...],
) -> None:
    for output in output_paths:
        declared_output = absolute_path(output)
        resolved_output = resolved_path(output)
        for input_path in input_paths:
            declared_input = absolute_path(input_path)
            resolved_input = resolved_path(input_path)
            if paths_equal_ignoring_case(declared_output, declared_input):
                raise ValueError("output path must differ from input paths")
            if paths_equal_ignoring_case(resolved_output, resolved_input):
                raise ValueError("output path must differ from input paths")
            if same_existing_file(output, input_path):
                raise ValueError("output path must differ from input paths")
            if input_path.expanduser().is_dir() and (
                path_is_within(declared_output, declared_input)
                or path_is_within(resolved_output, resolved_input)
                or path_is_within_ignoring_case(declared_output, declared_input)
                or path_is_within_ignoring_case(resolved_output, resolved_input)
                or (
                    output.expanduser().exists()
                    and resolved_input.is_dir()
                    and file_alias_in_directory(output, resolved_input)
                )
            ):
                raise ValueError("output path must differ from input paths")


def validate_protected_directories(
    output_paths: tuple[Path, ...],
    protected_directories: tuple[Path, ...],
) -> None:
    for directory in protected_directories:
        declared_directory, resolved_directory = validate_protected_directory(directory)
        for output in output_paths:
            declared_output = absolute_path(output)
            resolved_output = resolved_path(output)
            if paths_overlap(declared_output, declared_directory) or paths_overlap(
                resolved_output,
                resolved_directory,
            ):
                raise ValueError("output path must not overlap protected directories")
            expanded_output = output.expanduser()
            if (
                expanded_output.exists()
                and resolved_directory.is_dir()
                and file_alias_in_directory(expanded_output, resolved_directory)
            ):
                raise ValueError("output path must not overlap protected directories")


def paths_overlap(left: Path, right: Path) -> bool:
    return (
        path_is_within(left, right)
        or path_is_within(right, left)
        or path_is_within_ignoring_case(left, right)
        or path_is_within_ignoring_case(right, left)
    )


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def path_is_within_ignoring_case(path: Path, parent: Path) -> bool:
    path_parts = casefold_path_parts(path)
    parent_parts = casefold_path_parts(parent)
    return len(path_parts) >= len(parent_parts) and (
        path_parts[: len(parent_parts)] == parent_parts
    )


def paths_equal_ignoring_case(left: Path, right: Path) -> bool:
    return casefold_path_parts(left) == casefold_path_parts(right)


def casefold_path_parts(path: Path) -> tuple[str, ...]:
    normalized = Path(os.path.normpath(str(path)))
    return tuple(part.casefold() for part in normalized.parts)


def absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def resolved_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def output_paths_collide(left: Path, right: Path) -> bool:
    return (
        paths_equal_ignoring_case(absolute_path(left), absolute_path(right))
        or paths_equal_ignoring_case(resolved_path(left), resolved_path(right))
        or same_existing_file(left, right)
    )


def same_existing_file(left: Path, right: Path) -> bool:
    expanded_left = left.expanduser()
    expanded_right = right.expanduser()
    return (
        expanded_left.exists()
        and expanded_right.exists()
        and os.path.samefile(expanded_left, expanded_right)
    )


def file_alias_in_directory(output: Path, directory: Path) -> bool:
    for root, _directories, filenames in os.walk(
        directory,
        followlinks=False,
        onerror=raise_walk_error,
    ):
        for filename in filenames:
            if same_existing_file(output, Path(root) / filename):
                return True
    return False


def reject_protected_directory_symlinks(directory: Path) -> None:
    reject_protected_directory_parent_symlinks(directory)
    if not directory.exists():
        return
    if not directory.is_dir():
        raise ValueError("protected path must be a directory")
    for root, directories, filenames in os.walk(
        directory,
        followlinks=False,
        onerror=raise_walk_error,
    ):
        if any((Path(root) / name).is_symlink() for name in (*directories, *filenames)):
            raise ValueError("protected directory must not contain symlinks")


def reject_unexpanded_home_shorthand(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.parts and path.parts[0].startswith("~"):
            raise ValueError("path must not use unexpanded home shorthand")


def validate_protected_directory(directory: Path) -> tuple[Path, Path]:
    reject_unexpanded_home_shorthand((directory,))
    declared_directory = absolute_path(directory)
    reject_protected_directory_symlinks(declared_directory)
    return declared_directory, resolved_path(directory)


def reject_protected_directory_parent_symlinks(directory: Path) -> None:
    trusted_root = protected_directory_trusted_root(directory)
    current = directory
    while True:
        if trusted_root is not None and paths_equal_ignoring_case(
            current, trusted_root
        ):
            return
        if current.is_symlink():
            raise ValueError("protected directory must not contain symlinks")
        if current == current.parent:
            return
        current = current.parent


def protected_directory_trusted_root(directory: Path) -> Path | None:
    roots = protected_directory_trusted_roots()
    matching_roots = [
        root for root in roots if path_is_within_ignoring_case(directory, root)
    ]
    if not matching_roots:
        return None
    return max(matching_roots, key=lambda root: len(root.parts))


def protected_directory_trusted_roots() -> tuple[Path, ...]:
    raw_roots = (
        Path.cwd().resolve(strict=False),
        Path.home().resolve(strict=False),
        Path(tempfile.gettempdir()).resolve(strict=False),
        Path("/tmp"),
        Path("/var"),
    )
    roots: list[Path] = []
    for root in raw_roots:
        for candidate in (absolute_path(root), resolved_path(root)):
            if candidate not in roots:
                roots.append(candidate)
    return tuple(roots)


def raise_walk_error(error: OSError) -> None:
    raise error


def prepare_output_paths(
    outputs: Iterable[Path],
    inputs: Iterable[Path],
    *,
    protected_directories: Iterable[Path] = (),
) -> tuple[Path, ...]:
    output_paths = validate_output_paths(
        outputs,
        inputs,
        protected_directories=protected_directories,
    )
    remove_output_files(output_paths)
    return output_paths


def remove_output_files(paths: Iterable[Path]) -> None:
    for path in paths:
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_file() or path.is_symlink():
            path.unlink()
