"""Static asset compatibility exports for the local A-share HTML report."""

from __future__ import annotations

from a_share_selection_html_scripts import JS
from a_share_selection_html_styles import CSS


if __name__ == "__main__":
    from a_share_selection_cli_guard import fail_not_cli

    fail_not_cli(__file__)
