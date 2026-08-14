MILL_REVIEW_BEGIN
# Review: mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (best-effort self-assessment; environment metadata reports claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-14
```

## Findings

### [BLOCKING:consistency] String-fallback pattern won't match the quoted WinError text
**Section:** Decision `baseline-retry-match-on-winerror-not-string` **Issue:** the string fallback `"directory not empty" in str(exc).lower()` cannot match the actual message text the Problem section itself quotes verbatim — `[WinError 145] The directory is not empty` lowercases to `"the directory is not empty"`, which contains `"directory is not empty"`, not the pattern's `"directory not empty"` (the pattern omits "is"). **Fix:** correct the fallback pattern (e.g. `"directory is not empty"` or a looser check) so it actually matches Windows' real ERROR_DIR_NOT_EMPTY message text, and confirm no other reference elsewhere in the discussion repeats the wrong string.

### [NIT:design] Baseline wrapper's except clause narrower than the "never raises" contract it targets
**Section:** Decision `baseline-teardown-defense-in-depth`, layer (b) **Issue:** the wrapper around each `remove_safe` call site is scoped to `WorktreeError`/`WorktreeLockedError`, but `_run_baseline_stage`'s docstring promise ("Never raises") is unconditional; `remove_safe` also contains unguarded `_subprocess_util.run` calls (e.g. missing git binary) and calls into `_junction.strip_all_in_worktree`, whose exception surface isn't addressed by this task. **Fix:** either broaden layer (b)'s except to a general `Exception` catch to fully honor the docstring's existing promise, or explicitly scope the Decision's language to "only the WinError-145 retry-exhaustion case" so the docstring/SKILL.md guarantee isn't overstated by this fix.

## Verdict

REQUEST_CHANGES
Fix the self-contradicting WinError-145 string-match pattern before plan writing proceeds.
MILL_REVIEW_END
