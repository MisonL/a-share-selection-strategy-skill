"""Compatibility wrapper for the internal CLI guard helper."""

from __future__ import annotations

from lib.a_share_selection_cli_guard import *  # noqa: F401,F403


if __name__ == "__main__":
    fail_not_cli(__file__)
