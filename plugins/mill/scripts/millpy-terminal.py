"""
mill-terminal — open Claude Code in an active worktree.

Scans the worktrees container directory for subdirectories whose current git branch matches an
active task in Home.md, presents a numbered picker, then launches Claude Code in the selected
worktree via ``subprocess.run``.

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
import _subprocess_util
import _vscode_tasks
from wiki import _client as wiki
from _config import load_config as _load_config
from _paths import (
    resolve_git_root,
    resolve_hub_path,
    resolve_hub_relative_path,
    resolve_main_worktree_root,
    resolve_short_name,
    resolve_wiki_path,
    resolve_worktrees_dir,
    short_name_is_derived,
)


def _load_spawn_main():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("mill_spawn", Path(__file__).parent / "millpy-spawn.py")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def main(argv: list[str] | None = None) -> int:
    """Launch Claude Code in an active child worktree selected by the user.

    Resolves the worktrees directory from config, discovers all active worktrees via
    ``_spawn_core.discover_active_worktrees``, presents a numbered picker (or auto-selects when only
    one is found), then spawns Claude with ``--name <short>:<slug>`` (lower-cased) in the chosen worktree path.

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
        cfg = _load_config(resolve_hub_path(), resolve_hub_path())
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

    try:
        repo_name = resolve_main_worktree_root(git_root).name
    except (SystemExit, Exception):
        repo_name = git_root.name
    short = resolve_short_name(cfg, repo_name)
    try:
        session_name = _vscode_tasks.session_prefix(short, selected_slug)
    except ValueError as exc:
        message = " ".join(str(exc).split()).encode("ascii", "replace").decode("ascii")
        print(f"[mill-terminal] invalid session name: {message}", file=sys.stderr)
        return 1
    if short_name_is_derived(cfg):
        print(
            f"[mill-terminal] WARNING: repo.short_name is not set; using derived short name '{short}'. "
            "Set repo.short_name in mill-config.yaml or run /mill-setup.",
            file=sys.stderr,
        )

    # Load per-worktree stub config to honour hub_relative_path.
    hub_subpath = "."
    stub_path = selected_path / ".millhouse" / "config.local.yaml"
    if stub_path.exists():
        try:
            import yaml
            stub_cfg = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
            hub_subpath = stub_cfg.get("hub_relative_path", ".")
        except Exception:
            pass
    launch_path = resolve_hub_relative_path(selected_path, hub_subpath)

    print(f"Launching Claude Code in: {launch_path}", file=sys.stderr)
    print(f"Session name: {session_name}", file=sys.stderr)
    if os.name == "nt":
        # Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.
        subprocess.run(
            ["cmd", "/c", "claude", "--name", session_name], cwd=launch_path, env=_subprocess_util.scrub_env()
        )
    else:
        # Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.
        subprocess.run(["claude", "--name", session_name], cwd=launch_path, env=_subprocess_util.scrub_env())
    return 0


if __name__ == "__main__":
    sys.exit(main())
