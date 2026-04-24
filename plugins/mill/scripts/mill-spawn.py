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
    6. Propagate ``.millhouse/`` (minus ``scratch``, ``wiki``, ``active``).
    7. Recreate junctions from the wiki config's ``junctions:`` block
       inside the new worktree.
    8. Pick a non-green VS Code title-bar colour not in use by sibling
       worktrees; write ``.vscode/settings.json`` via ``_vscode``.
    9. Write the initial ``wiki/active/<slug>/status.md`` (phase=discussing)
       and commit+push.
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
import json
import sys
from pathlib import Path
from typing import Optional

import _active
import _junction
import _sidebar
import _status
import _subprocess_util
import _tasks_md
import _vscode
import _wiki
import _worktree
from _paths import resolve_git_root, resolve_path, resolve_wiki_path


# Worktree title-bar palette. Green is reserved for the hub (main worktree);
# child worktrees pick the first non-green colour not already used by a
# sibling. Mirrors v1's palette so users keep their colour muscle memory.
_WORKTREE_COLOR_PALETTE: list[str] = [
    "#2d7d46",  # green (hub only)
    "#7d2d6b",  # purple
    "#2d4f7d",  # blue
    "#7d5c2d",  # yellow
    "#6b2d2d",  # red
    "#2d6b6b",  # cyan
    "#4a2d7d",  # indigo
    "#7d462d",  # orange
]
_MAIN_WORKTREE_COLOR = "#2d7d46"


# --------------------------------------------------------------------------- #
# Task picker                                                                 #
# --------------------------------------------------------------------------- #


def pick_task(tasks: list[_tasks_md.Task]) -> tuple[str, Optional[_tasks_md.Task], list[_tasks_md.Task]]:
    """
    Decide which task mill-spawn should claim.

    Returns ``(mode, picked, candidates)``:

    - ``"fast-path"``: at least one task carries the ``[s]`` marker; ``picked``
      is the first such task in file order, ``candidates`` is empty.
    - ``"numbered"``: no ``[s]`` task, but at least one unmarked backlog task
      exists. ``picked`` is ``None``; the caller presents ``candidates`` as
      a numbered list and reads the user's choice.
    - ``"empty"``: nothing to pick (all tasks are claimed / done / abandoned,
      or Home.md has no tasks at all). Both ``picked`` and ``candidates``
      are empty.

    ``[active]``, ``[done]``, and ``[abandoned]`` are filtered out; those
    phases are managed by other scripts.
    """
    fast = next((t for t in tasks if t.phase == "s"), None)
    if fast is not None:
        return ("fast-path", fast, [])
    unmarked = [t for t in tasks if t.phase is None]
    if not unmarked:
        return ("empty", None, [])
    return ("numbered", None, unmarked)


def _prompt_numbered(candidates: list[_tasks_md.Task]) -> Optional[_tasks_md.Task]:
    """Read a 1-indexed choice from stdin; return the chosen Task or None."""
    print("Pick a task:", file=sys.stderr)
    for i, t in enumerate(candidates, start=1):
        marker = " (proposal)" if t.has_proposal else ""
        print(f"  {i}) {t.title} [{t.slug}]{marker}", file=sys.stderr)
    try:
        raw = input("Pick a task number: ")
    except EOFError:
        print("[spawn] No input available for numbered picker.", file=sys.stderr)
        return None
    try:
        choice = int(raw.strip())
    except ValueError:
        print(f"[spawn] Not a number: {raw!r}", file=sys.stderr)
        return None
    if choice < 1 or choice > len(candidates):
        print(
            f"[spawn] Choice {choice} out of range (1..{len(candidates)}).",
            file=sys.stderr,
        )
        return None
    return candidates[choice - 1]


# --------------------------------------------------------------------------- #
# VS Code colour                                                              #
# --------------------------------------------------------------------------- #


def _read_worktree_color(settings_path: Path) -> Optional[str]:
    """Return the ``titleBar.activeBackground`` hex from settings.json, or None."""
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        customizations = data.get("workbench.colorCustomizations") or {}
        value = customizations.get("titleBar.activeBackground")
        return value.lower() if isinstance(value, str) else None
    except (OSError, ValueError):
        return None


def pick_worktree_color(worktrees_dir: Path) -> str:
    """
    Pick the first non-green palette colour not used by any sibling worktree.

    Scans ``<worktrees_dir>/*/.vscode/settings.json`` for existing
    ``titleBar.activeBackground`` values. Returns the first non-green
    palette colour missing from that set. If every non-green colour is in
    use, wraps to the first non-green (never green — that's reserved for
    the hub).

    Args:
        worktrees_dir: Directory holding per-task worktrees. Missing dir
            returns the first non-green colour straight away.

    Returns:
        A hex colour like ``"#7d2d6b"``.
    """
    used: set[str] = set()
    if worktrees_dir.exists():
        for entry in worktrees_dir.iterdir():
            if not entry.is_dir():
                continue
            value = _read_worktree_color(entry / ".vscode" / "settings.json")
            if value:
                used.add(value)

    non_green = [c for c in _WORKTREE_COLOR_PALETTE if c.lower() != _MAIN_WORKTREE_COLOR.lower()]
    for color in non_green:
        if color.lower() not in used:
            return color
    return non_green[0]


# --------------------------------------------------------------------------- #
# Path resolution                                                             #
# --------------------------------------------------------------------------- #


def _load_config(wiki_path: Path, git_root: Path) -> dict:
    """Load ``wiki/config.yaml`` deep-merged with ``.millhouse/config.local.yaml``."""
    import yaml

    shared_path = wiki_path / "config.yaml"
    if not shared_path.exists():
        raise SystemExit(f"Missing config at {shared_path}")
    cfg = yaml.safe_load(shared_path.read_text(encoding="utf-8")) or {}

    local_path = git_root / ".millhouse" / "config.local.yaml"
    if local_path.exists():
        local_cfg = yaml.safe_load(local_path.read_text(encoding="utf-8")) or {}
        cfg = _deep_merge(cfg, local_cfg)
    return cfg


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Shallow-recursive deep merge; overlay wins on scalar conflicts."""
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _build_tokens(
    git_root: Path,
    wiki_path: Path,
    slug: Optional[str] = None,
) -> dict[str, str]:
    """Assemble the token map used by ``_junction.resolve_target``."""
    tokens = {
        "HUB_PATH": str(git_root),
        "CWD_PATH": str(Path.cwd()),
        "CONTAINER_PATH": str(git_root.parent),
        "WIKI_PATH": str(wiki_path),
        "REPO": git_root.name,
    }
    if slug is not None:
        tokens["SLUG"] = slug
    return tokens


def _resolve_worktrees_dir(cfg: dict, tokens: dict[str, str], git_root: Path) -> Path:
    """Return the worktrees-dir.

    When ``cfg["spawn"]["worktrees_dir"]`` is set explicitly (user override),
    treat it as a token template and substitute. When absent, delegate to
    ``resolve_path("worktrees", git_root)`` — this yields the
    hub-form default (``<container>/worktrees/``) or the prefix-form default
    (``<container>/<repo>.worktrees/``) per the unified sibling-path rule.
    """
    template = cfg.get("spawn", {}).get("worktrees_dir")
    if template is not None:
        return Path(_junction.resolve_target(template, tokens))
    return resolve_path("worktrees", git_root)


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
    wiki_path = resolve_wiki_path(git_root)
    cfg = _load_config(wiki_path, git_root)
    spawn_cfg = cfg.get("spawn", {})

    home_path = wiki_path / "Home.md"
    if not home_path.exists():
        raise SystemExit(
            f"Wiki not found at {wiki_path}. Run /mill-setup to create it, "
            "or set paths.wiki: in .millhouse/config.local.yaml."
        )

    _wiki.sync_pull(wiki_path)
    home_text = home_path.read_text(encoding="utf-8")
    tasks = _tasks_md.parse(home_text)

    # Pick the task. --slug short-circuits the picker; otherwise we use
    # the standard fast-path / numbered / empty flow.
    if args.slug is not None:
        picked = next(
            (t for t in tasks if t.slug == args.slug and t.phase in (None, "s")),
            None,
        )
        if picked is None:
            print(
                f"[spawn] --slug {args.slug!r} not found in Home.md or already claimed.",
                file=sys.stderr,
            )
            return 1
    else:
        mode, picked, candidates = pick_task(tasks)
        if mode == "empty":
            print(
                "[spawn] No pickable tasks. Mark a task [s] or leave one "
                "unmarked (see /mill-add). Exiting.",
            )
            return 0
        if mode == "numbered":
            picked = _prompt_numbered(candidates)
            if picked is None:
                return 1

    assert picked is not None  # pick_task/--slug guarantees this
    slug = picked.slug

    branch_prefix = spawn_cfg.get("branch_prefix", "")
    branch_name = f"{branch_prefix}/{slug}" if branch_prefix else slug

    tokens = _build_tokens(git_root, wiki_path, slug=slug)
    worktrees_dir = _resolve_worktrees_dir(cfg, tokens, git_root)
    worktree_path = worktrees_dir / slug

    if args.dry_run:
        print(f"[DryRun] Task:     {picked.title} [{slug}]")
        print(f"[DryRun] Branch:   {branch_name}")
        print(f"[DryRun] Worktree: {worktree_path}")
        print(f"[DryRun] Status:   {wiki_path / 'active' / slug / 'status.md'}")
        return 0

    # Claim the task under the wiki lock so we don't race another writer
    # editing Home.md. Sidebar regen + commit+push sit inside the same
    # lock because _sidebar reads Home.md to decide what to render.
    _wiki.acquire_lock(wiki_path, slug)
    try:
        claimed_text = _tasks_md.claim(home_text, slug)
        home_path.write_text(claimed_text, encoding="utf-8")
        _sidebar.regenerate(wiki_path)
        _wiki.write_commit_push(
            wiki_path, ["Home.md", "_Sidebar.md"], f"task: claim {slug}"
        )
    finally:
        _wiki.release_lock(wiki_path)

    # Capture the hub's current branch BEFORE creating the new worktree
    # so we can record it in status.md as the parent — mill-merge /
    # mill-cleanup read this to know where to merge back to.
    parent_result = _subprocess_util.run(
        ["git", "-C", str(git_root), "rev-parse", "--abbrev-ref", "HEAD"],
    )
    if parent_result.returncode != 0:
        raise SystemExit(
            f"Could not resolve hub parent branch: {parent_result.stderr.strip()!r}"
        )
    parent_branch = parent_result.stdout.strip()

    # Create the worktree. git refuses if the target path exists, so we
    # only ensure the PARENT exists. Any failure here surfaces as a
    # WorktreeError with captured stderr.
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    _worktree.create(branch_name, worktree_path, cwd=git_root)

    # Propagate .millhouse/ minus task/worktree-specific subtrees. The
    # excluded names cover (a) the scratch area whose contents belong to
    # the parent clone's last run and (b) junctions that must be
    # recreated per-worktree.
    _worktree.copy_millhouse(
        src=git_root / ".millhouse",
        dst=worktree_path / ".millhouse",
        exclude={"scratch", "wiki", "active"},
    )

    # Recreate every junction from the wiki config for the new worktree.
    # Per-worktree junctions (target contains <SLUG>) point at this task's
    # active dir and must be created with the slug-aware tokens.
    junction_templates = _wiki.read_junctions(wiki_path)
    for junction_rel, target_template in junction_templates.items():
        target = Path(_junction.resolve_target(target_template, tokens))
        link_path = worktree_path / junction_rel
        # mill-spawn always owns a freshly-created worktree, so pre-existing
        # junctions at these paths would be a bug in the copy step or a
        # stale filesystem — surface the error by letting _junction.create
        # raise rather than silently re-targeting.
        if _junction.has_slug_token(target_template):
            target.mkdir(parents=True, exist_ok=True)
        _junction.create(target, link_path)

    # Pick a colour + write .vscode/settings.json. The palette scans the
    # *existing* sibling worktrees in the shared worktrees dir; the newly
    # created one has no settings.json yet, so it does not self-contribute
    # to the "used" set.
    color = pick_worktree_color(worktrees_dir)
    window_title = f"{picked.title}: " + "${activeEditorShort}"
    _vscode.write_settings(
        color_hex=color,
        window_title=window_title,
        target=worktree_path / ".vscode" / "settings.json",
    )

    # Write the per-worktree marker file so every downstream script /
    # skill in this worktree can locate its task state.
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _active.write(
        worktree_path / ".millhouse",
        slug=slug,
        task_title=picked.title,
        branch=branch_name,
        spawned_at=ts,
    )

    # Render and write the initial status.md. v2's Home.md has no
    # dedicated description column; use the task title as description so
    # the template renders without empty placeholders.
    status_text = _status.render_initial(
        task_title=picked.title,
        task_description=picked.title,
        timestamp=ts,
        parent_branch=parent_branch,
    )
    status_rel = f"active/{slug}/status.md"
    status_abs = wiki_path / status_rel
    status_abs.parent.mkdir(parents=True, exist_ok=True)
    status_abs.write_text(status_text, encoding="utf-8")
    _wiki.acquire_lock(wiki_path, slug)
    try:
        _wiki.write_commit_push(
            wiki_path, [status_rel], f"spawn: init status for {slug}"
        )
    finally:
        _wiki.release_lock(wiki_path)

    print(f"Worktree: {worktree_path}")
    print(f"Branch:   {branch_name}")
    print(f"Status:   {status_abs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
