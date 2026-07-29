MILL_REVIEW_BEGIN
# Review: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Top-level `os.scandir(root)` guard's behavior/rationale left unspecified
**Section:** Decisions > Guard placement placement; Technical context (`_safe_rmtree.py`)
**Issue:** The stated rationale for the top-level `os.scandir(root)` guard ("root itself vanished between being listed by its parent's scandir and being recursed into") describes a race that the caller's per-entry `try/except FileNotFoundError: continue` (wrapping the recursive `_walk_strip_reparse_points(ep)` call) already catches — so as rationalized the guard is redundant. The call that is actually unprotected by anything else is `safe_rmtree`'s own direct invocation `_walk_strip_reparse_points(original)` (line 151) after the `exists()` check (line 147-148) — a TOCTOU window with no enclosing try/except anywhere in the call chain — and the discussion never names this as the guard's real justification. Unlike the parallel `_junction.py` guard, which gets a fully-specified log message and return-early behavior, this top-level guard's own except-clause behavior (log text? silent return?) is never spelled out. Testing's Scenario 3 (top-level entry-point coverage) is written only for `strip_all_in_worktree`, leaving no scenario exercising this specific `safe_rmtree`-step6-to-step7 window.
**Fix:** Re-anchor the rationale on the un-guarded `safe_rmtree` step 6->7 window on `original`, specify the guard's exact log message and return behavior (mirroring the per-entry `[safe-rmtree] skip vanished entry: {ep}` format or stating explicitly it returns silently), and add a Testing scenario for it (mock `os.scandir` to raise `FileNotFoundError` on the very first top-level call to `_walk_strip_reparse_points`).

## Verdict

GAPS_FOUND
One GAP: top-level guard's rationale is misattributed and its log/return behavior is unspecified.
MILL_REVIEW_END
