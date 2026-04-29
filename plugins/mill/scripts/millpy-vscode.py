"""
mill-vscode — open VS Code in an active worktree.

Scans the worktrees container directory for subdirectories that carry a
``.millhouse/active.slug.md`` marker, presents a numbered picker (or uses
``--slug`` to skip it), then opens VS Code in the selected worktree.

Usage:
    python mill-vscode.py [--slug <slug>] [--list]

    --slug <slug>   Skip the picker and open the worktree for this slug.
    --list          Print the list of active worktrees without launching.

Exit codes:
    0 — VS Code launched (or listing complete, or no active worktrees)
    1 — any error (not in git repo, slug not found, invalid selection)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import _spawn_core
from _config import load_config as _load_config
from _paths import resolve_git_root, resolve_hub_relative_path, resolve_wiki_path, resolve_worktrees_dir


def _build_code_argv(worktree_path: Path) -> list[str]:
    """Build the argv to open VS Code at ``worktree_path``.

    Probes for ``code.cmd`` and ``code`` on PATH; falls back to the
    canonical Windows install location under ``LOCALAPPDATA``.

    Args:
        worktree_path: Absolute path to the worktree to open.

    Returns:
        A list suitable for passing to ``subprocess.run``.
    """
    code = (
        shutil.which("code.cmd")
        or shutil.which("code")
        or os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs",
            "Microsoft VS Code",
            "bin",
            "code.cmd",
        )
    )
    return [code, str(worktree_path)]


def main(argv: list[str] | None = None) -> int:
    """Open VS Code in an active child worktree selected by the user.

    Resolves the worktrees directory from config, discovers all active
    worktrees via ``_spawn_core.discover_active_worktrees``, then either
    prints the list (``--list``), auto-selects by slug (``--slug``), or
    presents a numbered picker.

    Args:
        argv: Argument vector. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit code: 0 on success, 1 on error or invalid selection.
    """
    parser = argparse.ArgumentParser(
        prog="mill-vscode",
        description="Open VS Code in an active child worktree.",
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="Skip the picker and open the worktree for this slug.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print active worktrees without launching VS Code.",
    )
    args = parser.parse_args(argv)

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
        print("No active worktrees found.")
        return 0

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
    elif len(active) == 1:
        path, slug, title = active[0]
        print(f"Auto-selecting: {slug}", file=sys.stderr)
        selected_path = path
    else:
        print("Active worktrees:", file=sys.stderr)
        for i, (path, slug, title) in enumerate(active, start=1):
            label = f"{slug} — {title}" if title else slug
            print(f"  {i}) {label}", file=sys.stderr)
        try:
            raw = input(f"Select worktree (1-{len(active)}): ").strip()
        except EOFError:
            print("[mill-vscode] No input available.", file=sys.stderr)
            return 1
        try:
            num = int(raw)
            if num < 1 or num > len(active):
                raise ValueError
        except ValueError:
            print(f"[mill-vscode] Invalid selection: {raw!r}", file=sys.stderr)
            return 1
        selected_path = active[num - 1][0]

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

    print(f"Opening VS Code in: {launch_path}", file=sys.stderr)
    code_argv = _build_code_argv(launch_path)
    subprocess.run(code_argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
