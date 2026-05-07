"""
mill-cleanup — sweeper: reconcile hub git worktrees, wiki active/<slug>/ dirs, and Home.md markers based on status.md phase.

Runs from the hub. Pass --apply to execute removals; default is dry-run.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

import _active
import _inplace
import _junction
import _paths
import _sidebar
import _spawn_core
import _status
import _subprocess_util
import _tasks_md
import _wiki
import _worktree
from _config import load_config as _load_config


@dataclass(frozen=True)
class SlugRecord:
    slug: str
    worktree_path: Path | None
    branch: str | None
    wiki_active_dir: Path | None
    home_marker: str | None


@dataclass(frozen=True)
class CleanupPlan:
    to_remove_done: list[SlugRecord]
    to_remove_abandoned: list[SlugRecord]
    to_reset_home: list[str]
    to_report: list[str]


# Returns None if status.md is missing or phase: is unreadable.
def _read_phase(status_path: Path) -> str | None:
    _YAML_FENCE = "```yaml"
    try:
        text = status_path.read_text(encoding="utf-8")
        start = text.index(_YAML_FENCE) + len(_YAML_FENCE)
        end = text.index("```", start)
        cfg = yaml.safe_load(text[start:end])
        return cfg.get("phase")
    except Exception:
        return None


def build_plan(
    active_worktrees: list[Path],
    home_tasks: list[_tasks_md.Task],
    wiki_path: Path,
    hub_root: Path,
    *,
    container_path: Path | None = None,
) -> CleanupPlan:
    """
    Build a CleanupPlan from current repo state.

    No git or wiki writes (read-only git queries are permitted); reads
    status.md files via _read_phase (file I/O). Each path in
    ``active_worktrees`` is a worktree root discovered via
    ``_spawn_core.discover_active_worktrees``.

    Args:
        active_worktrees: List of worktree root paths, each carrying a
            valid ``.millhouse/active.slug.md`` marker.
        home_tasks: Tasks parsed from wiki ``Home.md``.
        wiki_path: Path to the wiki clone root.
        hub_root: Absolute path to the hub git checkout.
        container_path: When provided, scans ``<container_path>/wts/`` for
            worktree directories that have no active marker (orphan worktrees)
            and adds them to ``to_report``. Pass the result of
            ``_paths.resolve_container_path(hub_root)`` from the caller.
            When ``None``, orphan worktree detection is skipped.
    """
    marker_by_slug: dict[str, str | None] = {t.slug: t.phase for t in home_tasks}
    active_slugs: set[str] = set()

    to_remove_done: list[SlugRecord] = []
    to_remove_abandoned: list[SlugRecord] = []
    to_reset_home: list[str] = []
    to_report: list[str] = []

    _LIVE_PHASES = {
        "discussing", "discussed", "planning", "planned",
        "implementing", "reviewing", "fixing", "blocked",
    }

    for wt_path in active_worktrees:
        hub_subpath = "."
        stub_path = wt_path / ".millhouse" / "config.local.yaml"
        if stub_path.exists():
            try:
                stub_data = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or {}
                hub_subpath = stub_data.get("hub_relative_path", ".")
            except Exception:  # noqa: BLE001
                hub_subpath = "."
        hub_mill_dir = (
            wt_path / ".millhouse" if hub_subpath == "."
            else wt_path / hub_subpath / ".millhouse"
        )
        try:
            marker_data = _active.read_all(hub_mill_dir)
        except _active.ActiveError:
            continue

        slug = marker_data.get("slug", "")
        branch = marker_data.get("branch")
        if not slug:
            continue

        active_slugs.add(slug)
        phase = _read_phase(wt_path / "status.md")
        if phase is None:
            to_report.append(
                f"{slug} — status.md unreadable, skipping (inspect manually)"
            )
            continue

        wiki_active_dir_candidate = wiki_path / "active" / slug
        wiki_active_dir = wiki_active_dir_candidate if wiki_active_dir_candidate.is_dir() else None

        record = SlugRecord(slug, wt_path, branch, wiki_active_dir, marker_by_slug.get(slug))

        if phase == "done":
            parent_branch = _status.read_parent_branch(wt_path / "status.md")
            if parent_branch and record.branch:
                result = _subprocess_util.run(
                    ["git", "-C", str(hub_root), "log", "--oneline",
                     f"{parent_branch}..{record.branch}"]
                )
                if result.returncode == 0 and result.stdout.strip():
                    to_report.append(
                        f"{slug} — phase=done but has unmerged commits relative to "
                        f"{parent_branch!r}; run mill-merge first"
                    )
                    continue
            to_remove_done.append(record)
        elif phase == "abandoned":
            if record.home_marker == "active":
                to_remove_abandoned.append(record)
                to_reset_home.append(slug)
            else:
                to_report.append(
                    f"{slug} — phase=abandoned but Home.md marker is "
                    f"{record.home_marker!r}, not [active]; skipping (inspect manually)"
                )
        elif phase in _LIVE_PHASES:
            pass
        else:
            to_report.append(f"{slug} — unknown phase {phase!r}, skipping")

    # Orphan worktree detection: wts/ dirs without active markers.
    if container_path is not None:
        wts_dir = container_path / "wts"
        if wts_dir.is_dir():
            for entry in wts_dir.iterdir():
                if not entry.is_dir():
                    continue
                # Skip the hub itself (resolved to avoid symlink confusion).
                if entry.resolve() == hub_root.resolve():
                    continue
                if entry.name not in active_slugs:
                    to_report.append(
                        f"orphan worktree: {entry} (no active marker;"
                        f" run 'git worktree remove --force {entry}' to clean up)"
                    )

    # Orphan Home.md marker: [active] slug with no active worktree.
    for task in home_tasks:
        if task.phase == "active" and task.slug not in active_slugs:
            to_report.append(
                f"orphan Home.md marker: {task.slug} is [active] but has no "
                f"active worktree"
            )

    # Active worktree with no Home.md entry.
    for slug in active_slugs:
        if slug not in marker_by_slug:
            to_report.append(
                f"orphan active worktree: {slug} has active marker but no Home.md entry"
            )

    return CleanupPlan(to_remove_done, to_remove_abandoned, to_reset_home, to_report)


def _print_plan(plan: CleanupPlan) -> None:
    if not any([plan.to_remove_done, plan.to_remove_abandoned, plan.to_report]):
        print("Nothing to do.")
        return
    for r in plan.to_remove_done:
        print(
            f"REMOVE (done):      {r.slug}  "
            f"[worktree={r.worktree_path}, branch={r.branch}, wiki_active_dir={r.wiki_active_dir}]"
        )
    for r in plan.to_remove_abandoned:
        print(
            f"REMOVE (abandoned): {r.slug}  "
            f"[worktree={r.worktree_path}, branch={r.branch}, wiki_active_dir={r.wiki_active_dir}]"
            f"  \u2192 Home.md marker reset to unclaimed"
        )
    for line in plan.to_report:
        print(f"REPORT: {line}")


def _resolve_inplace_mode(
    record: "SlugRecord",
    hub_root: Path,
    cfg: dict,
) -> tuple[str, str]:
    """Determine whether a sweep record should use in-place or worktree cleanup.

    Reads the hub's ``.millhouse/active.slug.md`` marker once and delegates
    to ``_inplace.is_inplace``. When the stale-worktree edge applies (branch
    matches AND a worktree dir exists), prompts the user and returns their
    choice. The resolved task branch is returned alongside the mode so
    callers can pass it directly to ``_apply_inplace_record`` without a
    second read of the marker.

    Args:
        record: The SlugRecord being evaluated.
        hub_root: Absolute path to the hub git checkout.
        cfg: Deep-merged config dict.

    Returns:
        A ``(mode, task_branch)`` tuple where ``mode`` is one of:
        - ``"inplace"`` — skip worktree remove, delete branch only.
        - ``"worktree"`` — standard worktree remove flow.
        - ``"abort"`` — user aborted; caller should skip this record.
        ``task_branch`` is the branch name from the active marker when
        ``mode == "inplace"``, and ``""`` otherwise.
    """
    try:
        active_data = _active.read_all(hub_root / ".millhouse")
    except _active.ActiveError:
        return ("worktree", "")

    if active_data.get("slug") != record.slug:
        return ("worktree", "")

    task_branch = active_data.get("branch", "")

    # Stale-worktree edge: branch matches current HEAD AND worktree dir exists.
    recorded_branch = task_branch
    result = _subprocess_util.run(
        ["git", "-C", str(hub_root), "rev-parse", "--abbrev-ref", "HEAD"]
    )
    current_branch = result.stdout.strip() if result.returncode == 0 else ""

    worktrees_dir = _paths.resolve_worktrees_dir(cfg, hub_root)
    worktree_dir = worktrees_dir / record.slug

    if current_branch == recorded_branch and worktree_dir.is_dir():
        choice = _inplace.prompt_stale_worktree(record.slug, worktree_dir)
        if choice == "inplace":
            return ("inplace", task_branch)
        if choice == "worktree":
            return ("worktree", "")
        return ("abort", "")

    if _inplace.is_inplace(active_data, hub_root, cfg):
        return ("inplace", task_branch)

    return ("worktree", "")


def _apply_inplace_record(
    record: SlugRecord,
    hub_root: Path,
    task_branch: str = "",
) -> None:
    """Apply cleanup for a single in-place (no separate worktree) record.

    Reads the parent branch from ``status.md``, checks out the parent
    branch so we are not deleting the currently-checked-out branch,
    deletes the task branch (``-d`` for done, ``-D`` for abandoned),
    removes the ``.active`` junction at ``hub_root / ".active"``, and
    removes the ``active.slug.md`` marker. This function does NOT remove
    the wiki active dir — ``apply_plan`` handles that uniformly.

    Args:
        record: The SlugRecord for the in-place task being cleaned.
        hub_root: Absolute path to the hub git checkout.
        task_branch: The task branch name resolved by ``_resolve_inplace_mode``
            from the active marker. Avoids a second read of the marker file.

    """
    # Read parent branch from status.md so we can check out safely.
    if record.worktree_path is not None:
        parent_branch = _status.read_parent_branch(record.worktree_path / "status.md")
    else:
        parent_branch = None

    if not parent_branch:
        print(
            f"[cleanup] {record.slug}: cannot determine parent branch from status.md; "
            "aborting in-place branch deletion. Remove the branch manually.",
            file=sys.stderr,
        )
        return

    # Check out the parent branch before deleting the task branch.
    # This prevents git from refusing to delete the currently-checked-out branch.
    result = _subprocess_util.run(
        ["git", "-C", str(hub_root), "checkout", parent_branch]
    )
    if result.returncode != 0:
        print(
            f"[cleanup] {record.slug}: checkout {parent_branch!r} failed: "
            f"{result.stderr.strip()!r}; aborting branch deletion.",
            file=sys.stderr,
        )
        return

    # Determine deletion flag: done tasks get -d (safe); abandoned get -D (force).
    # Phase is re-read from the worktree's status.md; fall back to -D when absent.
    if record.worktree_path is not None:
        phase = _read_phase(record.worktree_path / "status.md")
        delete_flag = "-d" if phase == "done" else "-D"
    else:
        delete_flag = "-D"

    if task_branch:
        result = _subprocess_util.run(
            ["git", "-C", str(hub_root), "branch", delete_flag, task_branch]
        )
        if result.returncode != 0:
            print(
                f"[cleanup] branch {delete_flag} {task_branch!r} failed "
                f"(may already be gone): {result.stderr.strip()!r}",
                file=sys.stderr,
            )
    else:
        print(
            f"[cleanup] {record.slug}: no branch name in active marker; "
            "skipping branch deletion.",
            file=sys.stderr,
        )

    # Remove the .active junction at the hub root.
    active_junction = hub_root / ".active"
    _junction.remove(active_junction)
    print(f"[cleanup] removed .active junction: {active_junction}", file=sys.stderr)

    # Remove the active marker file.
    marker_path = hub_root / ".millhouse" / "active.slug.md"
    if marker_path.exists():
        marker_path.unlink()
        print(f"[cleanup] removed active marker: {marker_path}", file=sys.stderr)

    # Remove the portal entry for this task.
    container_path = _paths.resolve_container_path(hub_root)
    _junction.remove(container_path / "portals" / record.slug)
    print(f"[cleanup] removed portal entry: {container_path / 'portals' / record.slug}", file=sys.stderr)


def _apply_worktree_record(
    record: SlugRecord,
    hub_root: Path,
    wiki_path: Path,
    junctions_cfg: dict[str, str],
) -> None:
    """Apply cleanup for a single record that has a separate git worktree.

    Removes per-slug junctions inside the worktree, removes the worktree
    itself, and deletes the branch.

    Args:
        record: The SlugRecord for the task being cleaned.
        hub_root: Absolute path to the hub git checkout.
        wiki_path: Absolute path to the wiki clone.
        junctions_cfg: Junction template map from the wiki config.
    """
    if record.worktree_path is not None:
        # remove_safe strips all junctions before removal and falls back
        # to shutil.rmtree on long-path failures (junctions-stripped state
        # makes that fallback safe). See GitHub issue #100.
        _worktree.remove_safe(record.worktree_path, cwd=hub_root, junctions_cfg=junctions_cfg)
        if record.branch is not None:
            result = _subprocess_util.run(
                ["git", "-C", str(hub_root), "branch", "-D", record.branch]
            )
            if result.returncode != 0:
                print(
                    f"[cleanup] branch -D {record.branch!r} failed (may already be gone): "
                    f"{result.stderr.strip()!r}",
                    file=sys.stderr,
                )

    # Remove the portal entry for this task.
    container_path = _paths.resolve_container_path(hub_root)
    _junction.remove(container_path / "portals" / record.slug)
    print(f"[cleanup] removed portal entry: {container_path / 'portals' / record.slug}", file=sys.stderr)


def apply_plan(
    plan: CleanupPlan,
    wiki_path: Path,
    hub_root: Path,
    junctions_cfg: dict[str, str],
    cfg: dict | None = None,
) -> None:
    if cfg is None:
        cfg = {}
    wiki_relative_paths: list[str] = []

    for record in plan.to_remove_done + plan.to_remove_abandoned:
        # Determine whether this is an in-place task (no separate worktree dir).
        mode, task_branch = _resolve_inplace_mode(record, hub_root, cfg)
        if mode == "abort":
            print(
                f"[cleanup] skipping {record.slug} — user aborted stale-worktree prompt.",
                file=sys.stderr,
            )
            continue

        if mode == "inplace":
            _apply_inplace_record(record, hub_root, task_branch)
        else:
            _apply_worktree_record(record, hub_root, wiki_path, junctions_cfg)

        if record.wiki_active_dir is not None and record.wiki_active_dir.is_dir():
            shutil.rmtree(record.wiki_active_dir)
            wiki_relative_paths.append(f"active/{record.slug}")

    if plan.to_reset_home:
        home_text = (wiki_path / "Home.md").read_text("utf-8")
        for slug in plan.to_reset_home:
            home_text = _tasks_md.set_phase(home_text, slug, None)
        (wiki_path / "Home.md").write_text(home_text, "utf-8")
        wiki_relative_paths.append("Home.md")

    if wiki_relative_paths:
        _sidebar.regenerate(wiki_path)
        wiki_relative_paths.append("_Sidebar.md")
        _wiki.write_commit_push(
            wiki_path,
            wiki_relative_paths,
            f"chore: cleanup — {len(plan.to_remove_done)} done, "
            f"{len(plan.to_remove_abandoned)} abandoned",
            slug="mill-cleanup",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep done/abandoned task artefacts.")
    parser.add_argument("--apply", action="store_true", help="Execute removals (default: dry-run).")
    args = parser.parse_args()

    if (Path.cwd() / ".millhouse" / "active.slug.md").exists():
        sys.exit("Error: mill-cleanup must run from the hub, not from a worktree.")

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)
    container_path = _paths.resolve_container_path(git_root)

    _wiki.sync_pull(wiki_path, slug="mill-cleanup")

    active_wt_list = _spawn_core.discover_active_worktrees(container_path / "wts")
    active_worktrees = [path for path, _slug, _title in active_wt_list]

    home_text = (wiki_path / "Home.md").read_text("utf-8")
    home_tasks = _tasks_md.parse(home_text)
    junctions_cfg = _wiki.read_junctions(wiki_path)

    cfg = _load_config(wiki_path, git_root)
    plan = build_plan(
        active_worktrees, home_tasks, wiki_path,
        hub_root=git_root, container_path=container_path,
    )
    _print_plan(plan)

    if not args.apply:
        print("\nDry-run. Pass --apply to execute.")
        sys.exit(0)

    with _wiki.wiki_lock(wiki_path, "mill-cleanup"):
        apply_plan(plan, wiki_path, git_root, junctions_cfg, cfg=cfg)

    print(
        f"\nDone: {len(plan.to_remove_done)} done, "
        f"{len(plan.to_remove_abandoned)} abandoned removed. "
        f"{len(plan.to_report)} orphans/unreadable reported."
    )


if __name__ == "__main__":
    main()
