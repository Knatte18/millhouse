# Review: 12 (C) — Restructure hub junction layout

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: discussion.md (rename-hub-junctions)
date: 2026-05-06
```

## Findings

### [GAP] Migration "most recently active" slug unspecified
**Section:** Technical context / `millpy-migrate-layout.py`
**Issue:** Step 3 says update hub `.active` to point to "most recently active slug (or skip if none)" but provides no mechanism for determining recency — git timestamps, `task.md` `created_at`, `Home.md` order, and portals mtime are all candidates with different semantics.
**Fix:** Specify the recency heuristic (e.g., largest `created_at` in `wiki/active/*/task.md`, or simply the most-recently-modified `portals/<slug>` entry).

### [GAP] Migration behavior on dirty task worktree unspecified
**Section:** Technical context / `millpy-migrate-layout.py`
**Issue:** The migration `git mv` + commit step will fail or produce an unexpected result if a task worktree has uncommitted changes; no policy is stated (abort the step, skip that worktree with a warning, stash-and-restore).
**Fix:** State the intended behavior — e.g., "check for clean working tree before moving files; skip and warn if dirty, then report unprocessed worktrees at the end."

### [NOTE] `mill-spawn/SKILL.md` absent from update table
**Section:** SKILL.md files to update
**Issue:** Spawn gains three new responsibilities (wiki active dir creation, portal target change, hub `.active` update) but `mill-spawn/SKILL.md` is not in the update table.
**Fix:** Confirm whether the file exists and add it to the table if so.

### [NOTE] No integration test strategy for NTFS junction operations
**Section:** Testing
**Issue:** Unit tests cover logic but junction creation, portals re-targeting, and the migration script all touch real NTFS and real git; the discussion does not say whether integration tests will be added or are explicitly out of scope.
**Fix:** Add a one-line statement on integration test coverage (even "out of scope for this PR" is sufficient).

## Verdict

GAPS_FOUND
Two migration-path ambiguities must be resolved before the plan can be written without guesswork.