# TODO(integration): full mill-claim integration test pending PTY harness for the dirty-tree prompt
"""
mill-claim — claim a task from the wiki Home.md in the current worktree.

Unlike mill-spawn, which creates a new worktree directory, mill-claim
operates on the git checkout you are already in. After claiming, you
stay in the same directory on a new branch for the task.

Flow:
    1. Resolve the wiki clone via ``_paths.resolve_wiki_path``.
    2. Fast-forward pull the wiki so we pick against current state.
    3. Parse ``Home.md``; pick a task via ``pick_task_single_or_multi``
       (``--slug`` short-circuit, ``[s]`` fast-path, numbered prompt).
    4. Multi-select is not yet wired (arrives in Card 13).
    5. Mark the chosen task ``[active]`` under the wiki lock.
    6. Capture the current branch name as the parent for status.md.
    7. If the working tree is dirty, prompt: stash, carry, or abort.
    8. Check out a new branch via ``git checkout -b <branch_name>``.
    9. If stash was chosen, pop the stash onto the new branch.
   10. Recreate the ``.active`` junction pointing at this task's wiki dir.
   11. Write the per-worktree active marker and the initial status.md.
   12. Print Branch / Status / "in-place".

Usage:
    python plugins/mill/scripts/mill-claim.py
        [--slug <slug>]   # skip the picker; claim this specific slug
        [--dry-run]       # print decisions; make no changes

Exit codes:
    0 — task claimed (or empty backlog)
    1 — any non-empty failure
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

import _junction
import _spawn_core
import _subprocess_util
import _tasks_md
import _vscode
import _wiki
from _config import load_config as _load_config_lenient
from _paths import resolve_container_path, resolve_git_root, resolve_main_worktree_root, resolve_short_name, resolve_wiki_path


# --------------------------------------------------------------------------- #
# Private helpers                                                              #
# --------------------------------------------------------------------------- #


def _load_config(wiki_path: Path, git_root: Path) -> dict:
    """Load config; raises SystemExit when ``wiki/config.yaml`` is absent.

    Strict-mode wrapper around ``_config.load_config``: mill-claim requires
    a properly initialised wiki config to resolve branch prefixes and other
    spawn settings, so a missing file is always a fatal user error here.
    """
    shared_path = wiki_path / "config.yaml"
    if not shared_path.exists():
        raise SystemExit(f"Missing config at {shared_path}")
    return _load_config_lenient(wiki_path, git_root)


def _is_dirty(git_root: Path) -> bool:
    """Return True if the working tree has any uncommitted changes."""
    result = _subprocess_util.run(
        ["git", "-C", str(git_root), "status", "--porcelain"]
    )
    return bool(result.stdout.strip())


def _prompt_dirty_tree() -> int:
    """
    Prompt the user for how to handle a dirty working tree.

    Presents three numbered options and reads stdin until the user enters
    a valid choice. Re-prompts on invalid input up to 3 total attempts.
    On option 3 (Abort) or exhausted retries, raises ``SystemExit(1)``.

    Returns:
        1 — stash before checkout, pop after.
        2 — carry changes onto the new branch without stashing.

    Raises:
        SystemExit(1): user chose Abort or all 3 attempts were invalid.
    """
    print("Working tree has uncommitted changes. Choose:", file=sys.stderr)
    print(
        "1) Stash, create branch, then unstash on the new branch (Recommended)",
        file=sys.stderr,
    )
    print("2) Carry the changes onto the new branch (no stash)", file=sys.stderr)
    print("3) Abort", file=sys.stderr)

    for _ in range(3):
        try:
            raw = input("Choice: ").strip()
        except EOFError:
            break
        if raw == "1":
            return 1
        if raw == "2":
            return 2
        if raw == "3":
            raise SystemExit(1)
        print("[claim] Enter 1, 2, or 3.", file=sys.stderr)

    raise SystemExit(1)


_HUB_COLOR = "#2d7d46"
_HUB_COLOR_PATTERN = '"titleBar.activeBackground": "#2d7d46"'


def _update_hub_vscode_title(git_root: Path, cfg: dict, slug: str) -> None:
    """Flip the hub's VS Code title to '<short>: <slug>' when cwd is the hub.

    Skips silently when the settings file is absent, unreadable, or does not
    have the hub green background (indicating cwd is a differently-coloured
    worktree, not the hub).
    """
    settings_path = git_root / ".vscode" / "settings.json"
    if not settings_path.exists():
        return
    try:
        content = settings_path.read_text(encoding="utf-8")
    except OSError:
        return
    if _HUB_COLOR_PATTERN not in content:
        return
    short = resolve_short_name(cfg, git_root.name)
    _vscode.write_settings(
        color_hex=_HUB_COLOR,
        target=settings_path,
        short_name=short,
        slug=slug,
    )


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Claim a task from Home.md in the current working tree (in-place).",
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="Skip the picker and claim this specific slug (must be unmarked or [s]).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen; make no changes.",
    )
    args = parser.parse_args(argv)

    git_root = resolve_git_root()
    wiki_path = resolve_wiki_path(git_root)
    mill_dir = git_root / ".millhouse"
    cfg = _load_config(wiki_path, git_root)
    spawn_cfg = cfg.get("spawn", {})

    home_path = wiki_path / "Home.md"
    if not home_path.exists():
        raise SystemExit(
            f"Wiki not found at {wiki_path}. Run /mill-setup to create it, "
            "or set paths.wiki: in .millhouse/config.local.yaml."
        )

    _wiki.sync_pull(wiki_path, slug="mill-claim")
    home_text = home_path.read_text(encoding="utf-8")
    tasks = _tasks_md.parse(home_text)

    # Pick a task; multi-select is not yet wired (arrives in Card 13).
    try:
        mode, picked, _ = _spawn_core.pick_task_single_or_multi(tasks, slug=args.slug)
    except ValueError as exc:
        print(f"[claim] {exc}", file=sys.stderr)
        return 1

    if mode == "empty":
        print(
            "[claim] No pickable tasks. Mark a task [s] or leave one "
            "unmarked (see /mill-add). Exiting.",
            file=sys.stderr,
        )
        return 0

    if mode == "multi":
        # Collect merged entry from the user, then atomically groom+claim.
        source_slugs = [t.slug for t in picked]
        merged_title, merged_slug, body_for_home, has_proposal, proposal_body = (
            _spawn_core.prompt_merged_entry(picked)
        )
        picked = _spawn_core.multi_select_groom_then_claim(
            wiki_path, source_slugs, merged_title, merged_slug, body_for_home,
            has_proposal=has_proposal, proposal_body=proposal_body,
        )

    slug = picked.slug

    branch_prefix = spawn_cfg.get("branch_prefix", "")
    branch_name = f"{branch_prefix}/{slug}" if branch_prefix else slug

    if args.dry_run:
        print(f"[DryRun] Task:    {picked.title} [{slug}]")
        print(f"[DryRun] Branch:  {branch_name}")
        print(f"[DryRun] Status:  {wiki_path / 'active' / slug / 'status.md'}")
        print("[DryRun] Mode:    in-place")
        return 0

    # Claim under the wiki lock. Multi mode already claimed inside
    # multi_select_groom_then_claim, so skip to avoid a double-claim.
    if mode != "multi":
        _spawn_core.claim_in_wiki(wiki_path, slug)

    try:
        parent_branch = _spawn_core.capture_parent_branch(git_root)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    # Pre-flight dirty-tree check: stash, carry, or abort before branching.
    stashed = False
    if _is_dirty(git_root):
        choice = _prompt_dirty_tree()
        if choice == 1:
            stash_result = _subprocess_util.run(
                [
                    "git", "-C", str(git_root),
                    "stash", "push", "-m", f"mill-claim stash before {slug}",
                ]
            )
            if stash_result.returncode != 0:
                raise SystemExit(
                    f"[claim] git stash failed: {stash_result.stderr.strip()!r}"
                )
            stashed = True

    # Create the new branch in the current worktree.
    checkout = _subprocess_util.run(
        ["git", "-C", str(git_root), "checkout", "-b", branch_name]
    )
    if checkout.returncode != 0:
        raise SystemExit(
            f"[claim] git checkout -b {branch_name!r} failed: "
            f"{checkout.stderr.strip()!r}"
        )

    # Restore stashed changes onto the new branch.
    if stashed:
        pop_result = _subprocess_util.run(
            ["git", "-C", str(git_root), "stash", "pop"]
        )
        if pop_result.returncode != 0:
            stash_list = _subprocess_util.run(
                ["git", "-C", str(git_root), "stash", "list"]
            )
            print(
                f"Stash created but pop failed. "
                f"Stash list: {stash_list.stdout.strip()}. Resolve manually.",
                file=sys.stderr,
            )
            raise SystemExit(1)

    # Create the portal entry for this worktree and recreate .active.
    # Order is CRITICAL: portal entry must exist before recreate_active_junction
    # because that function calls target.mkdir(exist_ok=True) on portals/<slug>.
    # If we created portals/<slug> as a real dir first and then tried to make it
    # a junction, _junction.remove would fail ("not a junction or symlink").
    container_path = resolve_container_path(git_root)
    main_root = resolve_main_worktree_root(git_root)
    (container_path / "portals").mkdir(parents=True, exist_ok=True)

    portal_link = container_path / "portals" / slug
    if not portal_link.exists() and not portal_link.is_symlink():
        # First claim: create portal entry pointing at this worktree.
        _junction.create(target=main_root, link_path=portal_link)
    else:
        # Portal entry exists: check if it points at the current worktree.
        existing_target = os.path.realpath(str(portal_link))
        current_target = os.path.realpath(str(main_root))
        if existing_target != current_target:
            # Points elsewhere — remove and recreate.
            _junction.remove(portal_link)
            _junction.create(target=main_root, link_path=portal_link)
        # else: already correct, skip.

    _spawn_core.recreate_active_junction(slug, mill_dir, container_path)

    # Write the per-worktree active marker so downstream skills find this task.
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _spawn_core.write_active_marker(
        mill_dir,
        slug=slug,
        title=picked.title,
        branch=branch_name,
        ts=ts,
    )

    # Render and write the initial status.md; commit on task branch.
    status_abs = _spawn_core.write_initial_status(
        worktree_path=git_root,
        slug=slug,
        title=picked.title,
        ts=ts,
        parent_branch=parent_branch,
        branch=branch_name,
    )

    _update_hub_vscode_title(git_root, cfg, slug)

    print(f"Branch:  {branch_name}")
    print(f"Status:  {status_abs}")
    print("Mode:    in-place")
    return 0


if __name__ == "__main__":
    sys.exit(main())
