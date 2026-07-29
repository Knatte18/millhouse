MILL_REVIEW_BEGIN
# Review: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Guard-placement enumeration omits `entry.is_dir(follow_symlinks=False)` for the `_safe_rmtree` walk
**Section:** Decisions / "Guard placement: per-entry try/except plus a top-of-function guard"
**Issue:** For `_safe_rmtree._walk_strip_reparse_points`, the explicit list of calls to wrap in the per-entry `try/except FileNotFoundError` names `entry.is_symlink()`, `_is_reparse_point(ep)`, `_junction.remove(ep)`, and the recursive call — but omits `entry.is_dir(follow_symlinks=False)` (actual line 68 of `_safe_rmtree.py`). The Rationale paragraph immediately below, however, explicitly names `entry.is_dir(follow_symlinks=False)` as one of the calls that is "not guarded anywhere in either call chain" and needs the fix. For the sibling `_junction.py` walk, the parallel enumeration does explicitly include `entry.is_dir()`. This is exactly the class of enumeration ambiguity discussion-review round 2 flagged and fixed for the removal call — it has reappeared here for the dir-check call, and the Decision's own Rejected bullet warns against "giving the two walks different guard shapes."
**Fix:** Add `entry.is_dir(follow_symlinks=False)` explicitly to the `_safe_rmtree` walk's enumerated list in the Decision (not just the Rationale), matching the `_junction.py` walk's enumeration and confirming both walks' guarded regions are identical in shape.

## Verdict

GAPS_FOUND
One enumeration inconsistency in the guard-placement decision needs correcting before plan writing.
MILL_REVIEW_END
