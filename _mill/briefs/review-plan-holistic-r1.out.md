MILL_REVIEW_BEGIN
# Review: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] Corroboration self-healing persist never fires from real callers
**Location:** Batch 4, Card 8 (millpy-implement.py call sites); depends on Card 7's `status_path` guard in `_implementer_common.py`
**Issue:** `_run_verify_gates`'s new self-healing write (`_status.set_batch_field(status_path, batch_name, ...)`) only fires when both `status_path` and `batch_name` are non-`None`. Card 8 threads `batch_name=args.batch_name,` into the finalize/full-stage calls to `finalize_from_output`/`_forward_output`, but neither of those two call sites in `millpy-implement.py` (verified at lines ~734-751 and ~983-999) currently passes `status_path=status_path,` — `status_path` is only ever used there as `task_dir=status_path.parent,`. So in production `status_path` stays `None` at every real call into `_run_verify_gates`, and the persisted-baseline self-healing this batch's own scope description promises ("persist the expanded signature set back into status.md so later batches in the same task don't re-pay the same false block") never actually executes, even though the corroboration waiver itself (which doesn't need status_path) still works.
**Fix:** Card 8 must also add `status_path=status_path,` to both call sites (the local variable already exists in scope at both), immediately alongside the new `batch_name=args.batch_name,` line.
**Note:** Card 9's tests (72e/72f) call `_run_verify_gates` directly with an explicit `status_path=<fixture path>` kwarg, so they pass regardless of this gap — the missing wiring would not be caught by `verify:`.

### [NIT:consistency] New corroboration test case labels collide with an existing case 72e
**Location:** Batch 4, Card 9
**Issue:** Card 9 says to place new cases "immediately after ... cases (72a-72d)" and label the new ones 72e/72f/72g. `test-implementer-common.py` actually already has a case labelled `(e)`/"case 72e" at the current end of the Case-72 matrix (line ~4988, "a stuck dict with no 'signatures' key must never be waived") — there are 5 existing sub-cases (72a-72e), not 4, and "Case 73" (an unrelated dirty-tree regression test) immediately follows.
**Fix:** New cases should be labelled 72f/72g/72h (after the real last sub-case, 72e) and inserted before Case 73, not reusing the already-taken 72e label.

### [NIT:consistency] Card 3 reimplements `git worktree list --porcelain` parsing that `_worktree.list_worktrees` already provides
**Location:** Batch 2, Card 3 (`_scan_orphan_baseline_dirs`)
**Issue:** `millpy-cleanup.py` already imports `_worktree` and calls `_worktree.list_worktrees(hub_root)` (line 234) to get parsed `{"path":..., "branch":...}` dicts from the same porcelain output. Card 3 instead prescribes a hand-rolled `_subprocess_util.run(["git","-C",...,"worktree","list","--porcelain"])` + manual `worktree <path>` line-parsing inside `_scan_orphan_baseline_dirs`, duplicating that existing helper's logic in the same file.
**Fix:** Reuse `_worktree.list_worktrees(wt_path)` wrapped in `try/except _worktree.WorktreeError: return []` to get the fail-safe-on-failure behavior Card 3 wants, instead of reimplementing porcelain parsing.

## Verdict

REQUEST_CHANGES
Card 8 must thread `status_path` alongside `batch_name`, or batch 4's self-healing persistence silently never runs.
MILL_REVIEW_END
