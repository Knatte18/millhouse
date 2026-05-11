# Discussion: 46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup

```yaml
task: 46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup
slug: home-md-states-teardown-split
status: discussing
parent: main
```

## Problem

Two coupled design smells in the current finalize flow:

1. **mill-go prematurely flips Home.md `[done]` before mill-merge has run.** If mill-merge halts (e.g., merge conflict, Windows lock, PR-pending), the operator must manually flip Home.md back to `[active]`. This is semantically wrong — the task is not "done" until the squash has landed on the parent branch. The premature flip also breaks `millpy-merge-in-subagent.py`: `slug_from_branch` gates on `[active]` and fails when Home.md shows `[done]` (#230).

2. **mill-merge deletes its own worktree while running inside it.** Step 8 calls `_worktree.remove_safe` on the child worktree while mill-merge is executing there. This makes mill-go's `/mill-self-report` in Handoff step 6 lose access to source files. The `WorktreeLockedError` guard is fragile and was observed to cause a partial teardown on 2026-05-11 (task 43): `remove_safe` raised `WorktreeError` (Windows `Invalid argument` — not classified as a lock) and the fallback `rmdir` left a half-removed worktree on disk with no git worktree registry entry. mill-cleanup from parent would have been safe, but the chain broke inside mill-merge before cleanup was an option.

Both problems stem from the two-state Home.md (`[active]`/`[done]`): mill-merge must do merge + teardown atomically because there is no intermediate state to signal "merge done, teardown pending." Splitting the state machine enables splitting the responsibility.

## Scope

**In:**

- `_tasks_md.py`: add `[ready-to-merge]` and `[pr-pending]` to `_HEADING_RE`, `_VALID_PHASES`, and `Task.phase` type annotation.
- `_marker.py` (`slug_from_branch`): remove `[active]`-only phase check; validate only that slug exists in Home.md.
- `mill-go` SKILL.md, Handoff step 2: flip `[active]` → `[ready-to-merge]` instead of `[done]`.
- `mill-merge` SKILL.md: remove Steps 8–10 (worktree, portal, wiki active-dir teardown); flip Home.md to `[pr-pending]` (not `[active]`) on the PR path; Step 12 report updated to say "worktree intact — run `/mill-cleanup` to remove."
- `millpy-cleanup.py`: change teardown trigger from `status.md phase: done` to `Home.md marker [done]` (+ archive tag sanity check); add PR-reap for `[pr-pending]` tasks; add `to_reap_pr` to `CleanupPlan`.
- `mill-cleanup` SKILL.md: document PR-reap, new states, and that teardown now originates here.
- `mill-status` SKILL.md: add `[ready-to-merge]`, `[pr-pending]` columns to state table.
- `_worktree.py` (`remove_safe`): add `"Invalid argument"` to `_lock_patterns` (#232).
- Unit tests: `test-tasks-md.py` (new phases), `test-cleanup.py` (new trigger logic, PR-reap), `test-marker.py` (relaxed phase check).
- Integration test: `test-merge.py` — remove teardown assertions; add assertion that worktree still exists post-merge.

**Out:**

- mill-finalize (task 40) — depends on this task's teardown split; design follows this PR.
- `_status.update_field` `add_if_missing` fix (#238) — scoped to task 50 (bug-fix batch 5).
- mill-autorun (task 48), mill-orchestrator (task 30) — different scope.
- Mill-merge's merge lock, rollback, PR-creation, archive-tag, and Home.md `[done]` flip logic — unchanged.
- `discover_active_worktrees` — no change; already accepts any Home.md phase.

## Decisions

### relax-slug-from-branch-phase-check

- **Decision:** `slug_from_branch` removes the `if task.phase != "active": raise MarkerError(...)` check. It validates only that the slug is present in Home.md.
- **Rationale:** Per the proposal invariant, `task/status.md` is the lifecycle source of truth; Home.md is a coordination index. Skills that need phase validation read status.md themselves. The current `[active]`-only check is what causes issue #230 (merge-in subagent fails when Home.md shows `[done]` from the premature flip) and will cause the same failure with `[ready-to-merge]`.
- **Rejected:** Adding an allowed-phases list — couples `slug_from_branch` to the Home.md phase vocabulary unnecessarily. The slug-existence check is the right contract for a slug resolver.

### teardown-trigger-home-md-done

- **Decision:** `build_plan` triggers worktree teardown when the **Home.md marker is `[done]`**. The existing `git log parent..child_branch` guard is replaced by an archive tag existence check (`git tag -l archive/<slug>`) as a sanity gate.
- **Rationale:** `status.md phase: done` is ambiguous: it means "mill-go is done" but says nothing about whether the squash has landed. Home.md `[done]` is unambiguous — mill-merge sets it (Step 7) only after the squash is committed to origin. The `git log` guard is incorrect for squash merges: the child branch remains ahead of parent in git history even after squash (squash creates a new commit on parent, not a merge). Archive tag is set in mill-merge Step 6, immediately before the Home.md flip, so its presence is a reliable proxy.
- **Rejected:** Keep the git log check — this incorrectly flags every squash-merged task as "unmerged commits," blocking teardown. Rejected: Add a new `status.md` phase `ready-to-merge` — unnecessary schema coupling; Home.md already carries this signal.

### ready-to-merge-is-live

- **Decision:** `build_plan` treats tasks with `status.md phase: done` AND `Home.md marker [ready-to-merge]` as **live** (no action). They pass through the `_LIVE_PHASES` equivalent without entering `to_remove_done`.
- **Rationale:** `[ready-to-merge]` means mill-go is done but mill-merge has not run yet. Cleanup must not race with mill-merge or preempt the operator's chance to run mill-merge manually.
- **Rejected:** Report them in dry-run output — YAGNI; cleanup's job is removing done/abandoned artefacts, not surfacing merge-ready tasks.

### pr-pending-home-md-flip

- **Decision:** mill-merge's PR path (Step 5) flips Home.md to `[pr-pending]` after creating the PR. mill-cleanup detects `[pr-pending]` tasks during `build_plan`, adds them to `to_reap_pr`, and `apply_plan` polls the PR state.
- **Rationale:** Without the Home.md flip, `[active]` is overloaded to mean both "actively being implemented" and "waiting for a GitHub PR to merge." Operators cannot distinguish the two. `[pr-pending]` makes the state machine explicit and gives mill-cleanup a clean trigger.
- **Rejected:** Leave Home.md at `[active]` during PR wait and poll status.md — confusing; `[active]` should mean "worktree is live and being worked on."

### pr-reap-resolve-by-branch

- **Decision:** mill-cleanup resolves the PR for `[pr-pending]` tasks via `gh pr list --head <branch> --state all --json state,mergeCommit,number` using the branch name from the worktree. No new field is added to `status.md`.
- **Rationale:** The branch name is always derivable from the git worktree registry. Adding a `pr_number:` field to `status.md` requires a schema migration and a new `update_field` call in mill-merge, for no practical benefit.
- **Rejected:** Store PR number in `status.md` — adds schema coupling. Use `gh pr view` by number — requires knowing the number first.

### pr-reap-teardown-sequence

- **Decision:** When cleanup detects a `[pr-pending]` task whose PR is `MERGED`: (1) verify archive tag (create if absent — safety net); (2) flip Home.md `[done]`; (3) run standard worktree teardown (same `_apply_worktree_record` / `_apply_inplace_record` as for `[done]` tasks). When PR is `OPEN`: no-op. When PR is `CLOSED` (unmerged): report to operator for manual decision (abandon? reopen?).
- **Archive tag commit target:** mill-merge's PR path does NOT create the archive tag before halting (it halts at Step 11, skipping Step 6). mill-cleanup's PR-reap creates the tag. The tag should point to the cleanup-commit tip of the child branch. Sequence: (a) run `git fetch origin <child_branch>` — if the branch still exists remotely, tag the fetched tip; (b) if the fetch fails (GitHub auto-deleted the branch after merge), use the `mergeCommit` SHA from the `gh pr list` JSON, fetching it via `git fetch origin <mergeCommit_sha>` first. The tag is created via `git tag archive/<slug> <sha>` and `git push origin archive/<slug>`.
- **Rationale:** Same teardown code as `[done]` tasks avoids duplication. Archive tag commit target must be specified explicitly because GitHub may auto-delete the child branch after PR merge.
- **Rejected:** Calling mill-merge re-entry for PR-reap — mill-merge re-entry is designed for the cleanup commit + archive tag + Home.md flip, all of which may already be done; running it again is not idempotent for the Home.md flip.

### invalid-argument-is-lock

- **Decision:** Add `"Invalid argument"` to `_lock_patterns` in `_worktree.remove_safe`. This routes the Windows NTFS error to `WorktreeLockedError` instead of `WorktreeError`.
- **Rationale:** Windows reports `"Invalid argument"` when a file handle is held open by a running process (NTFS locks). The existing handling of `"Permission denied"` and `"Access is denied"` covers the same condition on different Windows builds. All three are lock conditions, not logic errors. `WorktreeLockedError` triggers the documented "close CC session and re-run" message rather than an opaque halt.
- **Rejected:** Handle only in mill-cleanup — the fix belongs in `remove_safe` because all callers share this code path.

## Technical context

### `_tasks_md.py`

`_HEADING_RE` is the regex that parses slug lines. The alternation group for phases is `s|active|done|abandoned`. Two new values are added: `ready-to-merge` and `pr-pending`. The `_VALID_PHASES` tuple mirrors the regex; it is checked in `set_phase`. No other parsing logic changes.

### `_marker.py`

`slug_from_branch` (lines 28–67) currently does:
```python
if task.phase != "active":
    raise MarkerError(f"task {slug!r} is not [active] in Home.md (phase={task.phase!r})")
```
This block is removed. The preceding existence check `if task is None: raise MarkerError(...)` remains.

### `mill-go` Handoff

Step 2 (SKILL.md line ~282–286) calls `_tasks_md.set_phase_at(home_path, slug, "done")`. Change to `"ready-to-merge"`. The status.md `phase: done` call in step 1 is unchanged — status.md still records `done` as the implementation-complete phase.

### `mill-merge` SKILL.md

Steps 8 (drop worktree + branch), 9 (remove portal), and 10 (remove wiki active directory) are deleted from the teardown sequence. Step 11 (release merge lock + sidebar) and Step 12 (notify + report) remain. The Step 12 report is updated: instead of "Worktree and branch removed," it says "Worktree intact — run `/mill-cleanup --apply` to remove worktree, branch, and portal."

The `WorktreeLockedError` handling block in Step 8 becomes obsolete and is removed with Step 8.

The PR path (Step 5) adds a Home.md flip to `[pr-pending]` before halting:
```python
with _wiki.wiki_lock(wiki_path, slug):
    home_text = home_path.read_text(encoding="utf-8")
    new_text = _tasks_md.set_phase(home_text, slug, "pr-pending")
    home_path.write_text(new_text, encoding="utf-8")
    _wiki.write_commit_push(wiki_path, ["Home.md"], f"task: pr-pending {slug}", slug=slug)
```

### `millpy-cleanup.py`

**`CleanupPlan`:** Add `to_reap_pr: list[SlugRecord]`.

**`build_plan` changes:**

The existing `if phase == "done":` branch changes to gate on both status.md and Home.md:
```python
if phase == "done":
    home_marker = marker_by_slug.get(slug)
    if home_marker == "done":
        # Archive tag sanity check (replaces git log guard)
        tag_result = _subprocess_util.run(
            ["git", "-C", str(hub_root), "tag", "-l", f"archive/{slug}"]
        )
        if tag_result.returncode == 0 and tag_result.stdout.strip():
            to_remove_done.append(record)
        else:
            to_report.append(
                f"{slug} — Home.md=[done] but archive tag absent; run mill-merge first"
            )
    elif home_marker == "ready-to-merge":
        pass  # live — mill-merge hasn't run yet, leave worktree intact
    else:
        to_report.append(
            f"{slug} — phase=done but Home.md marker is {home_marker!r}; inspect manually"
        )
```

New branch for `[pr-pending]` tasks (note: these come from Home.md, not status.md phase — but the worktree's status.md will show `phase: pr-pending`):
```python
elif phase == "pr-pending":
    to_reap_pr.append(record)
```

**Orphan detection for new states:** The existing orphan check fires only for `task.phase == "active"` tasks with no active worktree. Extend to also report `[ready-to-merge]` and `[pr-pending]` tasks with no active worktree — same `to_report` message pattern: `f"{slug} — Home.md marker is [{task.phase}] but has no active worktree"`. These can arise if a worktree is manually deleted mid-teardown, leaving the Home.md marker stranded. They should be reported so the operator can clean them up manually (e.g., flip Home.md or re-run mill-cleanup after resolving the worktree state). The orphan check extension is a one-line change to the phase condition: `if task.phase in ("active", "ready-to-merge", "pr-pending") and task.slug not in active_slugs`.

**`apply_plan` changes:** Add PR-reap loop over `plan.to_reap_pr`. For each record:
1. Run `gh pr list --head <branch> --state all --json state,mergeCommit,number`.
2. Parse JSON. `state == "MERGED"` → create archive tag if absent, flip Home.md `[done]`, call `_apply_worktree_record` or `_apply_inplace_record`, add to wiki_relative_paths. `state == "OPEN"` → no-op. `state == "CLOSED"` → append to `to_report`: `"${slug} — PR closed without merging; inspect manually (abandon or reopen)"`.

The `_print_plan` function is updated to show `to_reap_pr` records.

### `_worktree.py`

`_lock_patterns` in `remove_safe` (line 254):
```python
_lock_patterns = ("Permission denied", "is in use", "Access is denied")
```
Change to:
```python
_lock_patterns = ("Permission denied", "is in use", "Access is denied", "Invalid argument")
```

### Tests

**`test-tasks-md.py`:** New assertions in the `set_phase` block:
- `set_phase(text, slug, "ready-to-merge")` succeeds and round-trips via `parse`.
- `set_phase(text, slug, "pr-pending")` succeeds.
- `parse` accepts headings with `[ready-to-merge]` and `[pr-pending]` markers.
- `set_phase(text, slug, "ready-to-merge")` raises `ValueError` only if the slug is absent (existing behavior).

**`test-marker.py`:** New tests:
- `slug_from_branch` succeeds when Home.md phase is `ready-to-merge`.
- `slug_from_branch` succeeds when Home.md phase is `pr-pending`.
- `slug_from_branch` succeeds when Home.md phase is `done`.
- `slug_from_branch` still raises `MarkerError` when slug is absent from Home.md.
- `slug_from_branch` still raises `MarkerError` on detached HEAD.

**`test-cleanup.py`:** New test cases (each as a separate `with tempfile.TemporaryDirectory()` block following existing pattern):
- `build_plan` with `phase=done` + `home_marker="done"` + archive tag present → `to_remove_done`.
- `build_plan` with `phase=done` + `home_marker="done"` + archive tag absent → `to_report` (mill-merge not done).
- `build_plan` with `phase=done` + `home_marker="ready-to-merge"` → no action (live).
- `build_plan` with `phase=pr-pending` + `home_marker="pr-pending"` → `to_reap_pr`.
- `apply_plan` with `to_reap_pr`, PR state `MERGED` → teardown executed, Home.md flipped to `[done]`.
- `apply_plan` with `to_reap_pr`, PR state `OPEN` → no-op.

For the `apply_plan` PR-reap tests, mock `_subprocess_util.run` to return canned `gh pr list` JSON. Use the `patch` pattern already in the test file.

**`test-merge.py` (integration):** Remove assertions that check the worktree is deleted post-merge. Add assertion that `<container>/wts/<slug>` still exists after mill-merge completes. Verification of Home.md `[done]` and archive tag creation are retained.

## Constraints

No `CONSTRAINTS.md` at hub root.

From CLAUDE.md:
- Junctions inside worktrees must be stripped before any recursive deletion (`_worktree.remove_safe`; no raw `rmdir /s` or `shutil.rmtree` on worktree paths).
- Wiki mutations go through `_wiki.write_commit_push` inside a `_wiki.wiki_lock` block. Scripts must never `cd` into the wiki clone.
- `task/status.md` is the lifecycle source of truth. Home.md is the coordination index (ownership/claim state). Never use Home.md as the gate for phase-dependent logic inside scripts.
- `${CLAUDE_PLUGIN_ROOT}` for all intra-plugin paths in skills; source-tree `plugins/mill/` only for test runners.

## Testing

Per-module approach:

- **`_tasks_md.py`** — unit tests only; no git, no wiki. In-memory string fixtures are sufficient. Test the regex extension (parse) and the validation extension (set_phase). TDD candidate: write failing tests for new phases before editing the regex.
- **`_marker.py`** — unit tests with a tempdir git repo (as `_test_helpers._make_task_worktree` already does). Replace or extend existing happy-path tests to cover `ready-to-merge`, `pr-pending`, and `done` phases. Ensure the existing `MarkerError` cases (detached HEAD, unknown slug) still pass.
- **`millpy-cleanup.py`** — unit tests with mocked `_subprocess_util.run` (existing pattern). The archive tag check and `gh pr list` call are the new mock targets. Test each new branch of `build_plan` independently. PR-reap `apply_plan` tests mock `gh pr list` JSON output.
- **`_worktree.py`** — existing `test-worktree.py` has `remove_safe` tests for lock patterns; add a test case where stderr contains `"Invalid argument"` and assert `WorktreeLockedError` is raised.
- **Integration `test-merge.py`** — only teardown-related assertions change; squash, archive tag, and Home.md flip assertions are unchanged.

## Q&A log

- **Q:** Should `slug_from_branch` validate Home.md phase at all, or only confirm slug presence? **A:** [auto-pick] Only confirm slug presence. **Why:** Phase validation belongs in status.md per the design invariant; `slug_from_branch` is a slug resolver, not a phase gatekeeper. The existing `[active]`-only check is what causes #230.
- **Q:** How should mill-cleanup detect that a `[done]` task's squash has landed? (A) Archive tag check; (B) git log parent..child_branch; (C) status.md phase only. **A:** [auto-pick] (A) Archive tag check. **Why:** git log doesn't work for squash merges (child branch remains "ahead" of parent in history). Archive tag is set by mill-merge Step 6 immediately before the Home.md flip.
- **Q:** Should PR number be stored in status.md or resolved on-demand from branch? (A) Resolve on-demand via `gh pr list --head <branch>`; (B) Store PR number in status.md. **A:** [auto-pick] (A) Resolve on-demand. **Why:** Branch name is always available from git worktree list. Storing PR number adds a schema migration and a new `update_field` call in mill-merge.
- **Q:** Should tasks with status.md `phase: done` + Home.md `[ready-to-merge]` produce any output in dry-run? **A:** [auto-pick] No output, treated as live. **Why:** YAGNI — cleanup reports done/abandoned artefacts, not tasks waiting for mill-merge.
- **Q:** Is the `millpy-merge-in-subagent.py` fix subsumed by the `slug_from_branch` change? **A:** [auto-pick] Yes, fully subsumed. **Why:** The subagent calls `slug_from_branch`; once the phase check is removed there, the subagent inherits the fix with no separate change.
- **Q:** What `build_plan` logic change handles the ambiguity of status.md `phase: done`? (A) Check Home.md marker to distinguish `[ready-to-merge]` from `[done]`; (B) Add a new status.md phase `ready-to-merge`. **A:** [auto-pick] (A) Check Home.md marker. **Why:** Avoids adding schema complexity to status.md. Home.md marker is already the right authority for claim/ownership state.
