MILL_REVIEW_BEGIN
# Review: mill-go: done-gate halt path and cleanliness-gate recovery are under-documented

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; brief dictates sonnethigh)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] dead-parent fallback/cycle halt mechanism unspecified per call site
**Section:** Decision `cleanliness-gate-dead-parent-recovery`, `fallback`/`cycle` bullets.
**Issue:** The two call sites use different halt idioms verified in source: SKILL.md step 2b's existing "parent diff unresolvable" path sets `_status.set_batch_field(..., "blocked_reason", ...)` + `append_phase("blocked")` + commit + "Go to *Blocked*" (batch-scoped, shared section auto-releases the lock); handoff.md's terminal gate's existing halt (line 53) only prints a `BLOCKED:` message with no `blocked_reason` field write and explicitly "Do NOT set phase: done" (task-scoped, no state mutation). The `fallback`/`cycle` bullets prescribe one unified shape ("halt — `blocked_reason: ...` — release the builder lock") without saying which mechanism applies at which site — unlike item 4 in the same decision, which explicitly says "halt with the existing message as today (**or the batch-2b equivalent**)," acknowledging the two sites differ. Applied literally at the terminal gate, "release the builder lock" plus a bare `blocked_reason:` write introduces a field handoff.md's own convention never uses; applied literally at step 2b, it risks bypassing the batch-state bookkeeping (`state: blocked`, `Go to *Blocked*`) that a resumed `/mill-go` depends on to find the blocked batch.
**Fix:** State explicitly, per call site, which existing mechanism the `fallback`/`cycle` halts route through — step 2b via its own batch-blocked + Go-to-*Blocked* path, handoff.md's terminal gate via its own bare `BLOCKED:` message (with lock release now added by the other decision) — mirroring item 4's own site-differentiated phrasing.

### [NIT:decision] notify event name/kwargs unspecified for handoff.md's new lock-release+notify halts
**Section:** Decision `builder-lock-release-all-handoff-halts`.
**Issue:** The decision mandates `_notify.notify(...)` at all four handoff.md halt points but never states the event name or kwargs to pass — the cited canonical shape (`SKILL.md`'s `### Blocked`) uses `slug=slug, batch=batch_name`, but handoff.md's four gates are task-scoped with no `batch_name` in play.
**Fix:** Name the event string and kwargs to use at these four task-scoped call sites (e.g. reuse `"<VARIANT_LABEL>.blocked"` with `slug=slug` only, no `batch=`).

## Verdict

REQUEST_CHANGES
One BLOCKING: dead-parent fallback/cycle halt mechanism is unspecified across two structurally different call sites.
MILL_REVIEW_END
