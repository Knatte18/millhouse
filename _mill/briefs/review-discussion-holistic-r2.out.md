MILL_REVIEW_BEGIN
# Review: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Testing section misattributes existing test-junction.py coverage
**Section:** Testing — "Regression guard (existing coverage, must still pass)"
**Issue:** Claims `test-junction.py` has existing "junction create/remove/points_to" and "permission-denied" cases for `strip_all_in_worktree`; the actual file's docstring scopes it to FS-scan behavior only, and its 5 cases (strips-undeclared-junction, multiple-junctions, non-junction-untouched, missing-worktree, nested-junction) include no permission-denied case at all — the only existing `PermissionError` regression tests for worktree teardown live in `test-worktree.py` (targeting `remove_safe`, not `strip_all_in_worktree` directly).
**Fix:** Correct the regression-guard bullet to name the actual 5 existing cases, and note that widening `_walk`'s `except PermissionError` (line 318) to also catch `FileNotFoundError` currently has zero direct unit coverage protecting the permission-denied skip-and-return-early branch.

### [GAP] Guard-scope enumeration omits the `_junction.remove(ep)` / `_junction.remove(ep)` call itself
**Section:** Decisions — "Guard placement: per-entry try/except plus a top-of-function guard"
**Issue:** Both walks' per-entry try/except is enumerated as covering only the symlink/reparse-point *detection* calls and the recursive descent (`entry.is_symlink()`, `_is_reparse_point`/`_is_junction_or_symlink`, and the recursive walk call) — the actual removal call (`_junction.remove(ep)`, which does `os.unlink`/`os.rmdir` at `_safe_rmtree.py` line 66 and `_junction.py` line 330) is never explicitly named, leaving it ambiguous whether a symlink/junction that vanishes between being detected and being removed (the same TOCTOU class this fix targets) is inside or outside the guarded region.
**Fix:** Explicitly state whether `_junction.remove(ep)` is inside the per-entry `try/except FileNotFoundError` block, since `os.unlink`/`os.rmdir` on an already-vanished path is a real `FileNotFoundError` source this fix should plausibly cover.

## Verdict

GAPS_FOUND
Testing-coverage claim about test-junction.py is inaccurate; guard scope leaves the removal call's TOCTOU window unaddressed.
MILL_REVIEW_END
