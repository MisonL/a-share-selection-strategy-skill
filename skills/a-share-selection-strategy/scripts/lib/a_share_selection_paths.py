"""Shared filesystem paths for the A-share selection skill."""

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


from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
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
    """Resolve the historical scripts/*.json CLI alias to the canonical config."""

    if path.exists():
        return path
    if path.parent.resolve() == SCRIPTS_DIR and path.name in CONFIG_FILE_NAMES:
        return CONFIGS_DIR / path.name
    return path
