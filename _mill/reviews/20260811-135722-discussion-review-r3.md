MILL_REVIEW_BEGIN
# Review: mill-go2: fork-based fixer (NIT-fix) dispatch

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:design] fork-attempted flag has no continuity across an orchestrator crash/resume
**Section:** Decision `override-applies-to-first-attempt-only` **Issue:** The flag is explicitly "local" (in-Builder-session memory), reset only at "the start of each new scope/round dispatch." But `## Resume`'s `fixing` branch (`mill-go-base/SKILL.md:964-969`) re-enters the Agent-mode dispatch pattern from step 1-3 in a brand-new Builder session after any crash/interrupt, with no memory of a prior fork attempt. A crash between the fork's terminal failure (fallback logged and committed, per `record-the-fallback`) and the cold retry's own next phase write resumes onto `phase: fixing-{scope}-r{N}` (this exact crash window is already discussed at lines 235-244, but only for phase-routing correctness) and would re-consult Override point A with the flag unset — forking a second time instead of going cold, silently breaking the "one fork attempt, then cold" invariant `cold-fallback-on-first-terminal-failure` and the retry-budget comparability `fallback-consumes-existing-retry-budget` both depend on. **Fix:** State explicitly whether Resume must consult the new `## Fork-fallback log` (a row already exists on disk for this scope/round once a fallback fired) to reconstruct the flag, or accept and document the double-fork-on-crash-resume as a residual risk.

### [NIT:consistency] wrong line citation for scope_label computation
**Section:** Decision `record-the-fallback` **Issue:** "`{scope}` is ... matching the `scope_label` the fix CLI already computes (`millpy-fix.py:655`)" — line 655 is the literal `"fix"` role string passed to `emit_prepare`; `scope_label = args.batch_name if args.scope == "batch" else "holistic"` is actually computed at `millpy-fix.py:652`. **Fix:** Correct the citation to `:652`.

## Verdict

REQUEST_CHANGES
One BLOCKING: crash/resume can silently re-fork instead of going cold, undocumented.
MILL_REVIEW_END
