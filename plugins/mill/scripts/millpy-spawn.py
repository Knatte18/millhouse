"""
mill-spawn — claim one task from the wiki Home.md and spin up a worktree for it.

Flow:
    1. Resolve the wiki clone via ``_paths.resolve_wiki_path`` (``.millhouse/wiki`` is a junction for IDE/terminal convenience only).
    2. Fast-forward pull the wiki so we pick against current state.
    3. Parse ``Home.md``; pick a task via ``pick_task`` (fast-path on
       ``[s]``, numbered picker on unmarked-only, exit 0 when empty).
    4. Under the wiki lock: mark the chosen task ``[active]``, regenerate
       ``_Sidebar.md``, and commit+push.
    5. Create the worktree at ``<worktrees-dir>/<slug>`` on branch
       ``<branch-prefix>/<slug>`` (prefix optional).
    6. Propagate ``.millhouse/`` (minus ``wiki``, ``active`` junctions).
    7. Recreate junctions from the wiki config's ``junctions:`` block
       inside the new worktree.
    8. Pick a non-green VS Code title-bar colour not in use by sibling
       worktrees; write ``.vscode/settings.json`` via ``_vscode``.
    9. Write the initial ``task/status.md`` (phase=discussing) and commit+push.
   10. Print worktree-path, branch, and status path on stdout.

Usage:
    python plugins/mill/scripts/mill-spawn.py
        [--slug <slug>]        # skip the picker, claim this specific slug
        [--dry-run]             # print decisions; make no changes

Exit codes:
    0 — worktree created (or empty backlog reported)
    1 — any non-empty failure path
"""
from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path
from typing import Optional

import yaml

import _junction
import _paths
import _setup
import _spawn_core
import _vscode
import _worktree
from _config import load_config as _load_config
from _paths import resolve_container_path, resolve_git_root, resolve_hub_path, resolve_hub_relative_path, resolve_main_worktree_root, resolve_short_name, resolve_wiki_path, resolve_worktrees_dir
from _spawn_core import pick_worktree_color
from wiki import _client as wiki


# --------------------------------------------------------------------------- #
# Path resolution                                                             #
# --------------------------------------------------------------------------- #


def _build_tokens(
    hub_path: Path,
    wiki_path: Path,
    slug: Optional[str] = None,
) -> dict[str, str]:
    """Assemble the token map used by ``_junction.resolve_target``."""
    tokens = {
        "HUB_PATH": str(hub_path),
        "CWD_PATH": str(hub_path),
        "CONTAINER_PATH": str(resolve_container_path(hub_path)),
        "WIKI_PATH": str(wiki_path),
        "REPO": resolve_main_worktree_root(hub_path).name,
    }
    if slug is not None:
        tokens["SLUG"] = slug
    return tokens


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Claim a task from Home.md and spawn a worktree for it.",
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
    hub = resolve_hub_path()
    wiki_path = resolve_wiki_path(git_root)
    cfg = _load_config(hub, hub)
    hub_subpath = cfg.get("hub_relative_path", ".")
    spawn_cfg = cfg.get("spawn", {})

    home_path = wiki_path / "Home.md"
    if not home_path.exists():
        raise SystemExit(
            f"Wiki not found at {wiki_path}. Run /mill-setup to create it, "
            "or set paths.wiki: in .millhouse/config.local.yaml."
        )

    tasks = wiki.list_tasks_brief(wiki_path)

    # Pick the task. --slug short-circuits to single; multi fires from the
    # numbered prompt when the user enters comma-separated indices.
    try:
        mode, picked, _ = _spawn_core.pick_task_single_or_multi(tasks, slug=args.slug)
    except ValueError as exc:
        print(f"[spawn] {exc}", file=sys.stderr)
        return 1

    if mode == "empty":
        print(
            "[spawn] No pickable tasks. Mark a task [s] or leave one "
            "unmarked (see /mill-add). Exiting.",
            file=sys.stderr,
        )
        return 0

    if mode == "multi":
        # Collect merged entry from the user, then atomically groom+claim.
        source_slugs = [t["slug"] for t in picked]
        merged_title, merged_slug, body_for_home, has_proposal, proposal_body = (
            _spawn_core.prompt_merged_entry(picked)
        )
        picked = _spawn_core.multi_select_groom_then_claim(
            wiki_path, source_slugs, merged_title, merged_slug, body_for_home,
            has_proposal=has_proposal, proposal_body=proposal_body,
        )

    slug = picked["slug"]

    branch_prefix = spawn_cfg.get("branch_prefix", "")
    branch_name = f"{branch_prefix}{slug}" if branch_prefix else slug

    worktrees_dir = resolve_worktrees_dir(cfg, git_root)
    worktree_path = worktrees_dir / slug
    dest_hub = resolve_hub_relative_path(worktree_path, hub_subpath)

    if args.dry_run:
        print(f"[DryRun] Task:     {picked['title']} [{slug}]")
        print(f"[DryRun] Branch:   {branch_name}")
        print(f"[DryRun] Worktree: {worktree_path}")
        print(f"[DryRun] Status:   {_paths.status_path(dest_hub, cfg)}")
        return 0

    # Claim the task under the wiki lock. Multi mode already claimed inside
    # multi_select_groom_then_claim, so skip to avoid a double-claim.
    if mode != "multi":
        _spawn_core.claim_in_wiki(wiki_path, slug)

    # Capture the hub's current branch BEFORE creating the new worktree
    # so we can record it in status.md as the parent — mill-merge /
    # mill-cleanup read this to know where to merge back to.
    try:
        parent_branch = _spawn_core.capture_parent_branch(git_root)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    # Create the worktree. git refuses if the target path exists, so we
    # only ensure the PARENT exists. Any failure here surfaces as a
    # WorktreeError with captured stderr.
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    _worktree.create(branch_name, worktree_path, cwd=git_root)

    if hub_subpath != ".":
        dest_hub.mkdir(parents=True, exist_ok=True)

    # Propagate .millhouse/ minus task/worktree-specific subtrees. The
    # excluded names cover (a) the scratch area whose contents belong to
    # the parent clone's last run and (b) junctions that must be
    # recreated per-worktree.
    _worktree.copy_millhouse(
        src=hub / ".millhouse",
        dst=dest_hub / ".millhouse",
        exclude={"wiki", "active"},
    )

    # Timestamp used for write_initial_status.
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    container_path = resolve_container_path(git_root)
    (container_path / "portals").mkdir(parents=True, exist_ok=True)
    (dest_hub / "_mill").mkdir(parents=True, exist_ok=True)
    # Portal entry: <container>/portals/<slug> -> <hub>/_mill/ (dest_hub, not worktree root).
    _junction.create(target=dest_hub / "_mill", link_path=container_path / "portals" / slug)

    # Create remaining junctions/hardlinks from junctions config for the new
    # worktree (.wiki, .portals). _setup.create_hub_links uses the token-scope
    # filter so that entries requiring <SLUG> are only created in slug-bearing
    # (task) worktrees.
    dest_tokens = _build_tokens(dest_hub, wiki_path, slug=slug)
    _setup.create_hub_links(dest_hub, wiki_path, dest_tokens)

    # .active is task-scoped and points to <hub>/_mill/ -- created explicitly
    # rather than via mill-config.yaml junctions block so it is not auto-created
    # in non-task worktrees.
    _spawn_core.recreate_active_junction(dest_hub)
    _spawn_core.write_hub_active_indicator(git_root, slug)

    # Pick a colour + write .vscode/settings.json. The palette scans the
    # *existing* sibling worktrees in the shared worktrees dir; the newly
    # created one has no settings.json yet, so it does not self-contribute
    # to the "used" set.
    color = pick_worktree_color(worktrees_dir)
    short = resolve_short_name(cfg, git_root.name)
    _vscode.write_settings(color_hex=color, target=dest_hub / ".vscode" / "settings.json", short_name=short, slug=slug)
    # When hub lives in a subfolder, write a bootstrap stub at worktree root so
    # terminal/vscode discovery can find dest_hub without walking the tree.
    if hub_subpath != ".":
        stub_dir = worktree_path / ".millhouse"
        stub_dir.mkdir(parents=True, exist_ok=True)
        (stub_dir / "config.local.yaml").write_text(
            yaml.safe_dump({"hub_relative_path": hub_subpath}),
            encoding="utf-8",
        )

    # Use the task title as description so the status.md template renders without empty placeholders.
    status_abs = _spawn_core.write_initial_status(
        worktree_path=dest_hub,
        slug=slug,
        title=picked["title"],
        ts=ts,
        parent_branch=parent_branch,
        branch=branch_name,
        cfg=cfg,
    )

    print(f"Worktree: {worktree_path}")
    print(f"Branch:   {branch_name}")
    print(f"Status:   {status_abs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
