"""
mill-session-tasks — re-render the current worktree's VS Code session tasks.

Rewrites ``.vscode/tasks.json`` under the hub path from the current merged config.
Session names are ``<short_name>:<slug>:<phase>`` on a task worktree and ``<short_name>:<phase>`` on the hub,
lower-cased; the hub also gets the ``mill: orch`` task.
The fallback short name comes from the main worktree's directory name, with a warning on stderr.
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
from _paths import (
    resolve_git_root,
    resolve_hub_path,
    resolve_main_worktree_root,
    resolve_short_name,
    resolve_wiki_path,
    short_name_is_derived,
)


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
        short = resolve_short_name(cfg, resolve_main_worktree_root(git_root).name)
        try:
            slug = _marker.slug_from_branch(git_root, wiki_path, cfg)
            name = _vscode_tasks.session_prefix(short, slug)
            hub_render = False
        except _marker.MarkerError:
            name = _vscode_tasks.session_prefix(short)
            hub_render = True
        if short_name_is_derived(cfg):
            print(
                f"[mill-session-tasks] WARNING: repo.short_name is not set; using derived short name '{short}'. "
                "Set repo.short_name in mill-config.yaml or run /mill-setup.",
                file=sys.stderr,
            )
        status = _vscode_tasks.write_tasks(
            target, name, (cfg.get("spawn") or {}).get("sessions"), hub=hub_render
        )
    except (Exception, SystemExit) as exc:
        message = " ".join(str(exc).split()).encode("ascii", "replace").decode("ascii")
        print(f"[mill-session-tasks] failed: {message}", file=sys.stderr)
        return 1
    print(f"tasks: {status} {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
