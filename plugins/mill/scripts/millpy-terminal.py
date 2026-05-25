"""
mill-terminal — open Claude Code in an active worktree.

Scans the worktrees container directory for subdirectories whose current git
branch matches an active task in Home.md, presents a numbered picker, then
launches Claude Code in the selected worktree via ``subprocess.run``.

Usage:
    python mill-terminal.py

Exit codes:
    0 — Claude process started (or no active worktrees found)
    1 — any error (not in git repo, invalid pick, launcher not found)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import _spawn_core
from wiki import _client as wiki
from _config import load_config as _load_config
from _paths import resolve_git_root, resolve_hub_relative_path, resolve_wiki_path, resolve_worktrees_dir


def _load_spawn_main():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("mill_spawn", Path(__file__).parent / "millpy-spawn.py")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


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
    home_tasks: list = []
    try:
        wiki_path = resolve_wiki_path(git_root)
        cfg = _load_config(git_root, git_root)
        home_tasks = wiki.list_tasks_brief(wiki_path)
    except (SystemExit, Exception):
        cfg = {}

    branch_prefix = cfg.get("spawn", {}).get("branch_prefix", "")
    worktrees_dir = resolve_worktrees_dir(cfg, git_root)
    active = _spawn_core.discover_active_worktrees(worktrees_dir, home_tasks, branch_prefix)

    if not active:
        spawn_main = _load_spawn_main()
        rc = spawn_main([])
        if rc != 0:
            return rc
        active = _spawn_core.discover_active_worktrees(worktrees_dir, home_tasks, branch_prefix)
        if not active:
            print(
                "No tasks available and no active worktrees. Add tasks to Home.md first.",
                file=sys.stderr,
            )
            return 0

    if len(active) == 1:
        path, slug, title = active[0]
        print(f"Auto-selecting: {slug} -- {title}", file=sys.stderr)
        selected_path = path
        selected_slug = slug
    else:
        print("Active worktrees:", file=sys.stderr)
        for i, (path, slug, title) in enumerate(active, start=1):
            label = f"{slug} -- {title}" if title else slug
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
            worktree_cfg = _load_config(selected_path, selected_path)
        except (SystemExit, FileNotFoundError):
            worktree_cfg = {}
    else:
        worktree_cfg = {}
    hub_subpath = worktree_cfg.get("hub_relative_path", ".")
    launch_path = resolve_hub_relative_path(selected_path, hub_subpath)

    print(f"Launching Claude Code in: {launch_path}", file=sys.stderr)
    print(f"Session name: {selected_slug}", file=sys.stderr)
    if os.name == "nt":
        # Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.
        subprocess.run(["cmd", "/c", "claude", "--name", selected_slug], cwd=launch_path)
    else:
        # Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.
        subprocess.run(["claude", "--name", selected_slug], cwd=launch_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
