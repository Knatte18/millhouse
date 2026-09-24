"""
mill-session-tasks — re-render the current worktree's VS Code session tasks.

Rewrites ``.vscode/tasks.json`` under the hub path from the current merged config.
The session name is the task slug on a task worktree and the repo short name on the hub.
Model and effort come from ``spawn.sessions``; they are baked into the file, so re-run this
after changing those values.

Usage:
    python millpy-session-tasks.py

Exit codes:
    0 — tasks.json written or already up to date
    1 — any error (nothing is written)
"""
from __future__ import annotations

import argparse
import sys

import _marker
import _vscode_tasks
from _config import load_config as _load_config
from _paths import resolve_git_root, resolve_hub_path, resolve_short_name, resolve_wiki_path


def main(argv: list[str] | None = None) -> int:
    """
    Render ``<hub>/.vscode/tasks.json`` for the current worktree.

    A worktree whose branch yields no task slug (``_marker.MarkerError``) is treated as the hub.
    Every other failure, including ``SystemExit`` from config or path resolution, returns 1 and
    writes nothing.

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = argparse.ArgumentParser(
        prog="mill-session-tasks",
        description="Re-render this worktree's .vscode/tasks.json from the current mill config.",
    )
    parser.parse_args(argv)

    try:
        git_root = resolve_git_root()
        hub = resolve_hub_path()
        wiki_path = resolve_wiki_path(git_root)
        cfg = _load_config(hub_root=hub, worktree_root=git_root)
        target = hub / ".vscode" / "tasks.json"
        if not target.parent.exists():
            print(
                f"[mill-session-tasks] {target.parent} does not exist; nothing written",
                file=sys.stderr,
            )
            return 1
        try:
            name = _marker.slug_from_branch(git_root, wiki_path, cfg)
        except _marker.MarkerError:
            name = resolve_short_name(cfg, git_root.name)
        status = _vscode_tasks.write_tasks(target, name, (cfg.get("spawn") or {}).get("sessions"))
    except (Exception, SystemExit) as exc:
        message = " ".join(str(exc).split()).encode("ascii", "replace").decode("ascii")
        print(f"[mill-session-tasks] failed: {message}", file=sys.stderr)
        return 1
    print(f"tasks: {status} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
