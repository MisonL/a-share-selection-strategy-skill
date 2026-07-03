"""Shared filesystem paths for the A-share selection skill."""

from __future__ import annotations

from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPTS_DIR.parent
CONFIGS_DIR = SKILL_ROOT / "configs"
CONFIG_FILE_NAMES = {
    "example_config.json",
    "prediction_profile_config.json",
    "ultra_short_low_price_config.json",
    "hong_kong_generic_config.json",
}


def config_path(name: str) -> Path:
    return CONFIGS_DIR / name


def resolve_config_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.parent.name == "scripts" and path.name in CONFIG_FILE_NAMES:
        return CONFIGS_DIR / path.name
    return path


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
