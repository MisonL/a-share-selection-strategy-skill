"""Compatibility wrapper for configuration loading helpers."""

from __future__ import annotations

from lib.a_share_selection_config import *  # noqa: F401,F403


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
