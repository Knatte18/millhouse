"""
Shared spawn-flow helpers used by both ``mill-spawn`` and ``mill-claim``.

``mill-spawn`` creates a worktree and then delegates the task-picking,
wiki-claiming, and status-writing steps to the helpers here.
``mill-claim`` (batch 04) picks and claims a task in an existing worktree
without creating a new one; it calls the same helpers to keep parity.

Public API:
    WORKTREE_COLOR_NAME_TO_HEX
        Dict mapping palette color names to CSS hex strings. Green is reserved
        for the hub (main worktree); all other colors are for child worktrees.
    WORKTREE_COLOR_PALETTE
        List of hex strings derived from ``WORKTREE_COLOR_NAME_TO_HEX.values()``.
        Single source of truth for the palette order used by ``pick_worktree_color``.
    pick_worktree_color(worktrees_dir) -> str
        Pick the first non-green palette color not already in use by a sibling
        worktree. Scans ``<worktrees_dir>/*/.vscode/settings.json``.
    BacklogEmpty        — raised by ``pick_task_single`` when no task is pickable.
    pick_task_single(tasks, slug=None) -> Task
        Single-task picker: ``--slug`` short-circuit, ``[s]`` fast-path, or
        numbered interactive prompt. Raises ``BacklogEmpty`` when nothing is
        available; raises ``ValueError`` when the requested slug is invalid.
    pick_task_single_or_multi(tasks, slug=None) -> tuple[str, Task | list[Task] | None, list[Task]]
        Extends ``pick_task_single`` with multi-select support from the numbered
        prompt. ``mode`` is ``"single"``, ``"multi"``, or ``"empty"``; ``picked``
        is one Task, a list of Task, or None; ``candidates`` is always ``[]``.
        ``--slug`` short-circuit and ``[s]`` fast-path remain single-only.
    claim_in_wiki(wiki_path, slug) -> None
        Lock-acquire, mark Home.md ``[active]``, regen sidebar, commit+push,
        lock-release.
    multi_select_groom_then_claim(wiki_path, source_slugs, merged_title,
                                  merged_slug, merged_body, has_proposal=False,
                                  proposal_body=None) -> Task
        Single wiki transaction: remove source entries, append merged entry,
        claim it, regenerate sidebar, optionally write proposal file,
        commit+push under the wiki lock. Returns the merged Task.
    prompt_merged_entry(source_tasks) -> tuple[str, str, str, bool, str | None]
        Interactive stdin prompt that collects merged title, slug, body,
        and proposal flag from the user. Re-prompts 3× on invalid input;
        raises ValueError when attempts exhausted. Returns
        (merged_title, merged_slug, body_for_home, has_proposal, proposal_body).
    capture_parent_branch(git_root) -> str
        Return the current HEAD branch name via ``git rev-parse --abbrev-ref HEAD``.
        Raises ``RuntimeError`` on non-zero exit.
    write_active_marker(mill_dir, slug, title, branch, ts) -> None
        Thin wrapper around ``_active.write``.
    write_initial_status(wiki_path, slug, title, ts, parent_branch, branch) -> Path
        Render + write ``active/<slug>/status.md``; lock + commit+push; return
        the absolute path of the written file.
    recreate_active_junction(wiki_path, slug, mill_dir) -> None
        Delete-then-create the ``.active`` junction so it points at the correct
        active-task directory. Used by ``mill-claim``; ``mill-spawn`` handles
        junctions via its own per-worktree junction loop and does not call this.
    discover_active_worktrees(worktrees_dir) -> list[tuple[Path, str, str]]
        Scan ``<worktrees_dir>/*/.millhouse/active.slug.md`` and return
        ``(path, slug, task_title)`` triples for all valid entries.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

import _active
import _junction
import _sidebar
import _status
import _subprocess_util
import _tasks_md
import _wiki

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

# ---------------------------------------------------------------------------
# Worktree color palette
# ---------------------------------------------------------------------------

# Color-name → hex mapping. Green is reserved for the hub (main worktree);
# all non-green entries are candidates for child worktrees. The dict order
# determines the rotation used by ``pick_worktree_color``.
WORKTREE_COLOR_NAME_TO_HEX: dict[str, str] = {
    "green": "#2d7d46",
    "purple": "#7d2d6b",
    "blue": "#2d4f7d",
    "yellow": "#7d5c2d",
    "red": "#6b2d2d",
    "cyan": "#2d6b6b",
    "indigo": "#4a2d7d",
    "orange": "#7d462d",
}

# Single ordered list built from the dict's values so the two stay
# synchronised. Consumers that only need the hex values import this.
WORKTREE_COLOR_PALETTE: list[str] = list(WORKTREE_COLOR_NAME_TO_HEX.values())

_MAIN_WORKTREE_COLOR = WORKTREE_COLOR_NAME_TO_HEX["green"]


def _read_worktree_color_from_settings(settings_path: Path) -> Optional[str]:
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
    Pick the first non-green palette color not used by any sibling worktree.

    Scans ``<worktrees_dir>/*/.vscode/settings.json`` for existing
    ``titleBar.activeBackground`` values. Returns the first non-green
    palette color missing from that set. If every non-green color is in
    use, wraps to the first non-green (never green — that is reserved for
    the hub).

    Args:
        worktrees_dir: Directory holding per-task worktrees. Missing dir
            returns the first non-green color straight away.

    Returns:
        A hex color like ``"#7d2d6b"``.
    """
    used: set[str] = set()
    if worktrees_dir.exists():
        for entry in worktrees_dir.iterdir():
            if not entry.is_dir():
                continue
            value = _read_worktree_color_from_settings(
                entry / ".vscode" / "settings.json"
            )
            if value:
                used.add(value)

    non_green = [
        c for c in WORKTREE_COLOR_PALETTE if c.lower() != _MAIN_WORKTREE_COLOR.lower()
    ]
    for color in non_green:
        if color.lower() not in used:
            return color
    return non_green[0]


def discover_active_worktrees(
    worktrees_dir: Path,
) -> list[tuple[Path, str, str]]:
    """
    Scan ``worktrees_dir`` for worktrees that carry an ``active.slug.md`` marker.

    For each immediate subdirectory of ``worktrees_dir``, attempts to read
    ``.millhouse/active.slug.md`` via ``_active.read_all``. Entries that are
    missing or malformed are silently skipped. Results are returned in
    filesystem iteration order (non-deterministic on most platforms).

    Args:
        worktrees_dir: Container directory holding per-task worktrees.

    Returns:
        List of ``(path, slug, task_title)`` triples, one per valid worktree.
        Empty list when ``worktrees_dir`` does not exist or contains no
        valid markers.
    """
    results: list[tuple[Path, str, str]] = []
    if not worktrees_dir.exists():
        return results
    for entry in worktrees_dir.iterdir():
        if not entry.is_dir():
            continue
        mill_dir = entry / ".millhouse"
        try:
            data = _active.read_all(mill_dir)
        except _active.ActiveError:
            continue
        slug = data.get("slug", "")
        title = data.get("task_title", "")
        if slug:
            results.append((entry, slug, title))
    return results


class BacklogEmpty(Exception):
    """Raised by ``pick_task_single`` when no pickable task exists in Home.md."""


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


def pick_task_single(
    tasks: list[_tasks_md.Task],
    slug: Optional[str] = None,
) -> _tasks_md.Task:
    """
    Pick exactly one task from ``tasks`` for claiming.

    When ``slug`` is provided the task must exist and have phase ``None``
    or ``"s"`` (i.e. not already active, done, or abandoned). Any other
    slug value raises ``ValueError``.

    When ``slug`` is ``None`` the standard interactive flow runs:

    1. If at least one task carries ``[s]``, return the first such task
       (fast-path — no user prompt).
    2. Otherwise, if at least one unmarked task exists, present the
       numbered picker and return the chosen task.  A failed picker (EOF
       or out-of-range input) returns ``None`` from ``_prompt_numbered``,
       which is propagated as ``ValueError``.
    3. If nothing is pickable, raise ``BacklogEmpty``.

    Args:
        tasks: All tasks parsed from Home.md (including active/done/abandoned).
        slug: Optional ``--slug`` override. When given, bypasses the
            interactive picker entirely.

    Returns:
        The selected ``Task``.

    Raises:
        BacklogEmpty: No pickable task exists (slug=None path only).
        ValueError: The requested slug is unknown, already claimed/done/abandoned,
            or the numbered picker returned no selection.
    """
    if slug is not None:
        matched = next(
            (t for t in tasks if t.slug == slug and t.phase in (None, "s")),
            None,
        )
        if matched is None:
            raise ValueError(
                f"--slug {slug!r} not found in Home.md or already claimed."
            )
        return matched

    # Fast-path: first [s] task in file order.
    fast = next((t for t in tasks if t.phase == "s"), None)
    if fast is not None:
        return fast

    # Numbered picker: unmarked tasks only.
    unmarked = [t for t in tasks if t.phase is None]
    if not unmarked:
        raise BacklogEmpty(
            "No pickable tasks. Mark a task [s] or leave one unmarked "
            "(see /mill-add)."
        )

    picked = _prompt_numbered(unmarked)
    if picked is None:
        raise ValueError("No task selected from numbered picker.")
    return picked


def _prompt_numbered_multi(
    candidates: list[_tasks_md.Task],
) -> list[_tasks_md.Task]:
    """
    Read one or more 1-indexed comma-separated choices from stdin.

    Accepts ``"1"``, ``"1, 3"``, ``"1,3,4"``. De-duplicates repeated indices
    silently, preserving selection order. Re-prompts on non-numeric or
    out-of-range input; up to 3 total attempts before raising ``ValueError``.

    Args:
        candidates: Ordered list of pickable tasks shown to the user.

    Returns:
        A non-empty list of the selected Task objects (de-duplicated).

    Raises:
        ValueError: All 3 attempts were invalid, or EOF on stdin.
    """
    print(
        "Pick task(s) — enter one number or comma-separated numbers:",
        file=sys.stderr,
    )
    for i, t in enumerate(candidates, start=1):
        marker = " (proposal)" if t.has_proposal else ""
        print(f"  {i}) {t.title} [{t.slug}]{marker}", file=sys.stderr)

    for _ in range(3):
        try:
            raw = input("Pick task number(s): ")
        except EOFError:
            raise ValueError("No input available for multi-picker.")

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if not parts:
            print("[spawn] Empty input. Enter at least one number.", file=sys.stderr)
            continue

        # Validate all parts are integers before range-checking.
        try:
            indices = [int(p) for p in parts]
        except ValueError:
            print(
                f"[spawn] Non-numeric input: {raw!r}. Enter numbers separated by commas.",
                file=sys.stderr,
            )
            continue

        out_of_range = [idx for idx in indices if idx < 1 or idx > len(candidates)]
        if out_of_range:
            print(
                f"[spawn] Out of range: {out_of_range!r} (valid: 1..{len(candidates)}).",
                file=sys.stderr,
            )
            continue

        # De-duplicate preserving first-occurrence order.
        seen: set[int] = set()
        unique: list[int] = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                unique.append(idx)

        return [candidates[idx - 1] for idx in unique]

    raise ValueError("No valid task selection after 3 attempts.")


def pick_task_single_or_multi(
    tasks: list[_tasks_md.Task],
    slug: Optional[str] = None,
) -> tuple[str, _tasks_md.Task | list[_tasks_md.Task] | None, list[_tasks_md.Task]]:
    """
    Pick one or more tasks from ``tasks`` for claiming, with multi-select support.

    Extends ``pick_task_single`` by allowing the numbered interactive prompt to
    return multiple tasks when the user enters comma-separated indices. The
    ``--slug`` short-circuit and ``[s]`` fast-path always resolve to a single
    task; multi only fires from the numbered prompt.

    Return shape:
        - ``("single", task, [])`` — one task picked (slug bypass, fast-path,
          or numbered prompt with a single index).
        - ``("multi", [task_a, ...], [])`` — two or more tasks from the prompt.
        - ``("empty", None, [])`` — no pickable (unmarked) tasks exist.

    Args:
        tasks: All tasks parsed from Home.md.
        slug: Optional ``--slug`` override; always single-only bypass.

    Returns:
        3-tuple ``(mode, picked, candidates)`` where ``candidates`` is always
        an empty list (reserved for future use).

    Raises:
        ValueError: Invalid slug, or no valid selection after 3 prompt attempts.
    """
    # --slug short-circuit: bypass picker entirely, always single.
    if slug is not None:
        matched = next(
            (t for t in tasks if t.slug == slug and t.phase in (None, "s")),
            None,
        )
        if matched is None:
            raise ValueError(
                f"--slug {slug!r} not found in Home.md or already claimed."
            )
        return ("single", matched, [])

    # Fast-path: first [s] task, always single.
    fast = next((t for t in tasks if t.phase == "s"), None)
    if fast is not None:
        return ("single", fast, [])

    # Numbered multi-select: unmarked tasks only.
    candidates = [t for t in tasks if t.phase is None]
    if not candidates:
        return ("empty", None, [])

    picked_list = _prompt_numbered_multi(candidates)
    if len(picked_list) == 1:
        return ("single", picked_list[0], [])
    return ("multi", picked_list, [])


def multi_select_groom_then_claim(
    wiki_path: Path,
    source_slugs: list[str],
    merged_title: str,
    merged_slug: str,
    merged_body: str,
    has_proposal: bool = False,
    proposal_body: Optional[str] = None,
) -> _tasks_md.Task:
    """
    Atomic wiki transaction that absorbs multiple tasks into a single merged entry.

    Performs all edits under the wiki advisory lock so no concurrent writer
    can interleave between the read and the commit:

    1. Remove each source slug's entry from Home.md via ``_tasks_md.remove_entry``.
    2. Append the merged entry via ``_tasks_md.append_entry``.
    3. Mark the merged entry ``[active]`` via ``_tasks_md.claim``.
    4. Regenerate the sidebar.
    5. Optionally write ``proposal-<merged_slug>.md`` when ``has_proposal=True``
       and ``proposal_body`` is provided.
    6. Commit and push under a descriptive commit message.
    7. Re-parse Home.md and return the merged Task.

    Args:
        wiki_path: Directory containing the wiki clone.
        source_slugs: Slugs of the tasks to remove and absorb.
        merged_title: Human-readable title for the merged entry.
        merged_slug: Slug for the merged entry. Must be new (not already in Home.md).
        merged_body: Body text for the merged entry in Home.md.
        has_proposal: When True, emit the ``[[slug]](proposal-slug)`` link form.
        proposal_body: Content to write into ``proposal-<merged_slug>.md``. Only
            written when ``has_proposal=True`` and not None.

    Returns:
        The newly created and claimed ``Task`` (phase ``"active"``).

    Raises:
        ValueError: A source slug is not found in Home.md (from ``remove_entry``).
        RuntimeError: The merged task cannot be found after re-parsing (parse failure).
    """
    home_path = wiki_path / "Home.md"
    _wiki.acquire_lock(wiki_path, merged_slug)
    try:
        text = home_path.read_text(encoding="utf-8")

        # Remove all source entries first, then append the merged one.
        for slug in source_slugs:
            text = _tasks_md.remove_entry(text, slug)
        text = _tasks_md.append_entry(
            text, merged_slug, merged_title, merged_body, has_proposal=has_proposal
        )
        text = _tasks_md.claim(text, merged_slug)
        home_path.write_text(text, encoding="utf-8")
        _sidebar.regenerate(wiki_path)

        files_to_commit = ["Home.md", "_Sidebar.md"]

        # Write the proposal file alongside Home.md if requested.
        if has_proposal and proposal_body is not None:
            proposal_path = wiki_path / f"proposal-{merged_slug}.md"
            proposal_path.write_text(proposal_body, encoding="utf-8")
            files_to_commit.append(f"proposal-{merged_slug}.md")

        absorbed = ", ".join(source_slugs)
        commit_msg = (
            f"task: groom-and-claim {len(source_slugs)}->1 "
            f"({merged_slug}; absorbed {absorbed})"
        )
        _wiki.write_commit_push(wiki_path, files_to_commit, commit_msg)
    finally:
        _wiki.release_lock(wiki_path)

    # Re-parse after commit to return an authoritative Task object.
    new_text = home_path.read_text(encoding="utf-8")
    parsed_tasks = _tasks_md.parse(new_text)
    merged_task = next((t for t in parsed_tasks if t.slug == merged_slug), None)
    if merged_task is None:
        raise RuntimeError(
            f"merged task {merged_slug!r} not found after commit — parse failed"
        )
    return merged_task


def prompt_merged_entry(
    source_tasks: list[_tasks_md.Task],
) -> tuple[str, str, str, bool, Optional[str]]:
    """
    Collect a merged entry definition from the user via stdin.

    Prints the source tasks to stderr for context, then prompts for:
    1. ``Merged title:`` — free-text, non-empty; re-prompts up to 3 times.
    2. ``Merged slug:`` — must match ``[a-z][a-z0-9-]*``; re-prompts 3 times.
    3. ``Extract to proposal? (y/N):`` — ``y`` sets ``has_proposal=True``.
    4. Body lines read until a line containing only ``END``.

    When ``has_proposal=True``:
        ``body_for_home`` is set to the wiki link reference form and
        ``proposal_body`` holds the typed body text.
    When ``has_proposal=False``:
        ``body_for_home`` is the typed body and ``proposal_body`` is None.

    Args:
        source_tasks: Tasks being merged; titles are printed as context.

    Returns:
        5-tuple ``(merged_title, merged_slug, body_for_home, has_proposal,
        proposal_body)``.

    Raises:
        ValueError: Merged title or slug could not be collected after 3 attempts.
    """
    # Print source task titles so the user knows what they are merging.
    print("Merging these tasks:", file=sys.stderr)
    for t in source_tasks:
        print(f"  - {t.title} [{t.slug}]", file=sys.stderr)

    # Collect merged title: free-text, must be non-empty.
    merged_title: Optional[str] = None
    for _ in range(3):
        try:
            raw = input("Merged title: ").strip()
        except EOFError:
            break
        if raw:
            merged_title = raw
            break
        print("[merge] Title cannot be empty.", file=sys.stderr)
    if merged_title is None:
        raise ValueError("No valid merged title after 3 attempts.")

    # Collect merged slug: must satisfy the slug pattern.
    merged_slug: Optional[str] = None
    for _ in range(3):
        try:
            raw = input("Merged slug: ").strip()
        except EOFError:
            break
        if _SLUG_PATTERN.match(raw):
            merged_slug = raw
            break
        print(
            f"[merge] Invalid slug {raw!r}; must match [a-z][a-z0-9-]*.",
            file=sys.stderr,
        )
    if merged_slug is None:
        raise ValueError("No valid merged slug after 3 attempts.")

    # Decide whether to extract the body to a proposal file.
    try:
        raw = input("Extract to proposal? (y/N): ").strip().lower()
    except EOFError:
        raw = ""
    has_proposal = raw == "y"

    # Collect body lines until the sentinel "END".
    print(
        "Merged body (one line per bullet, terminate with single line \"END\"):",
        file=sys.stderr,
    )
    body_lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "END":
            break
        body_lines.append(line)
    body_text = "\n".join(body_lines)

    if has_proposal:
        body_for_home = f"See [proposal-{merged_slug}.md](proposal-{merged_slug}.md)."
        proposal_body: Optional[str] = body_text
    else:
        body_for_home = body_text
        proposal_body = None

    return (merged_title, merged_slug, body_for_home, has_proposal, proposal_body)


def claim_in_wiki(wiki_path: Path, slug: str) -> None:
    """
    Mark ``slug`` as ``[active]`` in Home.md, regen sidebar, and commit+push.

    Acquires the wiki advisory lock for the full operation so no other
    writer can interleave a Home.md edit between the read and the commit.

    Args:
        wiki_path: Directory containing the wiki clone.
        slug: Task slug to claim.
    """
    home_path = wiki_path / "Home.md"
    _wiki.acquire_lock(wiki_path, slug)
    try:
        home_text = home_path.read_text(encoding="utf-8")
        claimed_text = _tasks_md.claim(home_text, slug)
        home_path.write_text(claimed_text, encoding="utf-8")
        _sidebar.regenerate(wiki_path)
        _wiki.write_commit_push(
            wiki_path, ["Home.md", "_Sidebar.md"], f"task: claim {slug}"
        )
    finally:
        _wiki.release_lock(wiki_path)


def capture_parent_branch(git_root: Path) -> str:
    """
    Return the current HEAD branch name for the hub at ``git_root``.

    Runs ``git rev-parse --abbrev-ref HEAD`` against ``git_root``. This
    is called before a worktree is created so the result reflects the
    hub's branch, which mill-merge / mill-cleanup need to know where to
    merge back to.

    Args:
        git_root: Absolute path to the hub git checkout.

    Returns:
        The branch name as a plain string (e.g. ``"main"``).

    Raises:
        RuntimeError: ``git rev-parse`` returned non-zero. The caller
            (``mill-spawn.main``) translates this into ``SystemExit``.
    """
    result = _subprocess_util.run(
        ["git", "-C", str(git_root), "rev-parse", "--abbrev-ref", "HEAD"],
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not resolve hub parent branch: {result.stderr.strip()!r}"
        )
    return result.stdout.strip()


def write_active_marker(
    mill_dir: Path,
    slug: str,
    title: str,
    branch: str,
    ts: str,
) -> None:
    """
    Write the per-worktree marker file at ``mill_dir / "active.slug.md"``.

    Thin wrapper around ``_active.write``; exists so downstream callers
    import from ``_spawn_core`` without depending on ``_active`` directly.

    Args:
        mill_dir: The ``.millhouse/`` directory inside the worktree.
        slug: Task slug.
        title: Human-readable task title.
        branch: Branch name the worktree is on.
        ts: ISO-8601 UTC timestamp of spawn time.
    """
    _active.write(
        mill_dir,
        slug=slug,
        task_title=title,
        branch=branch,
        spawned_at=ts,
    )


def write_initial_status(
    wiki_path: Path,
    slug: str,
    title: str,
    ts: str,
    parent_branch: str,
    branch: str,
) -> Path:
    """
    Render and write the initial ``active/<slug>/status.md``, then commit+push.

    Uses ``_status.render_initial`` to produce the file body, writes the
    file, commits, and returns the absolute path. No wiki lock is acquired
    because ``status.md`` is a per-task file with a single writer.

    Args:
        wiki_path: Directory containing the wiki clone.
        slug: Task slug; determines the subdirectory path.
        title: Human-readable task title used both as the ``task:`` value
            and as the description placeholder.
        ts: ISO-8601 UTC timestamp for the timeline entry.
        parent_branch: Hub branch name recorded so mill-merge knows where
            to merge back to.
        branch: The task branch the worktree is on; recorded so the wiki
            state is self-describing without inferring from per-developer
            cfg.branch_prefix.

    Returns:
        Absolute path to the written ``status.md``.
    """
    status_text = _status.render_initial(
        task_title=title,
        task_description=title,
        timestamp=ts,
        parent_branch=parent_branch,
        slug=slug,
        branch=branch,
    )
    status_rel = f"active/{slug}/status.md"
    status_abs = wiki_path / status_rel
    status_abs.parent.mkdir(parents=True, exist_ok=True)
    status_abs.write_text(status_text, encoding="utf-8")
    _wiki.write_commit_push(
        wiki_path, [status_rel], f"spawn: init status for {slug}"
    )
    return status_abs


def recreate_active_junction(
    wiki_path: Path,
    slug: str,
    mill_dir: Path,
) -> None:
    """
    Delete-then-create the ``.active`` junction at ``mill_dir.parent / ".active"``.

    Points the junction at ``wiki_path / "active" / slug``. Called by
    ``mill-claim`` after claiming a task in an existing worktree where the
    junction may already exist pointing at a previous task. ``mill-spawn``
    does NOT call this helper — it handles junctions via its own per-worktree
    junction loop.

    If the target directory does not yet exist it is created (parents
    included) so ``_junction.create`` does not fail on a missing target.

    Args:
        wiki_path: Directory containing the wiki clone.
        slug: Task slug; determines the target path.
        mill_dir: The ``.millhouse/`` directory inside the worktree.
            The junction is placed at ``mill_dir.parent / ".active"``.
    """
    target = wiki_path / "active" / slug
    target.mkdir(parents=True, exist_ok=True)
    link_path = mill_dir.parent / ".active"
    if link_path.exists() or link_path.is_symlink():
        _junction.remove(link_path)
    _junction.create(target, link_path)
