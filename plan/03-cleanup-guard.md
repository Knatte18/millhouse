# Batch: Cleanup guard

```yaml
task: 19 (A) — mill-go + scripts infra fixes
batch: Cleanup guard
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch adds a guard in `millpy-cleanup.py`'s `build_plan()` function: before scheduling a `phase: done` worktree for removal, it checks whether the task branch has unmerged commits relative to the parent branch. If it does, the worktree goes to `to_report` instead of `to_remove_done`. This prevents mill-cleanup from deleting worktrees that mill-merge hasn't processed yet.

The external interface: `build_plan()` now uses `_subprocess_util.run` for a read-only `git log` query. Batch 05 (Tests) depends on this change to write the cleanup guard unit tests.

Batch-local decisions:
- The `continue` statement after adding to `to_report` skips `to_remove_done.append(record)` — this is the correct control flow.
- If `read_parent_branch` returns `None` or `record.branch` is `None`, the guard is skipped and the record falls through to `to_remove_done` (safe default — we can't verify without both branches).
- The git log query uses `hub_root` (not the worktree path) as the `-C` argument because the hub is the authoritative git repo that tracks all branches.

## Cards

### Card 5: Add unmerged-commits guard in build_plan()

- **Reads:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Modifies:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-cleanup.py`, inside `build_plan()`:

  1. Replace the block:
     ```python
     if phase == "done":
         to_remove_done.append(record)
     ```
     with:
     ```python
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
     ```

  2. Update `build_plan()`'s docstring to change "Side-effect-free w.r.t. git and wiki writes; reads status.md files via `_read_phase` (file I/O)." to "No git or wiki writes (read-only git queries are permitted); reads status.md files via `_read_phase` (file I/O)."

- **Commit:** `fix(millpy-cleanup): guard phase=done against unmerged commits`

## Batch Tests

`verify: null` — tests for the guard are added in Batch 05 (Tests), which depends on this batch. No standalone verify command here.
