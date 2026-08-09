# Batch: worktree-remove-safe-prune

```yaml
task: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation
batch: worktree-remove-safe-prune
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py
depends-on: []
```

## Batch Scope

Single batch: restructure `_worktree.remove_safe` (`plugins/mill/scripts/_worktree.py`) so `git worktree prune` runs unconditionally, once, after either the direct-success removal or the rmtree fallback removal — closing the gap where a force-removed task worktree leaves its nested transient worktree's git administrative entry (`.git/worktrees/<name>/`) orphaned in the hub's common gitdir. Then add real-git, no-mock end-to-end test coverage in `plugins/mill/unit_tests/test-worktree.py` reproducing the exact orphan scenario. One external interface: `remove_safe`'s signature and observable exceptions (`WorktreeLockedError`, `WorktreeError`) are unchanged; only its post-removal side effect (prune) and its trailing stderr message are affected. No batch-local decisions beyond the overview's `## Shared Decisions`.

## Cards

### Card 1: Restructure `remove_safe` to run `git worktree prune` unconditionally after either removal branch

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `_worktree.remove_safe` (currently at `plugins/mill/scripts/_worktree.py:222-318`):

  1. In the function's docstring `Sequence:` list, update item 4 (currently: "If git fails with a long-path error (Windows, common when `.scratch/` has deep claude session JSONs), fall back to `_safe_rmtree.safe_rmtree` — safe NOW because junctions are already gone — then `git worktree prune` to clear git's internal registry.") to describe `git worktree prune` as an unconditional trailing step run once after either the direct-success path or the fallback path, not only after the fallback. Renumber the existing item 5 ("Any other git failure is re-raised; callers handle "in use" messages etc.") to item 6, and insert it as new item 5 that a git failure not eligible for the rmtree fallback (an unrecognized error, or one matching `_lock_patterns`) is re-raised before prune ever runs.
  2. Locate the block:
     ```
    result = _subprocess_util.run(cmd)
    if result.returncode == 0:
        print(f"[worktree] remove_safe: removed via git ({path})", file=sys.stderr)
        return
     ```
     Remove the early `return`. Replace the `print` call in this branch with setting a new local variable `removed_via = "git"` (no print here — the print moves to the new shared trailing block in step 5 below).
  3. Wrap the existing failure-handling body — starting at `stderr = result.stderr.strip()` and continuing through the `try: _safe_rmtree.safe_rmtree(path, allowed_root=path) except PermissionError as exc: raise WorktreeLockedError(...) from exc` block — in an `else:` clause attached to the `if result.returncode == 0:` conditional from step 2, indented one additional level. This body's control flow (the `_rmtree_fallback_patterns` / `_lock_patterns` checks, the `WorktreeLockedError`/`WorktreeError` raises, the `_safe_rmtree.safe_rmtree` call and its `except PermissionError` re-raise) is otherwise unchanged.
  4. At the end of that `else:` body, after the `if path.exists(): try: ... except PermissionError ...` block, replace the two existing trailing statements (the `git worktree prune` call and its own `if prune.returncode != 0:` warning print, and the final `print(f"[worktree] remove_safe: removed via fallback ({path})", ...)`) with a single statement: `removed_via = "fallback"`.
  5. After the `if result.returncode == 0: ... else: ...` block (back at the function's original indentation level, i.e. no longer nested inside the conditional), add the shared trailing block that now runs unconditionally on every path that did not raise:
     ```python
     prune = _subprocess_util.run(
         ["git", "-C", str(cwd), "worktree", "prune"],
     )
     if prune.returncode != 0:
         print(
             f"[worktree] remove_safe: git worktree prune warning: "
             f"{prune.stderr.strip()!r}",
             file=sys.stderr,
         )
     print(f"[worktree] remove_safe: removed via {removed_via} ({path})", file=sys.stderr)
     ```
     This reuses the exact existing prune-call arguments, warning message text, and final print message shape (`removed via {removed_via}` produces the identical string `removed via git` or `removed via fallback` as the two messages it replaces).
  6. Do not change `remove_safe`'s parameters, return type (`None`), or any of `WorktreeLockedError`/`WorktreeError` raise sites' conditions or messages — only the control flow and the point(s) at which `git worktree prune` runs move.
- **Commit:** `fix(worktree): run git worktree prune unconditionally in remove_safe to clear orphaned nested-worktree registrations`

### Card 2: Add real-git end-to-end test reproducing the nested-worktree orphan scenario

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `import contextlib` and `import io` to `plugins/mill/unit_tests/test-worktree.py`'s existing top-of-file import block (alongside the existing `import json` / `import subprocess` / `import sys` / `import tempfile`).

  In `main()`, insert a new real-git (no mocks) test block immediately after the existing `# --- remove_safe exits cleanly when path absent and "is not a working tree" ---` block (currently ending at line 300) and before the `# --- processes_holding_path: ...` block (currently starting at line 302). Follow the file's existing `_git_init`/`list_worktrees` real-git test style (see the `list_worktrees: two worktrees` and `list_worktrees: detached HEAD` blocks earlier in `main()`):

  1. Create a `tempfile.TemporaryDirectory()` context. Inside it, create `hub = Path(tmp) / "hub"`, `hub.mkdir()`, then `_git_init(hub)`.
  2. Create a task worktree off the hub on a new branch: `subprocess.run(["git", "-C", str(hub), "worktree", "add", "-b", "task-branch", str(task_wt)], check=True, capture_output=True)` where `task_wt = Path(tmp) / "task"`.
  3. Create a worktree nested inside the task worktree, registered against the hub's common gitdir, mirroring `_verify_baseline._checkout_parent_branch`'s real detached-HEAD behavior: `nested_path = task_wt / ".scratch" / "nested"`. Explicitly create the parent directory first — `(task_wt / ".scratch").mkdir(parents=True, exist_ok=True)` — mirroring `_checkout_parent_branch`'s own explicit `scratch_dir.mkdir(parents=True, exist_ok=True)` — then `subprocess.run(["git", "-C", str(hub), "worktree", "add", "--detach", str(nested_path), "HEAD"], check=True, capture_output=True)`.
  4. Call `remove_safe(task_wt, cwd=hub, junctions_cfg={})` with its `sys.stderr` output captured, to later confirm which removal branch actually ran: wrap the call as `captured = io.StringIO()` then `with contextlib.redirect_stderr(captured): remove_safe(task_wt, cwd=hub, junctions_cfg={})`. Real call, no `patch()` of `_subprocess_util.run` or `kill_stale_holders`.
  5. Assert `not task_wt.exists()` (the outer worktree's directory is gone — existing, already-covered behavior).
  6. Assert the new behavior under test: call `wt_result = list_worktrees(hub)`, filter for any entry whose `Path(entry["path"]) == nested_path`, and assert that filtered list is empty — proving the trailing `git worktree prune` cleared the stale nested-worktree registration left behind by the outer worktree's force-removal. Use an assertion message that prints the unexpected surviving entries on failure.
  7. Assert `"removed via git" in captured.getvalue()` — pins down that the outer worktree removal went through the direct-success branch (`git worktree remove --force` returning 0) rather than the fallback branch, so this test cannot silently pass by only re-exercising the fallback branch's pre-existing prune call. Use an assertion message that prints `captured.getvalue()` on failure.
  8. `print("PASS: remove_safe prunes stale nested-worktree registration after force-removing enclosing task worktree")` on success.

  No new mocked test is needed — Card 1's restructure preserves the existing mocked tests' two-call `side_effect` ordering (`git worktree remove` result, then `git worktree prune` result) for the `is not a working tree` fallback-branch tests at (pre-restructure) lines 246-263 and 286-300 unchanged; do not modify those two blocks.
- **Commit:** `test(worktree): add real-git end-to-end coverage for remove_safe pruning a nested worktree's stale registration`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-worktree.py` directly (single file, matches this batch's `Edits:` scope exactly — both the restructured `remove_safe` and its new test live in files this command exercises). The file's `main()` runs every block sequentially in a single process and returns non-zero on any assertion failure or uncaught exception, so a plain script invocation is sufficient; no `run-all.py --only` wrapper is needed for a single-file batch.
