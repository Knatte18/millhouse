# Review: Replace git subprocess calls with pygit2

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-20
```

## Findings

### [GAP] SystemExit not caught by `except Exception` in review wrappers
**Section:** § Exception type contract for `_capture_head_sha` and `_capture_porcelain`
**Issue:** The public API section declares `head_sha()` raises `SystemExit` on failure; the exception-contract section says `_capture_head_sha` should "catch `Exception` from `head_sha()` and re-raise as `ReviewError`". `SystemExit` inherits from `BaseException`, not `Exception`, so `except Exception:` silently lets the `SystemExit` escape uncaught — `worktree_snapshot_guard`'s type-based disambiguation never sees a `ReviewError`, breaking its invariant.
**Fix:** Decide one of two mutually exclusive policies and state it explicitly: (a) `head_sha()` / `status_porcelain()` raise a plain `Exception` subclass (not `SystemExit`) when invoked from review-context callers, or (b) the wrapping code uses `except (Exception, SystemExit):`. Whichever is chosen, update both the public-API table and the contract section to agree.

## Verdict

GAPS_FOUND
One internal inconsistency between the `_pygit2_util` error contract and the `_review_common` wrapping pattern must be resolved.