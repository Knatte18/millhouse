"""
Flag-file API for ephemeral autonomous-mode state.

Replaces the removed ``pipeline.autonomous_mode`` config key. The flag file
``<hub>/.millhouse/autonomous.flag`` represents whether the current task is
in autonomous escalation mode.

Public API:
    is_autonomous(hub_dir) -> bool
    set_autonomous(hub_dir) -> None
    clear_autonomous(hub_dir) -> None
"""
from __future__ import annotations

from pathlib import Path


__all__ = ["is_autonomous", "set_autonomous", "clear_autonomous"]


def is_autonomous(hub_dir: Path) -> bool:
    """Return whether the hub is in autonomous mode.

    Args:
        hub_dir: Absolute path to the hub directory.

    Returns:
        True if the flag file exists, False otherwise.
    """
    flag_path = hub_dir / ".millhouse" / "autonomous.flag"
    return flag_path.exists()


def set_autonomous(hub_dir: Path) -> None:
    """Set the autonomous flag (idempotent).

    Args:
        hub_dir: Absolute path to the hub directory.
    """
    flag_path = hub_dir / ".millhouse" / "autonomous.flag"
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    flag_path.touch(exist_ok=True)


def clear_autonomous(hub_dir: Path) -> None:
    """Clear the autonomous flag (idempotent).

    Args:
        hub_dir: Absolute path to the hub directory.
    """
    flag_path = hub_dir / ".millhouse" / "autonomous.flag"
    flag_path.unlink(missing_ok=True)
