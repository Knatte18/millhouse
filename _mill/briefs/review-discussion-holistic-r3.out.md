MILL_REVIEW_BEGIN
# Review: mill-go: quality-gate coverage gaps (NIT-fix regressions, missing lint gate)

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Third NIT-fix dispatch site omitted from digest wiring
**Section:** Scope ("In:" bullet 1) / Decision `symmetric-batch-and-holistic-application`
**Issue:** `mill-go/SKILL.md` dispatches `millpy-fix.py --nits-only` at three sites, not two: per-batch in-flow (lines ~741-747), holistic in-flow (lines ~1162-1168), and the Handoff "Nit-enforcement gate" self-resolve dispatch (line ~1223, `## Handoff`), which explicitly reuses "the identical CLI, args, and dispatch-mode handling already documented for the in-flow NIT-fix pass." The `symmetric-batch-and-holistic-application` Decision and the Scope's digest-wiring bullet only name the two in-flow sites (`~749-770`, `~1170-1180`); the Handoff self-resolve dispatch is unaddressed anywhere in the discussion.
**Fix:** Either explicitly scope the Handoff self-resolve dispatch into the digest-wiring work (it already mirrors the in-flow call shape, so building/passing `--prior-blocking` there should be near-free), or add an explicit Decision/Scope line stating why it is deliberately excluded and what residual risk that leaves — as written, a plan writer patching only the two named line ranges leaves this self-resolve path exposed to the exact regression this task exists to close.

## Verdict

REQUEST_CHANGES
One BLOCKING: a third NIT-fix dispatch site (Handoff self-resolve gate) is missing from the digest-wiring scope.
MILL_REVIEW_END
