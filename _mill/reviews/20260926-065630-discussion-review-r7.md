MILL_REVIEW_BEGIN
# Review: Ask the parent session when stuck (parent_thread)

```yaml
duration_s: 89861.2
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-09-26
```

## Findings

### [BLOCKING:design] escalate-before-recording-block drops the incomplete-branch's commit/push variance
**Section:** `escalate-before-recording-block`
**Issue:** The restructuring collapses each `### Stuck escalation` bullet's own `set_batch_field`/`append_phase`/commit into a shared `*Blocked*` "records state" step, threading only `blocked_reason` through. Source (`mill-go-base/SKILL.md` `### Stuck escalation`) shows the `incomplete` bullet's commit differs from the other three: message suffix `" (incomplete after resume)"` plus a `git push`, which infrastructure/transient/verify-logic do not do. The decision names no parameter for this and doesn't say whether `*Blocked*` pushes for every stuck type now, drops the push, or needs a second threaded value.
**Fix:** Name the extra parameter(s) `*Blocked*` needs (e.g. `commit_message`, `needs_push`) so the `incomplete` behavior survives the restructuring unchanged.

## Verdict

REQUEST_CHANGES
One unresolved implicit decision in how the shared Blocked funnel preserves per-stuck-type commit/push behavior.
MILL_REVIEW_END
