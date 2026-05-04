"""
mill-worktree — generic worktree management (no wiki claim).

Usage:
    python mill-worktree.py create --branch <name> [--dir-name <name>]
                                   [--color <name>] [--dry-run]
    python mill-worktree.py remove <worktree_path>
    python mill-worktree.py list

Exit codes:
    0 — success
    1 — any error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

import _active
import _junction
import _subprocess_util
import _vscode
import _wiki
import _worktree
from _config import load_config as _load_config
from _paths import (
    resolve_container_path,
    resolve_git_root,
    resolve_hub_path,
    resolve_hub_relative_path,
    resolve_main_worktree_root,
    resolve_short_name,
    resolve_wiki_path,
    resolve_worktrees_dir,
)
from _spawn_core import WORKTREE_COLOR_NAME_TO_HEX, pick_worktree_color


def _cmd_create(args: argparse.Namespace, git_root: Path, cfg: dict) -> int:
    """Implement the ``create`` subcommand.

    Creates a new worktree on ``args.branch``, optionally using
    ``args.dir_name`` as the directory name. Does NOT write ``active.slug.md``
    or ``status.md``; this worktree is not claimed against the wiki.

    Steps:
    1. Resolve worktrees dir and target path.
    2. Dry-run: print and exit 0.
    3. If ``args.branch`` does not exist locally, create it with ``git branch``.
    4. ``git worktree add <target> <branch>``.
    5. Copy ``.millhouse/`` (minus junctions and wiki).
    6. Recreate hub-scope junctions (no ``<SLUG>`` token).
    7. Write ``.vscode/settings.json`` with color + title.
    """
    worktrees_dir = resolve_worktrees_dir(cfg, git_root)
    dir_name = args.dir_name or args.branch
    worktree_path = worktrees_dir / dir_name
    hub_subpath = cfg.get("hub_relative_path", ".")
    dest_hub = resolve_hub_relative_path(worktree_path, hub_subpath)

    if args.dry_run:
        print(f"[DryRun] Branch:   {args.branch}")
        print(f"[DryRun] Worktree: {worktree_path}")
        print(f"[DryRun] Color:    {args.color or '(auto)'}")
        return 0

    # Create the branch if it doesn't exist locally.
    check = _subprocess_util.run(
        ["git", "-C", str(git_root), "rev-parse", "--verify", args.branch]
    )
    if check.returncode != 0:
        branch_result = _subprocess_util.run(
            ["git", "-C", str(git_root), "branch", args.branch]
        )
        if branch_result.returncode != 0:
            print(
                f"[mill-worktree] Failed to create branch {args.branch!r}: "
                f"{branch_result.stderr.strip()!r}",
                file=sys.stderr,
            )
            return 1

    # Add the worktree. Branch already exists (created above or pre-existing),
    # so use `worktree add <path> <branch>` — NOT `-b` which requires a
    # non-existing branch name.
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    add_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "worktree", "add", str(worktree_path), args.branch]
    )
    if add_result.returncode != 0:
        print(
            f"[mill-worktree] git worktree add failed: {add_result.stderr.strip()!r}",
            file=sys.stderr,
        )
        return 1

    if hub_subpath != ".":
        dest_hub.mkdir(parents=True, exist_ok=True)

    # Copy .millhouse/ from hub, excluding junction aliases.
    _worktree.copy_millhouse(
        src=resolve_hub_path() / ".millhouse",
        dst=dest_hub / ".millhouse",
        exclude={"wiki", "active"},
    )

    # Recreate hub-scope junctions (those without <SLUG> token).
    try:
        wiki_path = resolve_wiki_path(git_root)
    except SystemExit:
        wiki_path = None

    if wiki_path is not None:
        junction_templates = _wiki.read_junctions(wiki_path)
        tokens = {
            "HUB_PATH": str(dest_hub),
            "CWD_PATH": str(dest_hub),
            "CONTAINER_PATH": str(resolve_container_path(git_root)),
            "WIKI_PATH": str(wiki_path),
            "REPO": resolve_main_worktree_root(git_root).name,
        }
        for junction_rel, target_template in junction_templates.items():
            if _junction.has_slug_token(target_template):
                # Slug-scoped junctions require an active task — skip.
                continue
            try:
                target = Path(_junction.resolve_target(target_template, tokens))
                link_path = worktree_path / junction_rel
                _junction.create(target, link_path)
            except (ValueError, OSError) as exc:
                print(
                    f"[mill-worktree] Junction {junction_rel!r} skipped: {exc}",
                    file=sys.stderr,
                )

    # Pick color and write .vscode/settings.json.
    if args.color is not None:
        color_hex = WORKTREE_COLOR_NAME_TO_HEX[args.color]
    else:
        color_hex = pick_worktree_color(worktrees_dir)

    short_name = resolve_short_name(cfg, git_root.name)
    window_title = f"{short_name}: {dir_name}"
    _vscode.write_settings(
        color_hex=color_hex,
        target=dest_hub / ".vscode" / "settings.json",
        window_title=window_title,
    )

    if hub_subpath != ".":
        stub_dir = worktree_path / ".millhouse"
        stub_dir.mkdir(parents=True, exist_ok=True)
        (stub_dir / "config.local.yaml").write_text(
            yaml.safe_dump({"hub_relative_path": hub_subpath}),
            encoding="utf-8",
        )

    print(f"Worktree: {worktree_path}")
    print(f"Branch:   {args.branch}")
    return 0


def _cmd_remove(args: argparse.Namespace, git_root: Path) -> int:
    """Implement the ``remove`` subcommand.

    Removes the `.millhouse/wiki` junction and the top-level `.active`
    junction from the worktree (best-effort), then runs
    ``git worktree remove --force``.
    """
    worktree_path = Path(args.worktree_path).resolve()

    # Best-effort removal of junctions inside .millhouse/.
    for junction_name in ("wiki",):
        candidate = worktree_path / ".millhouse" / junction_name
        try:
            _junction.remove(candidate)
        except ValueError as exc:
            print(
                f"[mill-worktree] Warning removing {candidate}: {exc}",
                file=sys.stderr,
            )

    # Also try the top-level .active junction (sibling to the worktree root).
    top_active = worktree_path / ".active"
    try:
        _junction.remove(top_active)
    except ValueError as exc:
        print(
            f"[mill-worktree] Warning removing {top_active}: {exc}",
            file=sys.stderr,
        )

    try:
        _worktree.remove(worktree_path, cwd=git_root, force=True)
    except _worktree.WorktreeError as exc:
        print(f"[mill-worktree] {exc}", file=sys.stderr)
        return 1

    print(f"Removed: {worktree_path}")
    return 0


def _cmd_list(git_root: Path) -> int:
    """Implement the ``list`` subcommand.

    Prints all registered worktrees from ``git worktree list --porcelain``,
    augmented with slug and task title from ``active.slug.md`` when present.
    """
    try:
        worktrees = _worktree.list_worktrees(cwd=git_root)
    except _worktree.WorktreeError as exc:
        print(f"[mill-worktree] {exc}", file=sys.stderr)
        return 1

    for entry in worktrees:
        path_str = entry.get("path") or ""
        branch = entry.get("branch") or "(detached)"
        slug = ""
        title = ""
        if path_str:
            mill_dir = Path(path_str) / ".millhouse"
            try:
                data = _active.read_all(mill_dir)
                slug = data.get("slug", "")
                title = data.get("task_title", "")
            except _active.ActiveError:
                pass
        task_info = f"  [{slug}] {title}".rstrip() if slug else ""
        print(f"{path_str}  ({branch}){task_info}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the create / remove / list subcommand.

    Args:
        argv: Argument vector. Defaults to ``sys.argv[1:]``.

    Returns:
        Exit code: 0 on success, 1 on any error.
    """
    valid_colors = ", ".join(sorted(WORKTREE_COLOR_NAME_TO_HEX))
    parser = argparse.ArgumentParser(
        prog="mill-worktree",
        description="Generic worktree management (no wiki claim).",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # create subcommand
    create_p = sub.add_parser("create", help="Create a new worktree.")
    create_p.add_argument(
        "--branch",
        required=True,
        help="Branch to check out in the new worktree (created if absent).",
    )
    create_p.add_argument(
        "--dir-name",
        default=None,
        dest="dir_name",
        help="Override directory name under the worktrees container.",
    )
    create_p.add_argument(
        "--color",
        default=None,
        choices=list(WORKTREE_COLOR_NAME_TO_HEX),
        help=f"Title-bar color name; one of: {valid_colors}. Default: auto-rotation.",
    )
    create_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print what would happen without making changes.",
    )

    # remove subcommand
    remove_p = sub.add_parser("remove", help="Remove a worktree.")
    remove_p.add_argument("worktree_path", help="Absolute path to the worktree.")

    # list subcommand
    sub.add_parser("list", help="List all registered worktrees.")

    args = parser.parse_args(argv)

    git_root = resolve_git_root()

    if args.subcommand == "create":
        try:
            wiki_path = resolve_wiki_path(git_root)
            cfg = _load_config(wiki_path, resolve_hub_path())
        except SystemExit:
            cfg = {}
        return _cmd_create(args, git_root, cfg)

    if args.subcommand == "remove":
        return _cmd_remove(args, git_root)

    if args.subcommand == "list":
        return _cmd_list(git_root)

    print(f"[mill-worktree] Unknown subcommand: {args.subcommand!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
