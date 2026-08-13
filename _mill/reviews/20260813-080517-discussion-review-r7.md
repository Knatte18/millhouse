MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 334.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [NIT:consistency] Testing section overclaims drift-guard catches arity mismatches
**Demoted-from:** BLOCKING
**Section:** `## Testing` **Issue:** Claims `test-skill-helper-drift.py` "would have caught... an arity mismatch introduced while rewriting Entry step 1's `hub_root` binding" — but the test's `_run_drift_guard` (`plugins/mill/unit_tests/test-skill-helper-drift.py:135-150`) only checks that `(module_stem, fn)` resolves to *some* function of that name in the target module; it never inspects parameter counts/signatures (confirmed via grep — no `arity`/`signature`/`inspect.signature` logic anywhere in the file). **Fix:** Reword the Testing section to state the guard catches typo'd/renamed helpers and unresolved modules only, not arity drift, so the plan writer/implementer doesn't skip manual verification of `_config.load_config(hub_root, worktree_root)`'s exact 2-arg order — precisely the class of bug #839/#826 are about.

### [NIT:consistency] `blocked_reason` example list mismatches source
**Section:** Decision "Max-rounds block: add a `blocked` re-entry row (#832)" **Issue:** "Any other `blocked_reason` value (`"non-progress round {N}"`, `"plan-validate non-progress"`)" cites `"plan-validate non-progress"` as an example — but the current step 1.5 two-pass-cap halt (SKILL.md:300) never calls `_status.set_blocked`, so that string is never actually written to `blocked_reason`; only three calls exist today (usage-error, non-progress, max-rounds), and the real third value ("plan review usage error: <message>", SKILL.md:451) is omitted from the list instead. **Fix:** Correct the illustrative list to name the actual persisted values, or note that `plan-validate non-progress`/ERROR-only/no-JSON halts are ephemeral (no status.md mutation) and therefore structurally can't reach the new `blocked` row at all.

## Verdict

APPROVE
One BLOCKING: Testing section misstates existing test coverage for the exact bug class this task fixes.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
