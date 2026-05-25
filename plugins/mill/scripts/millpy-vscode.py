"""
mill-vscode — open VS Code in an active worktree.

Scans the worktrees container directory for subdirectories whose current git
branch matches an active task in Home.md, filters out worktrees that already
have a VS Code window open, then shows a unified prompt: ``<Enter>`` spawns
a new task and opens it, a number opens the listed worktree, or ``q`` quits.

Usage:
    python millpy-vscode.py [--new | --slug <slug>] [--list] [--filter-open]

    --new           Spawn a new task and open it without showing the picker.
    --slug <slug>   Skip the picker and open the worktree for this slug.
    --list          Print the list of active worktrees without launching.
    --filter-open   Filter out worktrees that already have a VS Code window open.
    --new and --slug are mutually exclusive.

Exit codes:
    0 — VS Code launched (or listing complete, or no active worktrees)
    1 — any error (not in git repo, slug not found, invalid selection)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import _spawn_core
import _vscode_processes
from wiki import _client as wiki
from _config import load_config as _load_config
from _paths import resolve_git_root, resolve_hub_relative_path, resolve_wiki_path, resolve_worktrees_dir


def _build_code_argv(worktree_path: Path) -> list[str]:
    """Build the argv to open VS Code at ``worktree_path``.

    On Windows, delegates resolution to cmd.exe so that ``code.cmd`` is
    found via the full interactive PATH (including WindowsApps), which is
    not inherited by Python subprocesses launched from debugpy or non-
    interactive shells (see discussion.md § debugpy-path).

    On POSIX, ``code`` is on PATH and subprocess inherits it normally.

    Args:
        worktree_path: Absolute path to the worktree to open.

    Returns:
        A list suitable for passing to ``subprocess.run``.
    """
    if os.name == "nt":
        return ["cmd", "/c", "code", str(worktree_path)]
    return ["code", str(worktree_path)]


def _load_spawn_main():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("mill_spawn", Path(__file__).parent / "millpy-spawn.py")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def _filter_open_worktrees(
    active: list[tuple[Path, str, str]],
    wiki_path: Path | None,
    hub_subpath_default: str,
) -> list[tuple[Path, str, str]]:
    open_cmdlines = _vscode_processes.find_open_vscode_paths()
    if not open_cmdlines:
        return active
    result = []
    for entry_path, slug, title in active:
        hub_subpath = hub_subpath_default
        if wiki_path is not None:
            try:
                entry_cfg = _load_config(entry_path, entry_path)
                hub_subpath = entry_cfg.get("hub_relative_path", hub_subpath_default)
            except SystemExit:
                hub_subpath = hub_subpath_default
        launch = resolve_hub_relative_path(entry_path, hub_subpath)
        if not any(
            _vscode_processes.signature_matches(launch, slug, str(cmdline))
            for cmdline in open_cmdlines
        ):
            result.append((entry_path, slug, title))
    return result


def _spawn_and_open(
    worktrees_dir: Path,
    pre_active: list[tuple[Path, str, str]],
    wiki_path: Path | None,
    home_tasks: list,
    branch_prefix: str,
) -> int:
    pre_paths = {entry[0] for entry in pre_active}
    spawn_main = _load_spawn_main()
    rc = spawn_main([])
    if rc != 0:
        return rc
    post = _spawn_core.discover_active_worktrees(worktrees_dir, home_tasks, branch_prefix)
    new_entries = [e for e in post if e[0] not in pre_paths]
    if len(new_entries) == 0:
        print("[mill-vscode] spawn produced no new worktree; nothing to open.", file=sys.stderr)
        return 0
    if len(new_entries) > 1:
        print(
            f"[mill-vscode] spawn produced {len(new_entries)} new worktrees; refusing to guess.",
            file=sys.stderr,
        )
        return 1
    new_path, new_slug, _ = new_entries[0]
    if wiki_path is not None:
        try:
            worktree_cfg = _load_config(new_path, new_path)
        except SystemExit:
            worktree_cfg = {}
    else:
        worktree_cfg = {}
    hub_subpath = worktree_cfg.get("hub_relative_path", ".")
    launch_path = resolve_hub_relative_path(new_path, hub_subpath)
    print(f"Opening VS Code in: {launch_path}", file=sys.stderr)
    subprocess.run(_build_code_argv(launch_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Open VS Code in an active child worktree selected by the user.

    Resolves the worktrees directory from config, discovers all active
    worktrees via ``_spawn_core.discover_active_worktrees``, filters out
    worktrees that already have a VS Code window open, then presents a
    unified prompt.

    Args:
        argv: Argument vector. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit code: 0 on success, 1 on error or invalid selection.
    """
    parser = argparse.ArgumentParser(
        prog="mill-vscode",
        description="Open VS Code in an active child worktree.",
    )
    mutex = parser.add_mutually_exclusive_group()
    mutex.add_argument(
        "--new",
        action="store_true",
        help="Spawn a new task and open it without showing the picker.",
    )
    mutex.add_argument(
        "--slug",
        default=None,
        help="Skip the picker and open the worktree for this slug.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print active worktrees without launching VS Code.",
    )
    parser.add_argument(
        "--filter-open",
        action="store_true",
        help="Filter out worktrees that already have a VS Code window open.",
    )
    args = parser.parse_args(argv)

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

    if not active and args.list:
        print("No active worktrees found.", file=sys.stderr)
        return 0

    if not active and args.slug is not None:
        print("No active worktrees found.", file=sys.stderr)
        return 0

    if args.new:
        return _spawn_and_open(worktrees_dir, active, wiki_path, home_tasks, branch_prefix)

    if not active:
        return _spawn_and_open(worktrees_dir, active, wiki_path, home_tasks, branch_prefix)

    if args.list:
        for i, (path, slug, title) in enumerate(active, start=1):
            label = f"{slug} — {title}" if title else slug
            print(f"  {i}) {label}  [{path}]")
        return 0

    if args.slug is not None:
        matched = next((entry for entry in active if entry[1] == args.slug), None)
        if matched is None:
            print(
                f"[mill-vscode] slug {args.slug!r} not found in active worktrees.",
                file=sys.stderr,
            )
            return 1
        selected_path = matched[0]
    else:
        if args.filter_open:
            filtered = _filter_open_worktrees(active, wiki_path, cfg.get("hub_relative_path", "."))
            if not filtered:
                return _spawn_and_open(worktrees_dir, active, wiki_path, home_tasks, branch_prefix)
        else:
            filtered = active

        print("Active worktrees:", file=sys.stderr)
        for i, (path, slug, title) in enumerate(filtered, start=1):
            label = f"{slug} — {title}" if title else slug
            print(f"  {i}) {label}", file=sys.stderr)

        selected_path = None
        for _ in range(3):
            try:
                raw = input(
                    f"<Enter> to spawn new task, 1-{len(filtered)} to open, q to quit: "
                ).strip()
            except EOFError:
                print("[mill-vscode] No input available.", file=sys.stderr)
                return 1
            if raw == "":
                return _spawn_and_open(worktrees_dir, active, wiki_path, home_tasks, branch_prefix)
            if raw.lower() == "q":
                return 0
            try:
                num = int(raw)
                if 1 <= num <= len(filtered):
                    selected_path = filtered[num - 1][0]
                    break
            except ValueError:
                pass
            print(f"[mill-vscode] Invalid selection: {raw!r}", file=sys.stderr)

        if selected_path is None:
            return 1

    # Load per-worktree config to honour hub_relative_path.
    if wiki_path is not None:
        try:
            worktree_cfg = _load_config(selected_path, selected_path)
        except SystemExit:
            worktree_cfg = {}
    else:
        worktree_cfg = {}
    hub_subpath = worktree_cfg.get("hub_relative_path", ".")
    launch_path = resolve_hub_relative_path(selected_path, hub_subpath)

    print(f"Opening VS Code in: {launch_path}", file=sys.stderr)
    code_argv = _build_code_argv(launch_path)
    # Interactive launcher — must keep its console; do NOT route through _subprocess_util.run.
    subprocess.run(code_argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
