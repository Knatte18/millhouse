"""
mill-cleanup — sweeper: reconcile hub git worktrees, wiki active/<slug>/ dirs, and Home.md markers based on status.md phase.

Runs from the hub. Pass --apply to execute removals; default is dry-run.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

import _inplace
import _junction
import _marker
import _paths
import _pr_state
import _spawn_core
import _status
import _subprocess_util
import _worktree
from wiki import _client as wiki
from _config import load_config as _load_config


@dataclass(frozen=True)
class SlugRecord:
    slug: str
    worktree_path: Path | None
    branch: str | None
    home_marker: str | None


@dataclass(frozen=True)
class CleanupPlan:
    to_remove_done: list[SlugRecord]
    to_remove_abandoned: list[SlugRecord]
    to_reset_home: list[str]
    to_report: list[str]
    to_reap_pr: list[SlugRecord] = field(default_factory=list)
    orphan_portals: list[Path] = field(default_factory=list)
    # Slugs whose Home.md marker is exactly "active" but have no worktree
    # on disk, no local branch, and no portal junction -- safe to auto-reset
    # to unclaimed.  "ready-to-merge" and "pr-pending" are live PR states
    # and are never auto-reset.
    to_reset_unclaimed: list[str] = field(default_factory=list)


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


def _scan_orphan_portals(portals_dir: Path, active_slugs: set[str]) -> list[Path]:
    if not portals_dir.is_dir():
        return []
    stale: list[Path] = []
    for entry in portals_dir.iterdir():
        # Two-condition oracle: slug missing from Home.md OR target gone.
        if entry.name not in active_slugs or not entry.exists():
            stale.append(entry)
    return stale


def build_plan(
    active_worktrees: list[Path],
    home_tasks: list[dict],
    wiki_path: Path,
    hub_root: Path,
    *,
    container_path: Path | None = None,
    branch_prefix: str = "",
) -> CleanupPlan:
    """
    Build a CleanupPlan from current repo state.

    No git or wiki writes (read-only git queries are permitted); reads
    status.md files via _read_phase (file I/O). Each path in
    ``active_worktrees`` is a worktree root discovered via
    ``_spawn_core.discover_active_worktrees``.

    Args:
        active_worktrees: List of worktree root paths, each on a task
            branch detected via ``_spawn_core.discover_active_worktrees``.
        home_tasks: Tasks parsed from wiki ``Home.md``.
        wiki_path: Path to the wiki clone root.
        hub_root: Absolute path to the hub git checkout.
        container_path: When provided, scans ``<container_path>/wts/`` for
            worktree directories that have no active marker (orphan worktrees)
            and adds them to ``to_report``. Pass the result of
            ``_paths.resolve_container_path(hub_root)`` from the caller.
            When ``None``, orphan worktree detection is skipped.
    """
    marker_by_slug: dict[str, str | None] = {t["slug"]: t.get("status") for t in home_tasks}
    active_slugs: set[str] = set()

    to_remove_done: list[SlugRecord] = []
    to_remove_abandoned: list[SlugRecord] = []
    to_reset_home: list[str] = []
    to_report: list[str] = []
    to_reap_pr: list[SlugRecord] = []
    to_reset_unclaimed: list[str] = []

    _LIVE_PHASES = {
        "discussing", "discussed", "planning", "planned",
        "implementing", "reviewing", "fixing", "blocked",
    }

    for wt_path in active_worktrees:
        branch_proc = _subprocess_util.run(
            ["git", "-C", str(wt_path), "branch", "--show-current"]
        )
        if branch_proc.returncode != 0 or not branch_proc.stdout.strip():
            continue
        branch = branch_proc.stdout.strip()
        if branch_prefix and not branch.startswith(branch_prefix):
            continue
        slug = branch.removeprefix(branch_prefix) if branch_prefix else branch
        if slug not in marker_by_slug:
            continue

        active_slugs.add(slug)
        phase = _read_phase(_paths.resolve_task_path(wt_path, "_mill/status.md"))
        if phase is None:
            # status.md absent -- mill-merge deletes _mill/ before squash merge.
            # Fall back to Home.md marker: if [done], proceed to archive-tag check.
            if marker_by_slug.get(slug) == "done":
                phase = "done"
            else:
                to_report.append(
                    f"{slug} -- status.md unreadable, skipping (inspect manually)"
                )
                continue

        record = SlugRecord(slug, wt_path, branch, marker_by_slug.get(slug))

        if phase == "done":
            home_marker = marker_by_slug.get(slug)
            if home_marker == "done":
                result = _subprocess_util.run(
                    ["git", "-C", str(hub_root), "tag", "-l", f"archive/{slug}"]
                )
                if result.returncode == 0 and result.stdout.strip():
                    to_remove_done.append(record)
                else:
                    to_report.append(
                        f"{slug} -- Home.md=[done] but archive tag archive/{slug} absent;"
                        f" run mill-merge first"
                    )
            elif home_marker == "ready-to-merge":
                pass
            else:
                to_report.append(
                    f"{slug} -- status.md phase=done but Home.md marker is {home_marker!r};"
                    f" inspect manually"
                )
        elif phase == "abandoned":
            if record.home_marker == "active":
                to_remove_abandoned.append(record)
                to_reset_home.append(slug)
            else:
                to_report.append(
                    f"{slug} -- phase=abandoned but Home.md marker is "
                    f"{record.home_marker!r}, not [active]; skipping (inspect manually)"
                )
        elif phase == "pr-pending":
            to_reap_pr.append(record)
        elif phase in _LIVE_PHASES:
            pass
        else:
            to_report.append(f"{slug} -- unknown phase {phase!r}, skipping")

    # Orphan worktree detection: git registry worktrees without active markers.
    # Use git worktree list --porcelain instead of raw directory scan.
    # Only report wts/ entries that ARE registered git worktrees AND lack an
    # active marker. Plain directories (not in the git registry) are silently
    # ignored. CRITICAL: cross-reference Home.md before recommending deletion.
    # A slug that is [active]/[ready-to-merge]/[pr-pending] is IN USE -- the
    # .active junction may be stale or pointing elsewhere, but the worktree is
    # live. Recommending 'git worktree remove --force' on a live worktree
    # partially succeeds on Windows (admin dir deleted, working tree files
    # truncated while session holds others open), corrupting the user's session.
    _IN_USE_MARKERS = {"active", "ready-to-merge", "pr-pending"}
    if container_path is not None:
        registered_worktrees = []
        try:
            registered_worktrees = _worktree.list_worktrees(hub_root)
        except Exception:
            # Silent failure: list_worktrees unavailable, fall back to empty list
            pass
        registered_paths: set[Path] = set()
        for wt_entry in registered_worktrees:
            try:
                wt_path = Path(wt_entry["path"]).resolve()
                if wt_path != hub_root.resolve():
                    registered_paths.add(wt_path)
            except (OSError, ValueError):
                pass

        wts_dir = container_path / "wts"
        if wts_dir.is_dir():
            for entry in wts_dir.iterdir():
                if not entry.is_dir():
                    continue
                # Skip the hub itself (resolved to avoid symlink confusion).
                if entry.resolve() == hub_root.resolve():
                    continue
                # Only report if this dir IS a registered git worktree.
                if entry.resolve() not in registered_paths:
                    continue
                if entry.name not in active_slugs:
                    home_marker = marker_by_slug.get(entry.name)
                    if home_marker in _IN_USE_MARKERS:
                        to_report.append(
                            f"WARNING in-use worktree {entry} -- .active junction"
                            f" does not point here but Home.md marks slug"
                            f" {entry.name!r} as [{home_marker}]. DO NOT delete;"
                            f" reconcile state manually (likely repair the .active"
                            f" junction or run mill-claim)."
                        )
                    else:
                        to_report.append(
                            f"orphan worktree: {entry} (no active marker;"
                            f" run 'git worktree remove --force {entry}' to clean up)"
                        )

    orphan_portals: list[Path] = []
    if container_path is not None:
        orphan_portals = _scan_orphan_portals(
            container_path / "portals", active_slugs
        )

    # Orphan Home.md marker: [active]/[ready-to-merge]/[pr-pending] slug with no
    # worktree on disk. active_slugs is keyed off the .active junction, so a
    # slug whose junction has drifted but whose worktree dir still exists is
    # NOT truly orphaned -- only the junction is. Cross-reference container/wts/
    # to avoid false positives that would mislead callers into "fixing" a
    # healthy worktree.
    wts_slugs_on_disk: set[str] = set()
    if container_path is not None:
        wts_dir = container_path / "wts"
        if wts_dir.is_dir():
            for entry in wts_dir.iterdir():
                if not entry.is_dir():
                    continue
                if entry.resolve() == hub_root.resolve():
                    continue
                wts_slugs_on_disk.add(entry.name)

    for task in home_tasks:
        marker = task.get("status")
        if marker in ("active", "ready-to-merge", "pr-pending") and task["slug"] not in active_slugs:
            if task["slug"] in wts_slugs_on_disk:
                # Already reported under the in-use-worktree warning above.
                continue
            # For the narrow safe case of a plain "active" marker: attempt
            # automatic reconciliation to unclaimed if no worktree, no local
            # branch, and no portal junction exist.  "ready-to-merge" and
            # "pr-pending" are live PR states and must never be auto-reset.
            if marker == "active":
                slug_for_check = task["slug"]
                # Probe for a local branch: an existing branch means the task
                # is partially set up and should not be silently wiped.
                branch_name = f"{branch_prefix}{slug_for_check}" if branch_prefix else slug_for_check
                branch_check = _subprocess_util.run(
                    ["git", "-C", str(hub_root), "branch", "--list", branch_name]
                )
                has_local_branch = (
                    branch_check.returncode == 0 and branch_check.stdout.strip() != ""
                )
                # Probe for a portal junction: reuse the existing portals enumeration.
                has_portal = (
                    container_path is not None
                    and (container_path / "portals" / slug_for_check).exists()
                )
                if not has_local_branch and not has_portal:
                    to_reset_unclaimed.append(slug_for_check)
                    continue
            to_report.append(
                f"orphan Home.md marker: {task['slug']} is [{marker}] but has no "
                f"active worktree"
            )

    # Active worktree with no Home.md entry.
    for slug in active_slugs:
        if slug not in marker_by_slug:
            to_report.append(
                f"orphan active worktree: {slug} has active marker but no Home.md entry"
            )

    return CleanupPlan(
        to_remove_done,
        to_remove_abandoned,
        to_reset_home,
        to_report,
        to_reap_pr=to_reap_pr,
        orphan_portals=orphan_portals,
        to_reset_unclaimed=to_reset_unclaimed,
    )


def _print_plan(plan: CleanupPlan) -> None:
    if not any([plan.to_remove_done, plan.to_remove_abandoned, plan.to_reap_pr, plan.to_report, plan.orphan_portals, plan.to_reset_unclaimed]):
        print("Nothing to do.")
        return
    for r in plan.to_remove_done:
        print(
            f"REMOVE (done):      {r.slug}  "
            f"[worktree={r.worktree_path}, branch={r.branch}]"
        )
    for r in plan.to_remove_abandoned:
        print(
            f"REMOVE (abandoned): {r.slug}  "
            f"[worktree={r.worktree_path}, branch={r.branch}]"
            f"  -> Home.md marker reset to unclaimed"
        )
    for r in plan.to_reap_pr:
        print(f"REAP-PR:           {r.slug}  [worktree={r.worktree_path}, branch={r.branch}]")
    for slug in plan.to_reset_unclaimed:
        print(f"RECONCILE:         {slug}  [active marker -> unclaimed (no worktree/branch/portal)]")
    for line in plan.to_report:
        print(f"REPORT: {line}")
    for p in plan.orphan_portals:
        print(f"ORPHAN-PORTAL:     {p.name}  [target gone or not in Home.md]")


def _resolve_inplace_mode(
    record: "SlugRecord",
    hub_root: Path,
    wiki_path: Path,
    cfg: dict,
) -> tuple[str, str]:
    """Determine whether a sweep record should use in-place or worktree cleanup.

    Derives the hub's current slug via ``_marker.slug_from_branch`` and
    delegates to ``_inplace.is_inplace``. When the stale-worktree edge
    applies (branch matches AND a worktree dir exists), prompts the user
    and returns their choice. The resolved task branch is returned alongside
    the mode so callers can pass it directly to ``_apply_inplace_record``
    without a second branch lookup.

    Args:
        record: The SlugRecord being evaluated.
        hub_root: Absolute path to the hub git checkout.
        cfg: Deep-merged config dict.

    Returns:
        A ``(mode, task_branch)`` tuple where ``mode`` is one of:
        - ``"inplace"`` — skip worktree remove, delete branch only.
        - ``"worktree"`` — standard worktree remove flow.
        - ``"abort"`` — user aborted; caller should skip this record.
        ``task_branch`` is the current branch name when
        ``mode == "inplace"``, and ``""`` otherwise.
    """
    try:
        slug_for_record = _marker.slug_from_branch(hub_root, wiki_path, cfg)
    except _marker.MarkerError:
        return ("worktree", "")

    if slug_for_record != record.slug:
        return ("worktree", "")

    result_branch = _subprocess_util.run(
        ["git", "-C", str(hub_root), "branch", "--show-current"]
    )
    task_branch = result_branch.stdout.strip() if result_branch.returncode == 0 else ""

    # Stale-worktree edge: hub is on task branch AND worktree dir exists.
    worktrees_dir = _paths.resolve_worktrees_dir(cfg, hub_root)
    worktree_dir = worktrees_dir / record.slug

    if worktree_dir.is_dir():
        choice = _inplace.prompt_stale_worktree(record.slug, worktree_dir)
        if choice == "inplace":
            return ("inplace", task_branch)
        if choice == "worktree":
            return ("worktree", "")
        return ("abort", "")

    if _inplace.is_inplace(record.slug, hub_root, cfg):
        return ("inplace", task_branch)

    return ("worktree", "")


def _delete_remote_branch(hub_root: Path, branch: str) -> None:
    """
    Delete the remote origin branch for a task, tolerating an already-absent ref.

    Attempts `git push origin --delete <branch>` from `hub_root`. A non-zero
    exit whose stderr contains "remote ref does not exist" is treated as success
    (idempotent teardown -- the branch may never have been pushed, or was already
    deleted by an earlier abandon/cleanup run). Any other non-zero exit is printed
    to stderr as a non-fatal warning so the rest of the teardown proceeds.

    Args:
        hub_root: Absolute path to the hub git checkout used as the git -C target.
        branch: The remote branch name to delete (e.g. "hanf/my-task").
    """
    result = _subprocess_util.run(
        ["git", "-C", str(hub_root), "push", "origin", "--delete", branch]
    )
    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        # "remote ref does not exist" or "unable to delete" signals the branch was
        # never pushed or was already cleaned; both cases are acceptable -- nothing
        # to remove.
        if "remote ref does not exist" not in stderr_lower and "unable to delete" not in stderr_lower:
            print(
                f"[cleanup] push origin --delete {branch!r} failed (non-fatal): "
                f"{result.stderr.strip()!r}",
                file=sys.stderr,
            )


def _apply_orphan_portal(portal_path: Path) -> None:
    _junction.remove(portal_path)
    print(f"[cleanup] removed orphan portal: {portal_path}", file=sys.stderr)


def _apply_inplace_record(
    record: SlugRecord,
    hub_root: Path,
    task_branch: str = "",
    *,
    cfg: dict,
) -> None:
    """Apply cleanup for a single in-place (no separate worktree) record.

    Reads the parent branch from ``status.md``, checks out the parent
    branch so we are not deleting the currently-checked-out branch,
    deletes the task branch (``-d`` for done, ``-D`` for abandoned), and
    removes the ``.active`` junction at ``hub_root / ".active"``. This
    function does NOT remove the wiki active dir — ``apply_plan`` handles
    that uniformly.

    Args:
        record: The SlugRecord for the in-place task being cleaned.
        hub_root: Absolute path to the hub git checkout.
        task_branch: The task branch name resolved by ``_resolve_inplace_mode``
            via the current branch. Avoids a second git branch query.

    """
    # Read parent branch from status.md so we can check out safely.
    if record.worktree_path is not None:
        parent_branch = _status.read_parent_branch(_paths.status_path(record.worktree_path, cfg))
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
        phase = _read_phase(_paths.status_path(record.worktree_path, cfg))
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
        # Delete the remote branch after the local branch is gone so that
        # re-spawning the same slug starts clean (idempotent per Shared Decision).
        _delete_remote_branch(hub_root, task_branch)
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

    indicator = hub_root / "_mill" / f"{record.slug}.active"
    indicator.unlink(missing_ok=True)
    print(f"[cleanup] removed hub active indicator: {indicator}", file=sys.stderr)

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
        # to `_safe_rmtree.safe_rmtree` on long-path failures (junctions-stripped state
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
            # Delete the remote branch so re-spawning the same slug starts clean.
            # A missing remote ref is treated as success (idempotent teardown per
            # Shared Decision "Remote-branch delete tolerates a missing ref").
            if record.branch:
                _delete_remote_branch(hub_root, record.branch)

    # Remove the portal entry for this task.
    container_path = _paths.resolve_container_path(hub_root)
    _junction.remove(container_path / "portals" / record.slug)
    print(f"[cleanup] removed portal entry: {container_path / 'portals' / record.slug}", file=sys.stderr)

    indicator = hub_root / "_mill" / f"{record.slug}.active"
    indicator.unlink(missing_ok=True)
    print(f"[cleanup] removed hub active indicator: {indicator}", file=sys.stderr)


def _apply_pr_reap_record(
    record: SlugRecord,
    hub_root: Path,
    wiki_path: Path,
    junctions_cfg: dict[str, str],
    cfg: dict,
) -> list[str]:
    """Poll gh pr list for a [pr-pending] record and finalise teardown when the PR has merged.

    Returns a list of wiki-relative paths mutated (empty on early-exit paths).
    """
    wiki_relative_paths: list[str] = []

    # Delegate PR-state resolution to the shared helper, which applies
    # MERGED > OPEN > CLOSED precedence across all PRs on this branch and
    # collapses every error condition (gh absent, non-zero exit, empty/malformed
    # JSON) into state="none".
    pr = _pr_state.resolve_pr_state(record.branch, hub_root)
    state = pr["state"]
    merge_commit = pr["merge_commit"]
    number = pr["number"]

    if state == "none":
        print(
            f"[cleanup] PR-reap {record.slug}: no PR / gh unavailable",
            file=sys.stderr,
        )
        return wiki_relative_paths

    if state == "open":
        print(f"[cleanup] PR-reap {record.slug}: PR #{number} still OPEN -- skipping")
        return wiki_relative_paths

    if state == "closed":
        print(
            f"[cleanup] PR-reap {record.slug}: PR #{number} CLOSED without merge"
            f" -- inspect manually (abandon or reopen)",
            file=sys.stderr,
        )
        return wiki_relative_paths

    if state != "merged":
        print(
            f"[cleanup] PR-reap {record.slug}: unexpected PR state {state!r}; skipping",
            file=sys.stderr,
        )
        return wiki_relative_paths

    # MERGED: create archive tag if absent, flip Home.md, run standard teardown.
    tag_check = _subprocess_util.run(
        ["git", "-C", str(hub_root), "tag", "-l", f"archive/{record.slug}"]
    )
    if not (tag_check.returncode == 0 and tag_check.stdout.strip()):
        fetch_branch = _subprocess_util.run(
            ["git", "-C", str(hub_root), "fetch", "origin", record.branch]
        )
        if fetch_branch.returncode == 0:
            # Use FETCH_HEAD so the tag points to the remote's tip (what was
            # actually merged), not the local worktree copy which may lag behind.
            tag_target = "FETCH_HEAD"
        else:
            merge_sha = (merge_commit or {}).get("oid") if merge_commit else None
            if not merge_sha:
                print(
                    f"[cleanup] PR-reap {record.slug}: no merge SHA available; skipping",
                    file=sys.stderr,
                )
                return wiki_relative_paths
            _subprocess_util.run(
                ["git", "-C", str(hub_root), "fetch", "origin", merge_sha],
                check=True,
            )
            tag_target = merge_sha
        _subprocess_util.run(
            ["git", "-C", str(hub_root), "tag", f"archive/{record.slug}", tag_target]
        )
        _subprocess_util.run(
            ["git", "-C", str(hub_root), "push", "origin", f"archive/{record.slug}"]
        )

    wiki.set_phase(wiki_path, record.slug, "done")

    mode, task_branch = _resolve_inplace_mode(record, hub_root, wiki_path, cfg)
    if mode == "abort":
        print(
            f"[cleanup] PR-reap {record.slug}: user aborted stale-worktree prompt.",
            file=sys.stderr,
        )
        return wiki_relative_paths
    if mode == "inplace":
        _apply_inplace_record(record, hub_root, task_branch, cfg=cfg)
    else:
        _apply_worktree_record(record, hub_root, wiki_path, junctions_cfg)

    return wiki_relative_paths


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
        mode, task_branch = _resolve_inplace_mode(record, hub_root, wiki_path, cfg)
        if mode == "abort":
            print(
                f"[cleanup] skipping {record.slug} -- user aborted stale-worktree prompt.",
                file=sys.stderr,
            )
            continue

        if mode == "inplace":
            _apply_inplace_record(record, hub_root, task_branch, cfg=cfg)
        else:
            try:
                _apply_worktree_record(record, hub_root, wiki_path, junctions_cfg)
            except _worktree.WorktreeError as exc:
                hint = (
                    "file handle held by VS Code or terminal? Close it and retry"
                    if "Permission denied" in str(exc)
                    else "try 'git worktree remove --force' manually"
                )
                print(
                    f"REPORT: {record.slug} -- worktree removal failed ({hint}): {exc}",
                    file=sys.stderr,
                )
                continue

    for record in plan.to_reap_pr:
        wiki_relative_paths.extend(
            _apply_pr_reap_record(record, hub_root, wiki_path, junctions_cfg, cfg)
        )

    for portal_path in plan.orphan_portals:
        _apply_orphan_portal(portal_path)

    active_link = hub_root / ".active"
    if os.path.lexists(str(active_link)) and not active_link.is_dir():
        _junction.remove(active_link)
        print(f"[cleanup] removed dangling .active junction: {active_link}", file=sys.stderr)

    if plan.to_reset_home:
        for slug in plan.to_reset_home:
            wiki.set_phase(wiki_path, slug, None)

    # Reconcile orphaned "active" markers that have no worktree, branch, or portal.
    # This is the narrow safe auto-reset: only plain "active" (never live PR states)
    # and only when all three presence signals are absent.
    for slug in plan.to_reset_unclaimed:
        wiki.set_phase(wiki_path, slug, None)
        print(
            f"RECONCILE: {slug} active marker reset to unclaimed"
            f" (no worktree/branch/portal)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep done/abandoned task artefacts.")
    parser.add_argument("--apply", action="store_true", help="Execute removals (default: dry-run).")
    args = parser.parse_args()

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)
    cfg = _load_config(_paths.resolve_hub_path(), git_root)
    branch_prefix = cfg.get("spawn", {}).get("branch_prefix", "")
    container_path = _paths.resolve_container_path(git_root)

    # Hub check: if current branch is an active task branch, refuse to run.
    _br = _subprocess_util.run(["git", "-C", str(Path.cwd()), "branch", "--show-current"])
    _cur_branch = _br.stdout.strip() if _br.returncode == 0 else ""
    _check_slug = _cur_branch.removeprefix(branch_prefix) if branch_prefix and _cur_branch.startswith(branch_prefix) else (_cur_branch if not branch_prefix else "")

    home_tasks = wiki.list_tasks_brief(wiki_path)

    if _check_slug and any(t["slug"] == _check_slug and t["status"] == "active" for t in home_tasks):
        sys.exit("Error: mill-cleanup must run from the hub, not from a worktree.")
    junctions_cfg = _junction.read_junctions(git_root)

    active_wt_list = _spawn_core.discover_active_worktrees(
        container_path / "wts", home_tasks, branch_prefix
    )
    active_worktrees = [path for path, _slug, _title in active_wt_list]

    plan = build_plan(
        active_worktrees, home_tasks, wiki_path,
        hub_root=git_root, container_path=container_path, branch_prefix=branch_prefix,
    )
    _print_plan(plan)

    if not args.apply:
        print("\nDry-run. Pass --apply to execute.")
        sys.exit(0)

    apply_plan(plan, wiki_path, git_root, junctions_cfg, cfg=cfg)

    print(
        f"\nDone: {len(plan.to_remove_done)} done, "
        f"{len(plan.to_remove_abandoned)} abandoned removed. "
        f"{len(plan.to_reap_pr)} pr-reaped. "
        f"{len(plan.to_report)} orphans/unreadable reported."
    )


if __name__ == "__main__":
    main()
