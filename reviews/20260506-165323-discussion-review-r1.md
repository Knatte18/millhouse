# Review: 23 (A) — mill infra bugfix-batch

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: discussion.md
date: 2026-05-06
```

## Findings

### [GAP] git rev-parse failure mode in _forward_output unaddressed
**Section:** `### commit-sha-override` / Technical context
**Issue:** The discussion says "overwrite `commit_sha` unconditionally" but is silent on what `_forward_output` should do if `git rev-parse HEAD` exits non-zero. The function currently has a deliberate "always returns 0" contract; the new subprocess call introduces a failure path that needs a stated policy.
**Fix:** Add one sentence: e.g. "On non-zero exit from `git rev-parse`, forward the original JSON unmodified (preserving the always-0 return contract)." Testing section should include a failure-path test for the subprocess mock.

## Verdict

GAPS_FOUND
One gap: `git rev-parse` failure policy in `_forward_output` is unspecified.