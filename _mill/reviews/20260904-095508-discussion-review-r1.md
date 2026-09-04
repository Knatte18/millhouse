MILL_REVIEW_BEGIN
# Review: mill-plan: entry-gate, timeline, and script-portability bugs

```yaml
duration_s: 237.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed, uncertain)
reviewed_file: _mill/discussion.md
date: 2026-09-04
```

## Findings

### [BLOCKING:design] #938 drift-guard omits Step 3.5's retry re-dispatch
**Section:** Decision `discussion-drift-guard-938` **Issue:** "before dispatching each Phase: Plan Review round" names only the once-per-round check, but `mill-plan/SKILL.md`'s Plan Review has two LLM-dispatch sites per round: step 2's initial dispatch and step 3.5's ERROR-only-aggregate retry re-dispatch (~line 495-524), which also re-invokes the reviewer without consuming the round counter. **Fix:** explicitly state whether the sha check re-runs before the step 3.5 retry too, since the Testing section itself demands "no gap where a plan could still be committed or reviewed against a stale discussion.md" and this sub-site is currently unaddressed.

### [NIT:consistency] #938 rationale's cited repro mechanism is underspecified
**Section:** Decision `discussion-drift-guard-938`, Rationale **Issue:** the cited trigger (mill-start's post-`max_review_rounds` "unresolved gaps" fallback, `mill-start/SKILL.md` line ~407) sits before Phase: Handoff in a single run, so phase cannot already be `discussed` at that point within one invocation — the "phase can stay discussed across that rewrite" framing only holds for a *second*, un-gated `/mill-start` re-invocation on an already-handed-off task (mill-start's Entry has no phase check, confirmed by reading the file). **Fix:** clarify the rationale names a re-invocation scenario, not an in-loop one, so a plan writer verifying the repro doesn't get confused reading the cited line in isolation.

## Verdict

REQUEST_CHANGES
#938's drift-guard round-dispatch coverage needs one more explicit sentence to close a real per-round gap.
MILL_REVIEW_END
