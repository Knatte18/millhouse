"""
mill-terminal — open Claude Code in an active worktree.

Scans the worktrees container directory for subdirectories that carry a
``.millhouse/active.slug.md`` marker, presents a numbered picker, then
launches Claude Code in the selected worktree via ``subprocess.run``.

Usage:
    python mill-terminal.py

Exit codes:
    0 — Claude process started (or no active worktrees found)
    1 — any error (not in git repo, invalid pick, launcher not found)
"""
from __future__ import annotations

import shutil
import subprocess
import sys

import _spawn_core
from _config import load_config as _load_config
from _paths import resolve_git_root, resolve_hub_relative_path, resolve_wiki_path, resolve_worktrees_dir


def main(argv: list[str] | None = None) -> int:
    """Launch Claude Code in an active child worktree selected by the user.

    Resolves the worktrees directory from config, discovers all active
    worktrees via ``_spawn_core.discover_active_worktrees``, presents a
    numbered picker (or auto-selects when only one is found), then spawns
    Claude with ``--name <slug>`` in the chosen worktree path.

    Args:
        argv: Argument vector (unused — no CLI flags for this entrypoint).

    Returns:
        Exit code: 0 on success, 1 on error or invalid selection.
    """
    git_root = resolve_git_root()

    wiki_path = None
    try:
        wiki_path = resolve_wiki_path(git_root)
        cfg = _load_config(wiki_path, git_root)
    except SystemExit:
        cfg = {}

    worktrees_dir = resolve_worktrees_dir(cfg, git_root)
    active = _spawn_core.discover_active_worktrees(worktrees_dir)

    if not active:
        print("No active worktrees found.", file=sys.stderr)
        return 0

    if len(active) == 1:
        path, slug, title = active[0]
        print(f"Auto-selecting: {slug} — {title}", file=sys.stderr)
        selected_path = path
        selected_slug = slug
    else:
        print("Active worktrees:", file=sys.stderr)
        for i, (path, slug, title) in enumerate(active, start=1):
            label = f"{slug} — {title}" if title else slug
            print(f"  {i}) {label}", file=sys.stderr)
        try:
            raw = input(f"Select worktree (1-{len(active)}): ").strip()
        except EOFError:
            print("[mill-terminal] No input available.", file=sys.stderr)
            return 1
        try:
            num = int(raw)
            if num < 1 or num > len(active):
                raise ValueError
        except ValueError:
            print(f"[mill-terminal] Invalid selection: {raw!r}", file=sys.stderr)
            return 1
        selected_path, selected_slug, _ = active[num - 1]

    # Load per-worktree config to honour hub_relative_path.
    if wiki_path is not None:
        try:
            worktree_cfg = _load_config(wiki_path, selected_path)
        except SystemExit:
            worktree_cfg = {}
    else:
        worktree_cfg = {}
    hub_subpath = worktree_cfg.get("hub_relative_path", ".")
    launch_path = resolve_hub_relative_path(selected_path, hub_subpath)

    claude = shutil.which("claude") or "claude"
    print(f"Launching Claude Code in: {launch_path}", file=sys.stderr)
    print(f"Session name: {selected_slug}", file=sys.stderr)
    subprocess.run(
        [claude, "--name", selected_slug],
        cwd=launch_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
