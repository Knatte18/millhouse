MILL_REVIEW_BEGIN
# Review: Fix prepare-retry atomicity, partial-batch finalize routing, and envelope field parity

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-29
```

## Findings

### [NOTE] #563 staged-empty "skip" branch is effectively unreachable
**Section:** Decisions -> prepare-retry-atomic-commit; Testing -> #563
**Issue:** `session_id = str(uuid.uuid4())` is regenerated unconditionally (millpy-implement.py L283) before `set_batch_fields` (L285), so status.md is always dirty after every fire -- the new `git diff --cached --quiet` empty path never fires in normal flow; the prescribed "nothing staged -> no commit" test exercises guard mechanics, not a real production path.
**Fix:** Note in the plan that the empty-staged case is a defensive-only branch (the UUID rewrite guarantees a non-empty staged diff each fire); keep the test but label it as guard-mechanics coverage rather than a reachable retry scenario.

## Verdict

APPROVE
Round-3 GAPs (content-commit counting, precedence, completeness-gate alignment) are resolved; no blocking gaps remain.
MILL_REVIEW_END