Now I have enough source context to write the review.

# Review: (A) — Central safe-rmtree helper + ban direct rmtree

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: C:\Code\millhouse\wts\safe-rmtree\_mill\discussion.md
date: 2026-05-13
```

## Findings

### [GAP] resolve_container_path raises SystemExit, not Exception
**Section:** Technical Context — `resolve_container_path` behaviour for non-container paths  
**Issue:** `resolve_main_worktree_root` (called inside `resolve_container_path`) raises `SystemExit` on `git rev-parse` failure, not a regular `Exception`. The discussion says "wrap in try/except" without specifying the exception type — a standard `except Exception` silently misses `SystemExit` and crashes. Directly impacts the migrated unit-test `addCleanup(safe_rmtree, self.tmp_path, ...)` calls, since `$TEMP` paths are outside any git repo, and the `test_handles_non_container_allowed_root` test (which asserts no crash) would fail.  
**Fix:** Specify that the guard must be `except (Exception, SystemExit)` or `except BaseException` so the fallback-to-empty-blacklist path actually executes.

### [NOTE] os.scandir does not accept follow_symlinks parameter
**Section:** Decisions — Reparse-point detection  
**Issue:** The pseudocode `os.scandir(..., follow_symlinks=False)` is invalid — `os.scandir` has no `follow_symlinks` parameter; that argument belongs on per-entry methods (`entry.is_dir(follow_symlinks=False)`).  
**Fix:** Restate as "iterate `os.scandir(path)`; skip entries where `entry.is_dir(follow_symlinks=False)` would recurse into a junction — detect via `isjunction`/`st_file_attributes` check first, then call `_junction.remove`."

## Verdict

GAPS_FOUND  
One GAP: the try/except type is unspecified and the wrong default (`Exception`) silently breaks non-container paths.