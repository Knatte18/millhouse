MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-09
```

All code claims verified against source and accurate: `emit_prepare`/`start_sha` omission pattern (`_implementer_common.py:750-780`), marker-write gate (`:1093-1097`), synthetic `logic/no structured report` sentinel (`:1466`), `millpy-fix.py` finalize `nits_only=args.nits_only` (`:319`) and prepare call omitting it (`:507-516`), `_nit_gate.compute_unfixed_nits` (`:23`), SKILL step-6 flag list missing `--nits-only` (`:150-152`), identical #609 sentences (`:378`, `:680`), Handoff gate (`:721`), step 4(b)/(c) (`:131-144`), template `implementer.model: sonnethigh` (`:171`), brief anchors (`:52`, `:98`), and test pattern `test_env_override_impl` (`test-config.py:232`). Every Decision carries rationale + rejected alternatives; scope in/out is crisp; testing strategy is named per item. No blocking gaps.

## Findings

### [NOTE] #610 leaves existing carve-out prose contradictory
**Section:** implementer-liveness-probe / Technical context
**Issue:** SKILL `:131` states implementer dispatches go "never through the liveness probe in (c)" and `:133` bundles "stopped/interrupted" with turn-exhaustion; the #610 site list (`~line 131-138`) doesn't flag these for rewrite, risking a self-contradictory SKILL — the exact #609-class ambiguity this task fixes.
**Fix:** Explicitly require reconciling/qualifying the line-131 carve-out and the line-133 "OR stopped/interrupted" bundling when inserting the probe.

### [NOTE] #610 discriminator between stopped/interrupted and turn-exhaustion unstated
**Section:** implementer-liveness-probe
**Issue:** The implementer path currently treats both cases identically; the probe is scoped to stopped/interrupted only, but the discussion never states the discriminator is the same harness stopped/interrupted notification signal that step 4(c) already keys on.
**Fix:** State the implementer probe fires on the same notification signal as (c); clean turn-exhaustion = absence of that signal.

### [NOTE] #616 card-count self-check range-start undefined for fresh dispatch
**Section:** implementer-brief-completeness-self-check
**Issue:** The self-check counts commits via `<batch-start-ref>..HEAD`, but on a non-resume dispatch `<START_SHA>` is empty, leaving no range start.
**Fix:** Specify the count reuses the `git log --grep="^mill-go: start batch"` fallback when `<START_SHA>` is empty, mirroring Resume-after-incomplete.

### [NOTE] #616 regression-test assertion form left as two alternatives
**Section:** implementer-model-default-regression-test / Testing
**Issue:** "assert not `haiku`" vs. "member of an explicit allowed-tier allowlist" are offered without a firm choice.
**Fix:** Pick one — recommend the allowlist so future weak tiers are also excluded.

### [NOTE] #619 residual prose-drift risk not acknowledged
**Section:** nits-only-envelope-threading
**Issue:** Envelope-threading makes the script side unit-testable, but the fix still depends on a hand-maintained SKILL step-6 re-pass rule that remains prose-only and untested — the same drift class as the original bug, relocated not eliminated.
**Fix:** Note the residual risk; no test asserts the orchestrator actually re-passes `--nits-only`.

## Verdict

APPROVE
Well-grounded and internally consistent; only edit-precision and minor detail NOTEs remain.
MILL_REVIEW_END