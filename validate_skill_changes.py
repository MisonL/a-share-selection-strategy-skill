#!/usr/bin/env python3
"""Run local validation gates for the A-share selection skill.

This script only validates local repository contracts. It does not run real
market data, real prediction, broker, or live backtest gates.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
SKILL_ROOT = ROOT / "skills" / "a-share-selection-strategy"
SCRIPTS = SKILL_ROOT / "scripts"
DEFAULT_QUICK_VALIDATE = (
    Path.home()
    / ".codex"
    / "skills"
    / ".system"
    / "skill-creator"
    / "scripts"
    / "quick_validate.py"
)
# Keep the historical leaked-key probe split so this file does not match itself.
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}" + "|" + "96" + "e6cc2e")


@dataclass(frozen=True)
class Check:
    name: str
    run: Callable[[], None]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checks = build_checks(args)
    if args.list:
        print("Local validation gates:")
        for check in checks:
            print(f"- {check.name}")
        print(
            "External gates not run: real market data, real prediction, broker orders, live backtests"
        )
        return 0

    for index, check in enumerate(checks, start=1):
        print(f"[{index}/{len(checks)}] {check.name}")
        check.run()
    print("OK: local validation gates passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run local repository validation gates. This does not prove real "
            "market data, prediction quality, broker execution, or live backtest gates."
        )
    )
    parser.add_argument(
        "--quick-validate",
        type=Path,
        default=None,
        help=(
            "Path to skill-creator quick_validate.py; defaults to QUICK_VALIDATE "
            "or ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py."
        ),
    )
    parser.add_argument(
        "--skip-skill-validate",
        action="store_true",
        help="Explicitly skip skill quick_validate when that local tool is unavailable.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip the full unittest suite; intended only for fast local iteration.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List planned local gates without executing them.",
    )
    return parser


def build_checks(args: argparse.Namespace) -> list[Check]:
    checks = [
        Check("JSON configs and evals parse", check_json_files),
        Check("YAML agent manifest parse", check_yaml_agent_manifest),
        Check("scripts compileall", check_compileall),
    ]
    if not args.skip_skill_validate:
        checks.append(Check("skill quick_validate", lambda: check_skill_validate(args)))
    checks.extend(
        [
            Check("git diff --check", check_git_diff),
            Check("text whitespace and conflict marker scan", check_text_hygiene),
            Check("secret scan", check_secret_scan),
            Check("__pycache__ scan", check_pycache_absent),
        ]
    )
    if not args.skip_tests:
        checks.append(Check("full unittest suite", check_unittest))
    return checks


def check_json_files() -> None:
    paths = sorted((SKILL_ROOT / "evals").glob("*.json"))
    paths.extend(sorted((SKILL_ROOT / "configs").glob("*.json")))
    if not paths:
        raise RuntimeError("no JSON config or eval files found")
    for path in paths:
        json.loads(path.read_text(encoding="utf-8"))


def check_yaml_agent_manifest() -> None:
    manifests = sorted((SKILL_ROOT / "agents").glob("*.yaml"))
    if not manifests:
        raise RuntimeError("no YAML agent manifest files found")
    code = (
        "import yaml\n"
        "from pathlib import Path\n"
        f"manifests = {[str(path) for path in manifests]!r}\n"
        "for manifest in manifests:\n"
        "    data = yaml.safe_load(Path(manifest).read_text(encoding='utf-8'))\n"
        "    if not isinstance(data, dict):\n"
        "        raise RuntimeError(f'{manifest}: expected mapping root')\n"
        "    interface = data.get('interface')\n"
        "    if not isinstance(interface, dict):\n"
        "        raise RuntimeError(f'{manifest}: missing interface mapping')\n"
        "    for key in ['display_name', 'short_description', 'default_prompt']:\n"
        "        value = interface.get(key)\n"
        "        if not isinstance(value, str) or not value.strip():\n"
        "            raise RuntimeError(f'{manifest}: missing interface.{key}')\n"
    )
    if python_module_available("yaml"):
        run_command([sys.executable, "-c", code])
        return
    run_command([uv_command(), "run", "--with", "pyyaml", "python", "-c", code])


def check_compileall() -> None:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = "/tmp/a-share-selection-pycache"
    run_command(
        [sys.executable, "-m", "compileall", "-q", str(SCRIPTS)],
        env=env,
    )


def check_skill_validate(args: argparse.Namespace) -> None:
    quick_validate = quick_validate_path(args.quick_validate)
    run_command(
        [
            uv_command(),
            "run",
            "--with",
            "pyyaml",
            "python",
            str(quick_validate),
            str(SKILL_ROOT),
        ]
    )


def quick_validate_path(explicit_path: Path | None) -> Path:
    candidates = []
    if explicit_path is not None:
        candidates.append(explicit_path)
    env_path = os.environ.get("QUICK_VALIDATE")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(DEFAULT_QUICK_VALIDATE)
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "skill quick_validate.py not found; set QUICK_VALIDATE, pass --quick-validate, "
        "or explicitly use --skip-skill-validate"
    )


def check_git_diff() -> None:
    run_command(["git", "diff", "--check"])
    run_command(["git", "diff", "--cached", "--check"])


def check_text_hygiene() -> None:
    hits = []
    for path in text_hygiene_paths():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.rstrip(" \t") != line:
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: trailing whitespace")
            if conflict_marker(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}: conflict marker")
    if hits:
        raise RuntimeError("text hygiene issues found:\n" + "\n".join(hits))


def text_hygiene_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in [ROOT / ".github", SKILL_ROOT, ROOT / "tests"]:
        if directory.is_dir():
            paths.extend(path for path in directory.rglob("*") if path.is_file())
    for name in ["AGENTS.md", "README.md", "validate_skill_changes.py"]:
        path = ROOT / name
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def conflict_marker(line: str) -> bool:
    return (
        line.startswith("<<<<<<< ") or line == "=======" or line.startswith(">>>>>>> ")
    )


def check_secret_scan() -> None:
    hits = []
    for path in secret_scan_paths():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SECRET_RE.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{lineno}")
    if hits:
        raise RuntimeError("secret-like patterns found:\n" + "\n".join(hits))


def secret_scan_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in [ROOT / ".github", SKILL_ROOT, ROOT / "tests"]:
        if directory.is_dir():
            paths.extend(path for path in directory.rglob("*") if path.is_file())
    for name in ["AGENTS.md", "README.md", "validate_skill_changes.py"]:
        path = ROOT / name
        if path.is_file():
            paths.append(path)
    return sorted(set(paths))


def check_pycache_absent() -> None:
    pycache_dirs = [
        str(path.relative_to(ROOT))
        for path in managed_pycache_dirs()
    ]
    if pycache_dirs:
        raise RuntimeError("__pycache__ directories found:\n" + "\n".join(pycache_dirs))


def managed_pycache_dirs() -> list[Path]:
    paths = []
    root_pycache = ROOT / "__pycache__"
    if root_pycache.is_dir():
        paths.append(root_pycache)
    for root in [ROOT / "skills", ROOT / "tests"]:
        if root.is_dir():
            paths.extend(path for path in root.rglob("__pycache__") if path.is_dir())
    return sorted(set(paths))


def check_unittest() -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    run_command(
        [
            uv_command(),
            "run",
            "--with",
            "pandas",
            "--with",
            "numpy",
            "--with",
            "pyarrow",
            "python",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ],
        env=env,
    )


def uv_command() -> str:
    found = shutil.which("uv")
    if found:
        return found
    for candidate in [
        Path("/usr/local/bin/uv"),
        Path("/opt/homebrew/bin/uv"),
        Path.home() / ".local/bin/uv",
    ]:
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(
        "uv executable not found; install uv or add it to PATH before running validation"
    )


def python_module_available(module: str) -> bool:
    return (
        subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def run_command(command: list[str], env: dict[str, str] | None = None) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
