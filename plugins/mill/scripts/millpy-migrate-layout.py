"""
One-shot migration tool: moves an existing mill clone from the old
``hub/`` + ``worktrees/`` layout to the new ``wts/<repo>/`` + ``wts/<slug>/``
+ ``portals/`` layout.

Canonical step list: wiki/active/container-restructure/discussion.md
## Decisions → migration-strategy

Usage:
    python millpy-migrate-layout.py [--dry-run]
    python millpy-migrate-layout.py --step rename-junctions [--dry-run]

Options:
    --dry-run   Print planned operations with absolute paths and exit 0.
                No filesystem writes are performed.

Exit codes:
    0   Success (or successful dry-run).
    1   Pre-flight halt or any subprocess failure.

IMPORTANT: mill-setup MUST NOT be run between deploying the new mill
code and completing this migration. Run mill-setup AFTER the migration
completes (Step 6 instructs you to do this).

Pass ``--step rename-junctions`` to migrate an existing container from the old
``.millhouse/wiki + .others + .active`` junction layout to the new
``.wiki + .portals`` layout.

This script is NOT registered in _shortcuts.SHORTCUT_SCRIPTS because it
is intended for manual one-shot invocation outside the normal mill
workflow.
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sys
from pathlib import Path

import _config
import _gitignore
import _junction
import _setup
import _spawn_core
import _status
import _subprocess_util
import _tasks_md
import _timestamp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log(msg: str, log_fh, dry_run: bool) -> None:
    """Echo ``msg`` to stderr (always) and to the log file (when not dry-run)."""
    print(msg, file=sys.stderr)
    if log_fh is not None:
        print(msg, file=log_fh)


def _run(argv: list[str], log_fh, dry_run: bool, *, cwd: Path | None = None):
    """Run a subprocess, logging and checking exit code.

    In dry-run mode, prints the command but does NOT execute it.
    Returns None in dry-run mode; returns CompletedProcess otherwise.
    Exits with code 1 on non-zero return code (outside dry-run).
    """
    cmd_str = " ".join(str(a) for a in argv)
    if dry_run:
        _log(f"  [dry-run] would run: {cmd_str}", log_fh, dry_run)
        return None
    _log(f"  [run] {cmd_str}", log_fh, dry_run)
    result = _subprocess_util.run(argv, cwd=cwd)
    if result.returncode != 0:
        print(
            f"ERROR: command failed (exit {result.returncode}): {cmd_str}\n"
            f"  stderr: {result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    return result


def _mkdir(path: Path, log_fh, dry_run: bool) -> None:
    """Create ``path`` if it does not exist, logging the operation."""
    if path.exists():
        _log(f"  [skip] directory already exists: {path}", log_fh, dry_run)
        return
    if dry_run:
        _log(f"  [dry-run] would mkdir: {path}", log_fh, dry_run)
        return
    _log(f"  [mkdir] {path}", log_fh, dry_run)
    path.mkdir(parents=True, exist_ok=True)


def _rmdir(path: Path, log_fh, dry_run: bool) -> None:
    """Remove an empty directory ``path``, logging the operation."""
    if dry_run:
        _log(f"  [dry-run] would rmdir: {path}", log_fh, dry_run)
        return
    _log(f"  [rmdir] {path}", log_fh, dry_run)
    try:
        os.rmdir(str(path))
    except OSError as exc:
        print(
            f"ERROR: rmdir {path} failed: {exc}\n"
            f"  The directory is not empty -- a worktree-move may have failed silently.",
            file=sys.stderr,
        )
        sys.exit(1)


def _shutil_move(src: Path, dst: Path, log_fh, dry_run: bool) -> None:
    """Move ``src`` to ``dst`` via shutil.move, logging the operation."""
    if dry_run:
        _log(f"  [dry-run] would move: {src}  ->  {dst}", log_fh, dry_run)
        return
    _log(f"  [move] {src}  ->  {dst}", log_fh, dry_run)
    shutil.move(str(src), str(dst))


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

def _derive_wiki_path(main_root: Path) -> Path:
    """Return the wiki path as a sibling of the container.

    The OLD layout's structural invariant is: wiki is a sibling of hub
    at the container level. This equals ``main_root.parent / "wiki"``
    regardless of whether the main_root dir is named ``hub`` (old) or
    ``<repo>`` (mid-migration).

    We do NOT use ``_paths.resolve_wiki_path`` here: that helper's sibling
    logic is calibrated for the NEW layout (``parent.name == "wts"`` →
    ``parent.parent / "wiki"``); on the OLD layout it falls through to
    prefix-form, returning ``<container>/hub.wiki/`` — a non-existent path.
    """
    return main_root.parent / "wiki"


def _check_in_flight(wiki_path: Path, dry_run: bool) -> None:
    """Halt if any wiki active task is not done or abandoned."""
    active_dir = wiki_path / "active"
    if not active_dir.exists():
        print(
            f"ERROR: {active_dir} does not exist.\n"
            f"  This suggests the clone is already migrated, or was not set up with mill.",
            file=sys.stderr,
        )
        sys.exit(1)

    in_flight: list[str] = []
    for slug_dir in sorted(active_dir.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        status_path = slug_dir / "status.md"
        if not status_path.exists():
            # No status.md — treat as in-flight (conservative).
            in_flight.append(f"{slug} (no status.md)")
            continue
        try:
            info = _status.read_status(status_path)
            phase = info.get("phase", "")
        except (ValueError, KeyError):
            in_flight.append(f"{slug} (unreadable status.md)")
            continue
        if phase not in {"done", "abandoned"}:
            in_flight.append(f"{slug} (phase={phase})")

    if in_flight:
        print(
            "ERROR: Cannot migrate -- the following tasks are still in flight:\n"
            + "\n".join(f"  {s}" for s in in_flight)
            + "\n\nMerge or abandon all in-flight tasks before running this migration.",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# rename-junctions step
# ---------------------------------------------------------------------------

def _step_rename_junctions(args: argparse.Namespace) -> None:
    """Migrate junction layout from .millhouse/wiki+.others+.active to .wiki+.portals."""
    from _paths import resolve_git_root, resolve_wiki_path, resolve_container_path, resolve_main_worktree_root
    dry_run: bool = args.dry_run

    git_root = resolve_git_root()
    wiki_path = resolve_wiki_path(git_root)
    container = resolve_container_path(git_root)
    hub_root = resolve_main_worktree_root(git_root)

    cfg = _config.load_config(hub_root, hub_root)

    log_fh = None
    if not dry_run:
        scratch = hub_root / ".scratch"
        scratch.mkdir(exist_ok=True)
        ts_log = _timestamp.now_utc_compact()
        log_path = scratch / f"migrate-rename-junctions-{ts_log}.log"
        log_fh = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
        _log(f"[rename-junctions] Writing log to {log_path}", log_fh, dry_run)
    else:
        _log("[rename-junctions] DRY-RUN mode -- no filesystem writes will be performed.", log_fh, dry_run)

    try:
        _run_step_rename_junctions(hub_root, wiki_path, container, cfg, log_fh, dry_run)
    finally:
        if log_fh is not None:
            log_fh.close()


def _run_step_rename_junctions(
    hub_root: Path,
    wiki_path: Path,
    container: Path,
    cfg: dict,
    log_fh,
    dry_run: bool,
) -> None:
    junctions_cfg = cfg.get("junctions", {})
    branch_prefix = cfg.get("spawn", {}).get("branch_prefix", "")
    home_md = wiki_path / "Home.md"
    home_tasks_list = _tasks_md.parse(home_md.read_text(encoding="utf-8")) if home_md.exists() else []
    active_wts = _spawn_core.discover_active_worktrees(container / "wts", home_tasks_list, branch_prefix)

    _log(f"[rename-junctions] Found {len(active_wts)} active task worktree(s).", log_fh, dry_run)

    updated = 0
    for wt_path, slug, title in active_wts:
        _log(f"\n--- Task worktree: {slug} ({wt_path}) ---", log_fh, dry_run)

        # Strip new-layout junctions (idempotent via _junction.remove).
        if not dry_run:
            _junction.strip_all_in_worktree(wt_path, junctions_cfg)
            for name in [".millhouse/wiki", ".others", ".active"]:
                _junction.remove(wt_path / name)
        else:
            _log(f"  [dry-run] would strip junctions in {wt_path}", log_fh, dry_run)

        # Remove old portals entry.
        old_portal = container / "portals" / slug
        if not dry_run:
            _junction.remove(old_portal)
        else:
            _log(f"  [dry-run] would remove portal: {old_portal}", log_fh, dry_run)

        # Create new portals entry pointing at wts/<slug>/_mill/.
        new_portal_target = wt_path / "_mill"
        new_portal_link = container / "portals" / slug
        if not dry_run:
            _junction.create(target=new_portal_target, link_path=new_portal_link)
            _log(f"  [rename-junctions] created portal: {new_portal_link} -> {new_portal_target}", log_fh, dry_run)
        else:
            _log(f"  [dry-run] would create portal: {new_portal_link} -> {new_portal_target}", log_fh, dry_run)

        # Recreate junctions in the task worktree.
        tokens = {
            "SLUG": slug,
            "WIKI_PATH": str(wiki_path),
            "CONTAINER_PATH": str(container),
            "HUB_PATH": str(hub_root),
            "CWD_PATH": str(wt_path),
            "REPO": hub_root.name,
        }
        if not dry_run:
            _setup.create_hub_links(wt_path, wiki_path, tokens)
        else:
            _log(f"  [dry-run] would recreate junctions in {wt_path}", log_fh, dry_run)

        # Move working state to task/.
        result = _subprocess_util.run(
            ["git", "-C", str(wt_path), "status", "--porcelain"]
        )
        if result.returncode != 0 or result.stdout.strip():
            _log(
                f"  [rename-junctions] skipping _mill/ move for {slug}: working tree dirty",
                log_fh, dry_run,
            )
        else:
            task_dir = wt_path / "task"
            if not dry_run:
                task_dir.mkdir(exist_ok=True)
            else:
                _log(f"  [dry-run] would mkdir {task_dir}", log_fh, dry_run)

            moved_any = False
            for src_name in ["status.md", "discussion.md", "plan", "reviews"]:
                src = wt_path / src_name
                dst = task_dir / src_name
                if src.exists():
                    if not dry_run:
                        _run(
                            ["git", "-C", str(wt_path), "mv", str(src), str(dst)],
                            log_fh, dry_run,
                        )
                        moved_any = True
                    else:
                        _log(f"  [dry-run] would git mv {src} -> {dst}", log_fh, dry_run)

            if moved_any and not dry_run:
                _run(
                    ["git", "-C", str(wt_path), "commit",
                     "-m", f"migrate: move working state to task/ for {slug}"],
                    log_fh, dry_run,
                )

        updated += 1

    # Hub worktree junctions.
    _log(f"\n--- Hub worktree: {hub_root} ---", log_fh, dry_run)
    if not dry_run:
        for name in [".millhouse/wiki", ".others", ".active"]:
            _junction.remove(hub_root / name)
        _junction.strip_all_in_worktree(hub_root, junctions_cfg)
    else:
        _log(f"  [dry-run] would strip old junctions from hub: {hub_root}", log_fh, dry_run)

    hub_tokens = {
        "WIKI_PATH": str(wiki_path),
        "CONTAINER_PATH": str(container),
        "HUB_PATH": str(hub_root),
        "CWD_PATH": str(hub_root),
        "REPO": hub_root.name,
    }
    if not dry_run:
        _setup.create_hub_links(hub_root, wiki_path, hub_tokens)
    else:
        _log(f"  [dry-run] would recreate hub junctions in {hub_root}", log_fh, dry_run)

    hub_gitignore = hub_root / ".gitignore"
    if not dry_run:
        _gitignore.upsert(hub_gitignore, _gitignore.GLOB_ENTRIES)
        _log(f"  [rename-junctions] updated .gitignore: {hub_gitignore}", log_fh, dry_run)
    else:
        _log(f"  [dry-run] would update .gitignore: {hub_gitignore}", log_fh, dry_run)

    print(
        f"\nRename-junctions migration complete. {updated} task worktree(s) updated."
        " Run /mill-setup to refresh hardlinks.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned operations and exit 0 without performing any writes.",
    )
    parser.add_argument(
        "--step",
        choices=["rename-junctions"],
        default=None,
        help="Which migration step to run. Omit to run the full legacy-layout migration.",
    )
    args = parser.parse_args()

    if args.step == "rename-junctions":
        _step_rename_junctions(args)
        return

    dry_run: bool = args.dry_run

    # --- Locate main worktree root from cwd ---
    from _paths import resolve_main_worktree_root, resolve_git_root
    git_root = resolve_git_root()
    main_root = resolve_main_worktree_root(git_root)

    container = main_root.parent  # e.g. c:/Code/millhouse/

    # --- Derive wiki path using OLD-layout invariant ---
    wiki_path = _derive_wiki_path(main_root)

    # --- Pre-flight: wiki/active/ must exist ---
    # (checked inside _check_in_flight, which will sys.exit if missing)
    _check_in_flight(wiki_path, dry_run)

    # --- Open log file (.scratch/ might not exist yet) ---
    log_fh = None
    if not dry_run:
        scratch = Path(".scratch")
        scratch.mkdir(exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_path = scratch / f"migrate-{ts}.log"
        log_fh = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
        print(f"[migrate] Writing log to {log_path}", file=sys.stderr)
    else:
        print("[migrate] DRY-RUN mode -- no filesystem writes will be performed.", file=sys.stderr)

    try:
        _run_migration(main_root, container, wiki_path, log_fh, dry_run)
    finally:
        if log_fh is not None:
            log_fh.close()


def _run_migration(
    main_root: Path,
    container: Path,
    wiki_path: Path,
    log_fh,
    dry_run: bool,
) -> None:
    hub_path = main_root  # still named 'hub' at migration time

    # --- Discover repo name from git remote origin ---
    result = _subprocess_util.run(
        ["git", "-C", str(hub_path), "remote", "get-url", "origin"]
    )
    if result.returncode != 0:
        print(
            f"ERROR: Could not determine repo name from 'git remote get-url origin': "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    origin_url = result.stdout.strip()
    repo_name = Path(origin_url.rstrip("/")).stem  # strip .git suffix via .stem
    _log(f"[migrate] Detected repo name: {repo_name!r} from origin {origin_url!r}", log_fh, dry_run)

    wts_dir = container / "wts"
    worktrees_dir = container / "worktrees"
    new_main_root = wts_dir / repo_name

    _log("", log_fh, dry_run)
    _log("=== Planned operations ===", log_fh, dry_run)
    _log(f"  container:    {container}", log_fh, dry_run)
    _log(f"  old hub:      {hub_path}", log_fh, dry_run)
    _log(f"  new hub:      {new_main_root}", log_fh, dry_run)
    _log(f"  wts dir:      {wts_dir}", log_fh, dry_run)
    _log(f"  wiki path:    {wiki_path}", log_fh, dry_run)
    _log("", log_fh, dry_run)

    # -----------------------------------------------------------------------
    # Step 1: mkdir <container>/wts (idempotent)
    # -----------------------------------------------------------------------
    _log("--- Step 1: Create wts/ directory ---", log_fh, dry_run)
    _mkdir(wts_dir, log_fh, dry_run)

    # -----------------------------------------------------------------------
    # Step 2: Move child worktrees from worktrees/<slug> to wts/<slug>
    # -----------------------------------------------------------------------
    _log("--- Step 2: Move child worktrees ---", log_fh, dry_run)
    child_worktrees: list[Path] = []
    if worktrees_dir.exists():
        child_worktrees = [p for p in sorted(worktrees_dir.iterdir()) if p.is_dir()]

    if child_worktrees:
        for old_wt in child_worktrees:
            slug = old_wt.name
            new_wt = wts_dir / slug
            _log(f"  Moving child worktree: {old_wt}  ->  {new_wt}", log_fh, dry_run)
            _run(
                ["git", "-C", str(hub_path), "worktree", "move", str(old_wt), str(new_wt)],
                log_fh, dry_run,
            )
    else:
        _log("  (no child worktrees to move)", log_fh, dry_run)

    # -----------------------------------------------------------------------
    # Step 3: Move main worktree hub → wts/<repo>; then git worktree repair
    # -----------------------------------------------------------------------
    _log("--- Step 3: Move main worktree ---", log_fh, dry_run)
    _log(f"  Moving main worktree: {hub_path}  ->  {new_main_root}", log_fh, dry_run)
    _shutil_move(hub_path, new_main_root, log_fh, dry_run)
    _log("  Running git worktree repair ...", log_fh, dry_run)
    _run(
        ["git", "-C", str(new_main_root), "worktree", "repair"],
        log_fh, dry_run,
    )

    # -----------------------------------------------------------------------
    # Step 4: Remove now-empty worktrees/ directory
    # -----------------------------------------------------------------------
    _log("--- Step 4: Remove worktrees/ directory ---", log_fh, dry_run)
    if worktrees_dir.exists() or dry_run:
        _rmdir(worktrees_dir, log_fh, dry_run)
    else:
        _log("  (worktrees/ did not exist, skipping)", log_fh, dry_run)

    # -----------------------------------------------------------------------
    # Step 5: Create portals/ directory and per-worktree junction entries
    # -----------------------------------------------------------------------
    _log("--- Step 5: Create portals/ and junction entries ---", log_fh, dry_run)
    portals_dir = container / "portals"
    _mkdir(portals_dir, log_fh, dry_run)

    # All subdirectories of wts/ get a portal entry (including the main worktree).
    wts_entries: list[Path] = []
    if dry_run:
        # In dry-run, wts/ may not exist yet on disk; enumerate from what we know.
        wts_entries = [wts_dir / c.name for c in child_worktrees]
        wts_entries.append(new_main_root)
    else:
        if wts_dir.exists():
            wts_entries = sorted(wts_dir.iterdir())

    for wt_path in wts_entries:
        wt_name = wt_path.name
        link_path = portals_dir / wt_name
        target = wts_dir / wt_name

        if dry_run:
            _log(f"  [dry-run] would create portal: {link_path}  ->  {target}", log_fh, dry_run)
            continue

        # Explicit pre-check: skip already-correct, halt on wrong target.
        if os.path.lexists(str(link_path)):
            existing_target = str(Path(os.path.realpath(str(link_path))))
            desired_target = str(target.resolve())
            if existing_target == desired_target:
                _log(f"  portal already correct: {link_path}", log_fh, dry_run)
            else:
                print(
                    f"ERROR: Portal {link_path} already exists but points to "
                    f"{existing_target!r} instead of {desired_target!r}.\n"
                    f"  Remove the wrong junction manually before re-running.",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            _log(f"  Creating portal: {link_path}  ->  {target}", log_fh, dry_run)
            _junction.create(target=target, link_path=link_path)

    # -----------------------------------------------------------------------
    # Step 6: Banner — instruct operator to run mill-setup
    # -----------------------------------------------------------------------
    hub_display = new_main_root if not dry_run else new_main_root
    print("", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("Migration complete.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Next steps (per discussion.md operator constraint):", file=sys.stderr)
    print(f"  1. cd {hub_display}", file=sys.stderr)
    print("  2. Run /mill-setup  (the slash command in Claude Code, NOT a Python", file=sys.stderr)
    print("     invocation). This refreshes junctions, hardlinks, and the", file=sys.stderr)
    print("     gitignore for the new layout.", file=sys.stderr)
    print("", file=sys.stderr)
    print("IMPORTANT: Do NOT run mill-setup before this migration is complete.", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    if log_fh is not None:
        print("", file=log_fh)
        print("Migration complete.", file=log_fh)
        print(f"Next: cd {hub_display} and run /mill-setup", file=log_fh)


if __name__ == "__main__":
    main()
